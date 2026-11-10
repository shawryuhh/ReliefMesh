"""Disposable actual-n8n CLI verification, always against the LOCAL test double.
Test driver supplies simulated coordinator decisions BETWEEN executions.
No workflow contains or calls an approval endpoint.
"""
import argparse
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from fixture_server import Fixture, PREFIX

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--n8n-bin', required=True, help='Absolute n8n CLI executable path (n8n.cmd on Windows)')
parser.add_argument('--profile', required=True, help='Dedicated n8n user folder, never an existing production profile')
args=parser.parse_args()
env={**os.environ,'N8N_USER_FOLDER':str(Path(args.profile).resolve()),'N8N_DIAGNOSTICS_ENABLED':'false'}
logs=ROOT/'.runtime'/'verification'
logs.mkdir(parents=True,exist_ok=True)
evidence=[]

def stored_execution(previous_id, slug):
    # n8n may persist an error execution without flushing rawOutput on CLI exit.
    # Read the actual engine's SQLite record, not a simulated replacement result.
    with sqlite3.connect(Path(args.profile)/'.n8n'/'database.sqlite') as con:
        row=con.execute('SELECT e.status,d.data,e.id,e.workflowId FROM execution_entity e JOIN execution_data d ON e.id=d.executionId ORDER BY CAST(e.id AS INTEGER) DESC LIMIT 1').fetchone()
    assert int(row[2]) > previous_id and row[3]=='ReliefMeshFixture'+slug, 'No new persisted execution for this invocation'
    table=json.loads(row[1]); cache={}
    def entry(i):
        if i in cache: return cache[i]
        v=table[i]
        if isinstance(v,dict):
            target={};cache[i]=target
            target.update({k:entry(int(x)) if isinstance(x,str) else x for k,x in v.items()})
        elif isinstance(v,list):
            target=[];cache[i]=target
            target.extend(entry(int(x)) if isinstance(x,str) else x for x in v)
        else: target=v;cache[i]=target
        return target
    return {'status':row[0],'data':entry(0)}

def execute(slug, label, expected=None, fail=False):
    log=logs/(label+'.log')
    with sqlite3.connect(Path(args.profile)/'.n8n'/'database.sqlite') as con:
        previous_id=int(con.execute('SELECT COALESCE(MAX(CAST(id AS INTEGER)),0) FROM execution_entity').fetchone()[0])
    with log.open('w') as out:
        result=subprocess.run([args.n8n_bin,'execute','--id=ReliefMeshFixture'+slug,'--rawOutput'],env=env,stdout=out,stderr=subprocess.STDOUT,timeout=150)
    raw=log.read_text()
    start=raw.find('{\n')
    d=json.JSONDecoder().raw_decode(raw[start:])[0] if start>=0 else stored_execution(previous_id, slug)
    run=d['data']['resultData']['runData']
    name='Explicit failure' if fail else 'Result or WAIT FOR HUMAN'
    assert name in run, raw[-1500:]
    if fail:
        assert d['status']=='error'
        value=run['Check response and next stage'][-1]['data']['main'][0][0]['json']['failure']
    else:
        assert result.returncode==0 and d['status']=='success',raw[-1500:]
        value=run[name][-1]['data']['main'][0][0]['json']
    if expected:
        assert value.get('status',value.get('phase',value.get('error_code')))==expected,value
    stages=[]
    for op in run['Request context']:
        c=op['data']['main'][0][0]['json']
        stages.append({k:c[k] for k in ['stage','attempt','key']})
    evidence.append({'case':label,'workflow':slug,'execution_id':run['Validate and lock fixture mode'][0]['data']['main'][0][0]['json']['execution_id'],'engine_status':d['status'],'result':value,'requests':stages})
    print(label+': '+d['status']+' '+str(value),flush=True)
    return value

with tempfile.TemporaryDirectory(prefix='reliefmesh-n8n-verification-') as td:
    db=Path(td)/'fixture.sqlite'
    server=subprocess.Popen([sys.executable,str(ROOT/'scripts'/'fixture_server.py'),'--db',str(db)],stdout=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                req=urllib.request.Request('http://127.0.0.1:8094'+PREFIX+'/snapshot',headers={'X-Fixture-Actor':'automation'})
                with urllib.request.urlopen(req,timeout=1): break
            except OSError: time.sleep(.1)
        else: raise RuntimeError('Fixture server did not start')
        f=Fixture(db)
        with (logs/'import.log').open('w') as out:
            subprocess.run([args.n8n_bin,'import:workflow','--separate','--input='+str(ROOT/'workflows')],env=env,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=90)
        f.call('POST','/fixture/control/faults',{'path':PREFIX+'/automation/events','statuses':[429,503]},'fixture-coordinator')
        execute('intake','01-intake-transient-retry','awaiting_approval')
        execute('intake','02-intake-duplicate','awaiting_approval')
        execute('dispatch','03-gate-one-wait','WAIT_FOR_HUMAN')
        assert not f.call('GET',PREFIX+'/snapshot')[1]['deliveries']
        assert f.call('POST','/fixture/control/approve',{'version':1,'human_confirmed':True},'fixture-coordinator')[0]==200
        execute('dispatch','04-initial-dispatch','SIMULATED_DELIVERY_RECORDED')
        s=f.call('GET',PREFIX+'/snapshot')[1];c1=s['commands']['fixture-INC-1042-v1']
        body={k:c1[k] for k in ['command_id','claim_token','incident_id','recommendation_version','new_assignments']}
        assert f.call('POST','/fixture/receiver/deliver',body,key=c1['command_id'])[1]['duplicate']
        execute('dispatch','05-no-duplicate-command','NO_AUTHORIZED_COMMAND')
        execute('obstruction','06-obstruction','awaiting_replacement')
        execute('obstruction','07-obstruction-duplicate','awaiting_replacement')
        execute('dispatch','08-gate-two-wait','WAIT_FOR_HUMAN')
        assert len(f.call('GET',PREFIX+'/snapshot')[1]['deliveries'])==1
        assert f.call('POST','/fixture/control/approve',{'version':2,'human_confirmed':True},'fixture-coordinator')[0]==200
        execute('dispatch','09-replacement-dispatch','SIMULATED_DELIVERY_RECORDED')
        s=f.call('GET',PREFIX+'/snapshot')[1]
        assert s['commands']['fixture-INC-1042-v2']['new_assignments']==[{'assignment_id':'ASG-889','resource_id':'AMB-05'}]
        assert f.call('POST','/fixture/receiver/deliver',body,key=c1['command_id'])[0]==409
        execute('completion','10-completion','resolved')
        execute('completion','11-completion-duplicate','resolved')
        execute('dispatch','12-terminal-no-restart','NO_AUTHORIZED_COMMAND')
        f.call('POST','/fixture/control/faults',{'path':PREFIX+'/automation/events','statuses':[503]*4},'fixture-coordinator')
        execute('intake','13-retry-exhaustion','RETRY_EXHAUSTED',fail=True)
        f.call('POST','/fixture/control/faults',{'path':PREFIX+'/automation/events','statuses':[403]},'fixture-coordinator')
        execute('intake','14-forbidden-no-retry','INJECTED_REJECTION',fail=True)
        s=f.call('GET',PREFIX+'/snapshot')[1]
        assert s['phase']=='resolved' and len(s['reports'])==1 and len(s['deliveries'])==2
        assert len(s['approvals'])==2 and set(s['resources'].values())=={'available'}
        for version,label in [(1,'initial'),(2,'replacement')]:
            c=s['commands'][f'fixture-INC-1042-v{version}']
            example={k:v for k,v in c.items() if k not in ['claim_token','lease_until','lease_expires_at','created_at']}
            example.update(state='pending',claim_attempts=0,created_at='2026-09-20T10:01:00Z')
            (ROOT/'fixtures'/(label+'-command.json')).write_text(json.dumps({'fixture_only':True,'note':'Illustrative backend-issued command; not authorization to deliver. Claim it from the test double.', 'command':example},indent=2)+'\n')
        proof={k:s[k] for k in ['fixture','phase','revision','reports','resources','assignments','approvals','deliveries','audit','failures']}
        report={'verification':'ACTUAL_N8N_WITH_LOCAL_CONTRACT_DOUBLE','n8n_version':'2.39.8','real_backend_integration':False,'executions':evidence,'final_state':proof}
        (ROOT/'fixtures'/'verification-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: actual n8n executions recorded; real backend integration NOT RUN.',flush=True)
    finally:
        server.terminate();server.wait(timeout=5)
