"""Contract-double tests. These do NOT test Person 2's real backend."""
import concurrent.futures
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from fixture_server import Fixture, PREFIX
ROOT = Path(__file__).resolve().parents[1]

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'state.sqlite'
        self.f = Fixture(self.db)
        self.data = {n: json.loads((ROOT / 'fixtures' / (n + '.json')).read_text()) for n in ['intake','obstruction','completion']}
    def tearDown(self): self.tmp.cleanup()
    def event(self, name, body=None):
        b = body or self.data[name]
        return self.f.call('POST', PREFIX+'/automation/events', b, key=b['event_id'])
    def snapshot(self): return self.f.call('GET', PREFIX+'/snapshot')[1]
    def approve(self, v):
        return self.f.call('POST','/fixture/control/approve',{'version':v,'human_confirmed':True},'fixture-coordinator')
    def claim(self, v):
        cid = f'fixture-INC-1042-v{v}'
        status, b = self.f.call('POST',PREFIX+'/automation/commands/'+cid+'/claim',{'worker_id':'test'},key='claim-'+str(v))
        self.assertEqual(status,200,b)
        return b['command']
    def delivery(self,c):
        b = {k:c[k] for k in ['command_id','claim_token','incident_id','recommendation_version','new_assignments']}
        return self.f.call('POST','/fixture/receiver/deliver',b,key=c['command_id'])
    def result(self,c):
        b = dict(event_id=c['command_id']+':accepted',claim_token=c['claim_token'],outcome='accepted',occurred_at=c['created_at'],delivery_reference='simulated:'+c['command_id'])
        return self.f.call('POST',PREFIX+'/automation/commands/'+c['command_id']+'/result',b,key=b['event_id'])
    def initial_dispatch(self):
        self.assertEqual(self.event('intake')[0],202)
        self.assertEqual(self.approve(1)[0],200)
        c=self.claim(1)
        self.assertEqual(self.delivery(c)[0],200)
        self.assertEqual(self.result(c)[0],200)
        return c
    def replacement(self):
        c1=self.initial_dispatch()
        self.assertEqual(self.event('obstruction')[0],202)
        self.assertEqual(self.approve(2)[0],200)
        c2=self.claim(2)
        self.assertEqual(self.delivery(c2)[0],200)
        self.assertEqual(self.result(c2)[0],200)
        return c1,c2
    def test_both_human_gates_and_resolution(self):
        self.event('intake')
        for _ in range(3): self.assertEqual(self.f.call('GET',PREFIX+'/automation/commands')[1]['command_ids'],[])
        self.assertEqual(self.snapshot()['phase'],'awaiting_approval')
        self.assertEqual(self.snapshot()['assignments'],{})
        self.approve(1); c=self.claim(1); self.delivery(c); self.result(c)
        self.event('obstruction')
        for _ in range(3): self.assertEqual(self.f.call('GET',PREFIX+'/automation/commands')[1]['command_ids'],[])
        self.assertEqual(self.snapshot()['resources']['AMB-05'],'available')
        self.approve(2); c=self.claim(2)
        self.assertEqual(c['new_assignments'],[{'assignment_id':'ASG-889','resource_id':'AMB-05'}])
        self.assertEqual(c['continuing_assignment_ids'],['ASG-888'])
        self.delivery(c); self.result(c)
        self.assertEqual(self.event('completion')[0],202)
        s=self.snapshot()
        self.assertEqual(s['phase'],'resolved')
        self.assertEqual(set(s['resources'].values()),{'available'})
        self.assertEqual(s['assignments']['ASG-887']['status'],'superseded')
        self.assertEqual(len(s['approvals']),2)
        self.assertEqual(len(s['deliveries']),2)
        self.assertEqual(sum(a['type']=='incident_resolved' for a in s['audit']),1)
    def test_originals_and_duplicate_intake(self):
        self.event('intake'); self.assertTrue(self.event('intake')[1]['duplicate'])
        self.assertEqual(self.snapshot()['reports'],[self.data['intake']['payload']])
    def test_same_id_changed_payload_conflicts(self):
        self.event('intake'); b=copy.deepcopy(self.data['intake']); b['payload']['originalText']+=' changed'
        self.assertEqual(self.event('intake',b),(409,{'code':'IDEMPOTENCY_CONFLICT','fixture':True}))
    def test_automation_cannot_approve(self):
        self.event('intake')
        self.assertEqual(self.f.call('POST','/fixture/control/approve',{'version':1,'human_confirmed':True})[0],403)
        self.assertEqual(self.snapshot()['commands'],{})
    def test_forged_command_or_approval_metadata_not_authority(self):
        self.event('intake')
        self.assertEqual(self.f.call('POST','/fixture/receiver/deliver',{'command_id':'forged','approval_required':False,'approved_by':'coordinator'},key='forged')[0],404)
    def test_duplicate_delivery_and_callback(self):
        c=self.initial_dispatch()
        self.assertTrue(self.delivery(c)[1]['duplicate']); self.assertTrue(self.result(c)[1]['duplicate'])
        self.assertEqual(len(self.snapshot()['deliveries']),1)
    def test_concurrent_delivery_one_effect(self):
        self.event('intake'); self.approve(1); c=self.claim(1)
        with concurrent.futures.ThreadPoolExecutor(8) as pool: results=list(pool.map(lambda _:self.delivery(c),range(8)))
        self.assertTrue(all(s==200 for s,b in results)); self.assertEqual(sum(not b['duplicate'] for s,b in results),1)
    def test_changed_delivery_conflicts(self):
        c=self.initial_dispatch(); b={k:c[k] for k in ['command_id','claim_token','incident_id','recommendation_version','new_assignments']}
        b['new_assignments']=[]
        self.assertEqual(self.f.call('POST','/fixture/receiver/deliver',b,key=c['command_id'])[1]['code'],'IDEMPOTENCY_CONFLICT')
    def test_duplicate_obstruction(self):
        self.initial_dispatch(); self.event('obstruction'); self.assertTrue(self.event('obstruction')[1]['duplicate'])
        self.assertEqual(sum(a['type']=='road_obstruction' for a in self.snapshot()['audit']),1)
    def test_stale_and_mismatched_obstruction(self):
        self.initial_dispatch()
        for key,val in [('incident_id','INC-OTHER'),('expected_version',99)]:
            b=copy.deepcopy(self.data['obstruction']);b[key]=val
            self.assertEqual(self.event('obstruction',b)[0],409)
        b=copy.deepcopy(self.data['obstruction']);b['payload']['resource_id']='AMB-05'
        self.assertEqual(self.event('obstruction',b)[0],409)
        self.assertEqual(self.snapshot()['phase'],'dispatched')
    def test_stale_callback_after_replacement(self):
        c1,c2=self.replacement()
        self.assertEqual(self.result(c1)[1]['code'],'STALE_COMMAND')
        self.assertEqual(self.delivery(c1)[0],409)
        self.assertEqual(self.snapshot()['assignments']['ASG-887']['status'],'superseded')
    def test_completion_duplicates_and_terminal_no_restart(self):
        c1,c2=self.replacement();self.event('completion');self.assertTrue(self.event('completion')[1]['duplicate'])
        self.assertEqual(self.result(c2)[0],409)
        self.assertTrue(self.event('intake')[1]['duplicate'])
        b=copy.deepcopy(self.data['intake']);b['event_id']='new-source-id'
        self.assertEqual(self.event('intake',b)[0],409)
        self.assertEqual(self.snapshot()['phase'],'resolved')
    def test_stale_completion_does_not_resolve(self):
        self.replacement();b=copy.deepcopy(self.data['completion']);b['payload']['assignment_ids']=['ASG-887','ASG-888']
        self.assertEqual(self.event('completion',b)[0],409)
        self.assertEqual(self.snapshot()['phase'],'dispatched')
    def test_durable_restart_receipts(self):
        c=self.initial_dispatch();self.f=Fixture(self.db)
        self.assertTrue(self.delivery(c)[1]['duplicate']);self.assertEqual(len(self.snapshot()['reports']),1)
    def test_claim_contention_and_expired_lease(self):
        self.event('intake');self.approve(1);c=self.claim(1)
        self.assertEqual(self.f.call('POST',PREFIX+'/automation/commands/'+c['command_id']+'/claim',{'worker_id':'other'},key='other')[0],409)
        with sqlite3.connect(self.db) as con:
            s=json.loads(con.execute('SELECT state FROM fixture').fetchone()[0]);s['commands'][c['command_id']]['lease_until']=0
            con.execute('UPDATE fixture SET state=?',(json.dumps(s),))
        self.assertEqual(self.delivery(c)[1]['code'],'LEASE_EXPIRED')
    def test_failed_delivery_recorded_and_not_polled_forever(self):
        self.event('intake');self.approve(1);c=self.claim(1)
        b=dict(event_id='failed-1',claim_token=c['claim_token'],outcome='failed',error_code='RETRY_EXHAUSTED')
        self.assertEqual(self.f.call('POST',PREFIX+'/automation/commands/'+c['command_id']+'/result',b,key='failed-1')[0],200)
        self.assertTrue(self.f.call('POST',PREFIX+'/automation/commands/'+c['command_id']+'/result',b,key='failed-1')[1]['duplicate'])
        self.assertEqual(self.f.call('GET',PREFIX+'/automation/commands')[1]['command_ids'],[])

    def test_final_callback_cannot_be_overwritten(self):
        c=self.initial_dispatch()
        b=dict(event_id='late-failure',claim_token=c['claim_token'],outcome='failed',error_code='OTHER')
        self.assertEqual(self.f.call('POST',PREFIX+'/automation/commands/'+c['command_id']+'/result',b,key='late-failure')[1]['code'],'RESULT_ALREADY_FINAL')
        self.assertEqual(self.snapshot()['commands'][c['command_id']]['state'],'accepted')

if __name__=='__main__':unittest.main(verbosity=2)
