"""LOCAL TEST DOUBLE ONLY. No real backend, AI, credentials, or responders.

SQLite serializes synthetic state/receipts so concurrent delivery and process
restarts can be tested. This is not Person 2's backend implementation.
"""
import argparse
import copy
import hashlib
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PREFIX = '/fixture/v1'


class Rejected(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def require(condition, code='INVALID_ENVELOPE', status=422):
    if not condition:
        raise Rejected(status, code)


def stamp():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def initial():
    return dict(fixture=True, phase='empty', revision=0, version=0, reports=[],
                assignments={}, commands={}, resources={k: 'available' for k in
                ['AMB-02', 'AMB-05', 'RESCUE-01']}, approvals=[], audit=[],
                receipts={}, deliveries={}, failures=[], faults={}, requests=[], pending_plan=None)


class Fixture:
    def __init__(self, db):
        self.db = str(db)
        with sqlite3.connect(self.db) as con:
            con.execute('CREATE TABLE IF NOT EXISTS fixture (id INTEGER PRIMARY KEY, state TEXT)')
            con.execute('INSERT OR IGNORE INTO fixture VALUES (1, ?)', (json.dumps(initial()),))

    def call(self, method, path, body=None, actor='automation', key=None):
        body = body or {}
        path = urlsplit(path).path
        with sqlite3.connect(self.db, timeout=15) as con:
            con.execute('BEGIN IMMEDIATE')
            s = json.loads(con.execute('SELECT state FROM fixture WHERE id=1').fetchone()[0])
            before = copy.deepcopy(s)
            try:
                fault = s['faults'].get(path, [])
                if fault:
                    status = fault.pop(0)
                    result = {'code': 'INJECTED_TRANSIENT' if status >= 500 or status == 429 else 'INJECTED_REJECTION'}
                else:
                    status, result = self.route(s, method, path, body, actor, key)
            except Rejected as e:
                s = before  # rejection must not partially change state
                status, result = e.status, {'code': e.code}
            if method != 'GET' or path != PREFIX + '/snapshot':
                s['requests'].append({'path': path, 'status': status, 'key': key,
                                      'body_hash': digest(body)})
            con.execute('UPDATE fixture SET state=? WHERE id=1', (json.dumps(s),))
        return status, {**result, 'fixture': True}

    def audit(self, s, kind, **data):
        s['revision'] += 1
        s['audit'].append(dict(id=f"fixture-audit-{s['revision']}", type=kind,
                               occurred_at=stamp(), **data))

    def replay(self, s, scope, key, body):
        require(isinstance(key, str) and bool(key), 'IDEMPOTENCY_KEY_REQUIRED')
        old = s['receipts'].get(scope + ':' + key)
        if old:
            require(old['hash'] == digest(body), 'IDEMPOTENCY_CONFLICT', 409)
            return {**old['result'], 'duplicate': True}

    def receipt(self, s, scope, key, body, result):
        s['receipts'][scope + ':' + key] = {'hash': digest(body), 'result': result}
        return result

    def envelope(self, b):
        require(b.get('schema_version') == 1 and b.get('source') == 'synthetic-demo')
        for field in ['event_id', 'event_type', 'occurred_at', 'correlation_id']:
            require(isinstance(b.get(field), str) and 0 < len(b[field]) <= 128)
        require(isinstance(b.get('payload'), dict))
        try:
            dt = datetime.fromisoformat(b['occurred_at'].replace('Z', '+00:00'))
            require(dt.tzinfo is not None)
        except ValueError:
            raise Rejected(422, 'INVALID_TIMESTAMP')
        # Historical synthetic timestamps are allowed; live freshness is a contract decision.

    def current(self, s, b):
        require(b.get('incident_id') == 'INC-1042', 'INCIDENT_MISMATCH', 409)
        require(s['phase'] not in ['empty', 'resolved'], 'TERMINAL_OR_MISSING', 409)
        require(b.get('expected_version') == s['version'], 'STALE_VERSION', 409)

    def authorized(self, s, cid, b, allow_accepted=False, allow_failed=False):
        c = s['commands'].get(cid)
        require(c is not None, 'UNKNOWN_COMMAND', 404)
        require(s['phase'] not in ['empty', 'resolved'] and c['recommendation_version'] == s['version'], 'STALE_COMMAND', 409)
        require(c['state'] == 'claimed' or (allow_accepted and c['state'] == 'accepted') or
                (allow_failed and c['state'] == 'failed'), 'INVALID_COMMAND_STATE', 409)
        require(b.get('claim_token') == c.get('claim_token'), 'INVALID_CLAIM', 403)
        require(time.time() < c.get('lease_until', 0), 'LEASE_EXPIRED', 409)
        require(all(s['assignments'][x['assignment_id']]['status'] == 'dispatched' for x in c['new_assignments']), 'STALE_ASSIGNMENT', 409)
        return c

    def route(self, s, method, path, b, actor, key):
        require(actor in ['automation', 'fixture-coordinator'], 'FORBIDDEN', 403)
        if method == 'GET' and path == PREFIX + '/snapshot':
            return 200, copy.deepcopy(s)
        if path.startswith('/fixture/control/'):
            require(actor == 'fixture-coordinator', 'APPROVAL_FORBIDDEN', 403)
            require(method == 'POST')
            if path == '/fixture/control/faults':
                require(isinstance(b.get('path'), str) and isinstance(b.get('statuses'), list))
                require(len(b['statuses']) <= 10 and all(type(v) is int and 400 <= v <= 599 for v in b['statuses']))
                s['faults'][b['path']] = b['statuses']
                return 200, {'configured': True}
            require(path == '/fixture/control/approve', 'NOT_FOUND', 404)
            require(b.get('human_confirmed') is True, 'HUMAN_CONFIRMATION_REQUIRED', 403)
            require(s['phase'] in ['awaiting_approval', 'awaiting_replacement'] and b.get('version') == s['version'], 'STALE_PLAN', 409)
            replacement = s['phase'] == 'awaiting_replacement'
            resources = ['AMB-05'] if replacement else ['AMB-02', 'RESCUE-01']
            if replacement:
                s['assignments']['ASG-887']['status'] = 'superseded'
                s['resources']['AMB-02'] = 'available'
                for c in s['commands'].values():
                    if c['state'] != 'accepted':
                        c['state'] = 'cancelled'
            new = []
            for rid in resources:
                aid = {'AMB-02': 'ASG-887', 'RESCUE-01': 'ASG-888', 'AMB-05': 'ASG-889'}[rid]
                s['assignments'][aid] = dict(assignment_id=aid, resource_id=rid, status='dispatched')
                s['resources'][rid] = 'dispatched'
                new.append(dict(assignment_id=aid, resource_id=rid))
            cid = f"fixture-INC-1042-v{s['version']}"
            approval = {'approval_id': f"fixture-approval-{s['version']}", 'actor': 'fixture-coordinator', 'version': s['version']}
            s['approvals'].append(approval)
            c = dict(command_id=cid, incident_id='INC-1042', recommendation_version=s['version'],
                     action='redispatch' if replacement else 'dispatch', authorization=approval,
                     approved_resource_ids=['AMB-05', 'RESCUE-01'] if replacement else resources,
                     new_assignments=new, continuing_assignment_ids=['ASG-888'] if replacement else [],
                     superseded_assignment_ids=['ASG-887'] if replacement else [],
                     state='pending', claim_attempts=0, created_at=stamp())
            s['commands'][cid] = c
            s['phase'] = 'dispatched'
            s['pending_plan'] = None
            self.audit(s, 'replacement_approved' if replacement else 'approved', command_id=cid)
            return 200, {'command_id': cid, 'phase': s['phase']}

        require(actor == 'automation', 'AUTOMATION_ROLE_REQUIRED', 403)
        if method == 'POST' and path == PREFIX + '/automation/events':
            self.envelope(b)
            require(key == b['event_id'], 'IDEMPOTENCY_KEY_MISMATCH')
            old = self.replay(s, 'event', key, b)
            if old:
                return 200, old
            p, kind = b['payload'], b['event_type']
            if kind == 'report_received':
                require(s['phase'] == 'empty', 'INCIDENT_ALREADY_EXISTS_OR_TERMINAL', 409)
                require('incident_id' not in b, 'CLIENT_INCIDENT_ID_FORBIDDEN')
                require(all(isinstance(p.get(k), str) and p[k].strip() for k in
                            ['source_report_id', 'channel', 'originalText', 'originalLanguage', 'receivedAt']))
                require(len(p['originalText']) <= 10000)
                s['reports'].append(copy.deepcopy(p))
                s['phase'], s['version'] = 'awaiting_approval', 1
                s['pending_plan'] = dict(version=1, state='pending', simulated=True,
                    recommended_resources=['AMB-02', 'RESCUE-01'], eta_minutes={'AMB-02': 6})
                self.audit(s, 'report_received', event_id=key)
                self.audit(s, 'fixture_analysis_pending_plan', simulated=True)
            elif kind == 'road_obstruction':
                self.current(s, b)
                require(s['phase'] == 'dispatched' and s['version'] == 1, 'INVALID_PHASE', 409)
                a = s['assignments'].get(p.get('assignment_id'), {})
                require(a.get('resource_id') == p.get('resource_id') == 'AMB-02' and a.get('status') == 'dispatched', 'STALE_ASSIGNMENT', 409)
                require(p.get('previous_eta_minutes') == 6 and p.get('eta_minutes') == 24, 'INVALID_FIXTURE_ETA')
                require(s['commands']['fixture-INC-1042-v1']['state'] == 'accepted', 'DELIVERY_NOT_CONFIRMED', 409)
                s['phase'], s['version'] = 'awaiting_replacement', 2
                s['pending_plan'] = dict(version=2, state='pending', simulated=True,
                    recommended_resources=['AMB-05', 'RESCUE-01'], replacement_for='AMB-02',
                    eta_minutes={'AMB-02': 24, 'AMB-05': 9}, continuing_resource_ids=['RESCUE-01'])
                self.audit(s, 'road_obstruction', event_id=key, previous_eta_minutes=6, eta_minutes=24)
                self.audit(s, 'fixture_replacement_pending', simulated=True, eta_minutes=9)
            elif kind == 'response_completed':
                self.current(s, b)
                require(s['phase'] == 'dispatched', 'INVALID_PHASE', 409)
                current = sorted(k for k, a in s['assignments'].items() if a['status'] == 'dispatched')
                require(isinstance(p.get('assignment_ids'), list) and sorted(p['assignment_ids']) == current, 'STALE_ASSIGNMENT', 409)
                require(p.get('evidence') == 'simulated responder completion', 'COMPLETION_EVIDENCE_REQUIRED')
                require(all(c['state'] == 'accepted' for c in s['commands'].values() if c['recommendation_version'] == s['version']), 'DELIVERY_NOT_CONFIRMED', 409)
                for aid in current:
                    s['assignments'][aid]['status'] = 'completed'
                    s['resources'][s['assignments'][aid]['resource_id']] = 'available'
                for c in s['commands'].values():
                    if c['state'] != 'accepted':
                        c['state'] = 'cancelled'
                s['phase'] = 'resolved'
                self.audit(s, 'incident_resolved', event_id=key)
            else:
                raise Rejected(422, 'UNSUPPORTED_EVENT')
            result = dict(event_id=key, accepted=True, duplicate=False, incident_id='INC-1042', revision=s['revision'], phase=s['phase'])
            return 202, self.receipt(s, 'event', key, b, result)

        if method == 'GET' and path == PREFIX + '/automation/commands':
            commands = [c['command_id'] for c in s['commands'].values() if c['state'] == 'pending' or
                        (c['state'] == 'claimed' and time.time() >= c['lease_until'] and c['claim_attempts'] < 3)]
            return 200, {'command_ids': commands, 'phase': s['phase'], 'version': s['version']}

        match = re.fullmatch(PREFIX + r'/automation/commands/([A-Za-z0-9_-]+)/(claim|validate|result)', path)
        if match and method == 'POST':
            cid, op = match.groups()
            if op == 'claim':
                old = self.replay(s, 'claim', key, b)
                if old:
                    return 200, old
                c = s['commands'].get(cid)
                require(c is not None, 'UNKNOWN_COMMAND', 404)
                require(c['recommendation_version'] == s['version'] and s['phase'] == 'dispatched', 'STALE_COMMAND', 409)
                require(c['state'] == 'pending' or (c['state'] == 'claimed' and time.time() >= c['lease_until']), 'ALREADY_CLAIMED', 409)
                require(c['claim_attempts'] < 3, 'CLAIMS_EXHAUSTED', 409)
                c['claim_attempts'] += 1
                c['state'], c['claim_token'] = 'claimed', 'fixture-lease-' + digest({'claim': key, 'id': cid})[:16]
                c['lease_until'] = time.time() + 180
                c['lease_expires_at'] = datetime.fromtimestamp(c['lease_until'], timezone.utc).isoformat()
                return 200, self.receipt(s, 'claim', key, b, {'command': copy.deepcopy(c), 'duplicate': False})
            if op == 'validate':
                c = self.authorized(s, cid, b)
                return 200, {'valid': True, 'command': copy.deepcopy(c)}
            # Check terminal/current command BEFORE a result replay. Old callbacks cannot reactivate.
            c = self.authorized(s, cid, b, allow_accepted=True, allow_failed=True)
            require(key == b.get('event_id'), 'IDEMPOTENCY_KEY_MISMATCH')
            old = self.replay(s, 'result', key, b)
            if old:
                return 200, old
            require(c['state'] == 'claimed', 'RESULT_ALREADY_FINAL', 409)
            require(b.get('outcome') in ['accepted', 'failed'])
            if b['outcome'] == 'accepted':
                require(b.get('delivery_reference') == s['deliveries'].get(cid, {}).get('delivery_reference') and cid in s['deliveries'], 'DELIVERY_MISMATCH', 409)
            c['state'] = b['outcome']
            self.audit(s, 'delivery_' + b['outcome'], command_id=cid)
            return 200, self.receipt(s, 'result', key, b, {'accepted': True, 'command_id': cid, 'duplicate': False})

        if method == 'POST' and path == '/fixture/receiver/deliver':
            cid = b.get('command_id')
            c = self.authorized(s, cid, b, allow_accepted=True)
            require(key == cid, 'IDEMPOTENCY_KEY_MISMATCH')
            # A receiver deduplicates the immutable command payload, not the renewable lease.
            immutable = {k: v for k, v in b.items() if k != 'claim_token'}
            old = self.replay(s, 'delivery', key, immutable)
            if old:
                return 200, old
            require(b.get('new_assignments') == c['new_assignments'] and b.get('recommendation_version') == c['recommendation_version']
                    and b.get('incident_id') == c['incident_id'], 'COMMAND_MISMATCH', 409)
            result = dict(delivery_reference='simulated:' + cid, command_id=cid, duplicate=False, simulated=True)
            s['deliveries'][cid] = result
            self.audit(s, 'simulated_delivery', command_id=cid, resources=[a['resource_id'] for a in c['new_assignments']])
            return 200, self.receipt(s, 'delivery', key, immutable, result)

        if method == 'POST' and path == '/fixture/failures':
            old = self.replay(s, 'failure', key, b)
            if old:
                return 200, old
            s['failures'].append(b)
            return 200, self.receipt(s, 'failure', key, b, {'recorded': True})
        raise Rejected(404, 'NOT_FOUND')


def serve(db, port):
    fixture = Fixture(db)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.run_request()

        def do_POST(self):
            self.run_request()

        def run_request(self):
            try:
                size = int(self.headers.get('Content-Length', '0'))
                require(0 <= size <= 65536, 'PAYLOAD_TOO_LARGE', 413)
                body = json.loads(self.rfile.read(size)) if size else {}
                require(isinstance(body, dict))
                status, result = fixture.call(self.command, self.path, body,
                    self.headers.get('X-Fixture-Actor', ''), self.headers.get('Idempotency-Key'))
            except (ValueError, Rejected) as e:
                status, result = (e.status, {'code': e.code}) if isinstance(e, Rejected) else (422, {'code': 'INVALID_JSON'})
            data = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            if status == 429:
                self.send_header('Retry-After', '1')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            pass  # No report text/lease tokens in console logs.

    print(f'LOCAL FIXTURE ONLY http://127.0.0.1:{port}; state={db}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8094)
    parser.add_argument('--db', type=Path, default=ROOT / '.runtime' / 'fixture.sqlite')
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    serve(args.db, args.port)
