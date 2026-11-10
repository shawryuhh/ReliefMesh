// Shared pure logic embedded verbatim in exports and exercised by tests.
// No filesystem, network, environment or credentials inside Code nodes.
function assert(ok, code) { if (!ok) throw new Error(code); }
function stableId(value) { return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value); }
function normalizeEvent(input, kind) {
  const b = JSON.parse(JSON.stringify(input));
  assert(b.schema_version === 1 && b.event_type === kind, 'INVALID_EVENT_TYPE');
  assert(stableId(b.event_id) && stableId(b.correlation_id), 'STABLE_SOURCE_ID_REQUIRED');
  assert(typeof b.source === 'string' && b.source.trim() === 'synthetic-demo', 'FIXTURE_SOURCE_REQUIRED');
  b.source = b.source.trim();
  assert(typeof b.occurred_at === 'string' && /(Z|[+-]\d\d:\d\d)$/.test(b.occurred_at) && Number.isFinite(Date.parse(b.occurred_at)), 'INVALID_TIMESTAMP');
  b.occurred_at = new Date(b.occurred_at).toISOString();
  const p = b.payload;
  assert(p && typeof p === 'object' && !Array.isArray(p), 'INVALID_PAYLOAD');
  if (kind === 'report_received') {
    assert(!('incident_id' in b) && !('expected_version' in b), 'BACKEND_OWNS_INCIDENT');
    assert(stableId(p.source_report_id) && p.channel === 'synthetic', 'INVALID_SOURCE_REPORT');
    assert(typeof p.originalText === 'string' && p.originalText.trim().length > 0 && p.originalText.length <= 10000, 'INVALID_ORIGINAL_TEXT');
    assert(['en','hi','kn','ta','te','ml','mr','bn','gu','pa','ur','as','or'].includes(p.originalLanguage), 'INVALID_ORIGINAL_LANGUAGE');
    assert(typeof p.receivedAt === 'string' && /(Z|[+-]\d\d:\d\d)$/.test(p.receivedAt) && Number.isFinite(Date.parse(p.receivedAt)), 'INVALID_RECEIVED_AT');
  } else {
    assert(stableId(b.incident_id) && Number.isInteger(b.expected_version) && b.expected_version > 0, 'INCIDENT_VERSION_REQUIRED');
    if (kind === 'road_obstruction') {
      assert(stableId(p.assignment_id) && stableId(p.resource_id), 'ASSIGNMENT_REQUIRED');
      assert(Number.isFinite(p.previous_eta_minutes) && p.previous_eta_minutes >= 0 && Number.isFinite(p.eta_minutes) && p.eta_minutes >= 0 && p.reason_code === 'road_blocked', 'INVALID_ETA');
    } else {
      assert(Array.isArray(p.assignment_ids) && p.assignment_ids.length > 0 && p.assignment_ids.every(stableId) && new Set(p.assignment_ids).size === p.assignment_ids.length, 'ASSIGNMENTS_REQUIRED');
      assert(p.evidence === 'simulated responder completion', 'SIMULATED_EVIDENCE_REQUIRED');
    }
  }
  // Immutable originals (including whitespace) are never translated/rewritten.
  return b;
}
function request(stage, method, path, body, key) {
  return {stage, method, path, body, key, attempt: 1, retry: false, more: true, failed: false};
}
function prepare(input, kind, executionId, mode = 'fixture') {
  assert(mode === 'fixture', 'LIVE_DISABLED_PENDING_PERSON_2_CONTRACT');
  const context = {mode, execution_id: String(executionId), base_url: 'http://127.0.0.1:8094'};
  if (kind === 'dispatch') return {...context, ...request('poll', 'GET', '/fixture/v1/automation/commands?state=pending', {}, 'poll:' + executionId)};
  const envelope = normalizeEvent(input, kind);
  return {...context, envelope, ...request('event', 'POST', '/fixture/v1/automation/events', envelope, envelope.event_id)};
}
function commandCheck(c, now) {
  assert(c && stableId(c.command_id) && stableId(c.incident_id), 'INVALID_COMMAND');
  assert(c.state === 'claimed' && ['dispatch', 'redispatch'].includes(c.action), 'UNAUTHORIZED_COMMAND');
  assert(c.authorization && stableId(c.authorization.approval_id) && c.authorization.version === c.recommendation_version && typeof c.authorization.actor === 'string' && c.authorization.actor.length > 0, 'COMMITTED_APPROVAL_REQUIRED');
  assert(Number.isInteger(c.recommendation_version) && c.recommendation_version > 0, 'INVALID_VERSION');
  assert(stableId(c.claim_token) && Date.parse(c.lease_expires_at) > now + 1000, 'EXPIRED_CLAIM');
  assert(Array.isArray(c.approved_resource_ids) && new Set(c.approved_resource_ids).size === c.approved_resource_ids.length, 'INVALID_APPROVED_SET');
  assert(Array.isArray(c.new_assignments) && c.new_assignments.length > 0 && Array.isArray(c.continuing_assignment_ids) && Array.isArray(c.superseded_assignment_ids), 'INVALID_ASSIGNMENTS');
  const ids = c.new_assignments.map(a => a.assignment_id), rids = c.new_assignments.map(a => a.resource_id);
  assert(ids.every(stableId) && rids.every(stableId) && new Set(ids).size === ids.length && new Set(rids).size === rids.length, 'DUPLICATE_ASSIGNMENT');
  assert(c.new_assignments.every(a => c.approved_resource_ids.includes(a.resource_id) && !c.continuing_assignment_ids.includes(a.assignment_id) && !c.superseded_assignment_ids.includes(a.assignment_id)), 'CONTINUING_OR_UNAPPROVED_RESOURCE');
  return c;
}
function callback(c, outcome, delivery, error) {
  return {event_id: c.command_id + ':result:' + c.claim_attempts + ':' + outcome,
    claim_token: c.claim_token, outcome, occurred_at: new Date().toISOString(),
    ...(outcome === 'accepted' ? {delivery_reference: delivery} : {error_code: error})};
}
function fail(ctx, code) {
  const failure = {failure_id: ctx.execution_id + ':' + ctx.stage, stage: ctx.stage,
    event_id: ctx.envelope?.event_id || null, command_id: ctx.command?.command_id || null,
    attempts: ctx.attempt, error_code: code, simulated: true};
  if (ctx.stage === 'failure_log') return {...ctx, retry: false, more: false, failed: true, failure: ctx.failure || failure};
  if (ctx.stage === 'delivery' && ctx.command) {
    const b = callback(ctx.command, 'failed', null, code);
    return {...ctx, failure, ...request('failed_callback', 'POST', '/fixture/v1/automation/commands/' + ctx.command.command_id + '/result', b, b.event_id)};
  }
  const record = ctx.failure || failure;
  return {...ctx, failure: record, ...request('failure_log', 'POST', '/fixture/failures', record, record.failure_id)};
}
function advance(ctx, response, now = Date.now()) {
  assert(ctx.mode === 'fixture' && ctx.base_url === 'http://127.0.0.1:8094' && ctx.path.startsWith('/fixture/'), 'LIVE_DISABLED');
  const status = Number(response.statusCode || 0);
  let b = response.body;
  if (typeof b === 'string') { try { b = JSON.parse(b); } catch { b = {}; } }
  b = b || {};
  const transient = status === 0 || status === 429 || status >= 500;
  if (transient && ctx.attempt < 4) {
    let delay = [1, 3, 10][ctx.attempt - 1];
    const ra = response.headers?.['retry-after'];
    if (ra) {
      const parsed = /^\d+$/.test(String(ra)) ? Number(ra) : Math.ceil((Date.parse(ra) - now) / 1000);
      if (Number.isFinite(parsed)) delay = Math.max(delay, parsed);
    }
    if (delay > 30) return fail(ctx, 'RETRY_AFTER_REQUIRES_OPERATOR');
    return {...ctx, attempt: ctx.attempt + 1, retry: true, delay_seconds: delay};
  }
  if (status < 200 || status >= 300) return fail(ctx, transient ? 'RETRY_EXHAUSTED' : (b.code || 'HTTP_' + status));
  try {
    assert(b.fixture === true, 'FIXTURE_RESPONSE_REQUIRED');
    const next = (stage, path, body, key, method = 'POST') => ({...ctx, ...request(stage, method, path, body, key)});
    if (ctx.stage === 'event') {
      assert(b.accepted === true && b.event_id === ctx.envelope.event_id && stableId(b.incident_id), 'MISMATCHED_EVENT_ACK');
      return {...ctx, more: false, retry: false, result: b};
    }
    if (ctx.stage === 'poll') {
      assert(Array.isArray(b.command_ids) && b.command_ids.every(stableId), 'INVALID_COMMAND_LIST');
      if (!b.command_ids.length) return {...ctx, more: false, retry: false, result: {status: ['awaiting_approval','awaiting_replacement'].includes(b.phase) ? 'WAIT_FOR_HUMAN' : 'NO_AUTHORIZED_COMMAND', phase: b.phase, fixture: true}};
      const id = b.command_ids[0];
      return {...next('claim', '/fixture/v1/automation/commands/' + id + '/claim', {worker_id: 'fixture-n8n'}, 'claim:' + ctx.execution_id + ':' + id), requested_command_id: id};
    }
    if (ctx.stage === 'claim') {
      const c = commandCheck(b.command, now);
      assert(c.command_id === ctx.requested_command_id, 'CLAIM_ID_MISMATCH');
      return {...next('validate', '/fixture/v1/automation/commands/' + c.command_id + '/validate', {claim_token: c.claim_token}, c.command_id + ':validate:' + c.claim_attempts), command: c};
    }
    if (ctx.stage === 'validate') {
      const c = commandCheck(b.command, now);
      assert(b.valid === true && JSON.stringify(c) === JSON.stringify(ctx.command), 'REVALIDATION_MISMATCH');
      const body = {command_id: c.command_id, claim_token: c.claim_token, incident_id: c.incident_id, recommendation_version: c.recommendation_version, new_assignments: c.new_assignments};
      return next('delivery', '/fixture/receiver/deliver', body, c.command_id);
    }
    if (ctx.stage === 'delivery') {
      assert(b.simulated === true && b.command_id === ctx.command.command_id && typeof b.delivery_reference === 'string', 'INVALID_DELIVERY_RECEIPT');
      const body = callback(ctx.command, 'accepted', b.delivery_reference);
      return next('callback', '/fixture/v1/automation/commands/' + ctx.command.command_id + '/result', body, body.event_id);
    }
    if (ctx.stage === 'callback') {
      assert(b.accepted === true && b.command_id === ctx.command.command_id, 'MISMATCHED_CALLBACK');
      return {...ctx, more: false, retry: false, result: {status: 'SIMULATED_DELIVERY_RECORDED', command_id: b.command_id, fixture: true}};
    }
    if (ctx.stage === 'failed_callback') return fail(ctx, ctx.failure.error_code);
    if (ctx.stage === 'failure_log') return {...ctx, retry: false, more: false, failed: true};
    throw new Error('UNKNOWN_STAGE');
  } catch (e) { return fail(ctx, e.message); }
}
if (typeof module !== 'undefined') module.exports = {prepare, advance, normalizeEvent, commandCheck};
