const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {prepare,advance,normalizeEvent,commandCheck} = require('../scripts/workflow_logic');
const root=path.resolve(__dirname,'..');
const fixture=n=>JSON.parse(fs.readFileSync(path.join(root,'fixtures',n+'.json')));
const initial=()=>prepare(fixture('intake'),'report_received','test-execution');
const ok=b=>({statusCode:200,body:{...b,fixture:true}});
test('all exports parse, have unique nodes, valid connections, explicit failure, no credentials or approval endpoints',()=>{
  for(const file of fs.readdirSync(path.join(root,'workflows'))){
    const w=JSON.parse(fs.readFileSync(path.join(root,'workflows',file)));
    assert.equal(w.active,false);
    const names=new Set(w.nodes.map(n=>n.name));assert.equal(names.size,w.nodes.length);
    assert.equal(new Set(w.nodes.map(n=>n.id)).size,w.nodes.length);
    for(const [name,connection] of Object.entries(w.connections)){
      assert(names.has(name));for(const output of connection.main)for(const e of output || [])assert(names.has(e.node));
    }
    const reached=new Set(),visit=n=>{if(reached.has(n))return;reached.add(n);for(const output of w.connections[n]?.main||[])for(const e of output||[])visit(e.node);};
    visit('Manual trigger');assert(reached.has('Explicit failure'));assert(reached.has('Result or WAIT FOR HUMAN'));
    for(const n of w.nodes){assert(!n.credentials);if(n.type.endsWith('.code'))new Function(n.parameters.jsCode);}
    assert(!JSON.stringify(w).includes('/fixture/control/approve'));
    assert(!JSON.stringify(w).includes('/replanning'));
  }
});
test('original text and language preserved byte for byte; timestamp normalized',()=>{
  const b=fixture('intake');b.payload.originalText='  नमस्ते\nमदद  ';b.payload.originalLanguage='hi';b.occurred_at='2026-09-20T15:30:00+05:30';
  const c=normalizeEvent(b,'report_received');assert.equal(c.payload.originalText,b.payload.originalText);assert.equal(c.payload.originalLanguage,'hi');assert.equal(c.occurred_at,'2026-09-20T10:00:00.000Z');
});
test('live mode and invalid input blocked before HTTP',()=>{
  assert.throws(()=>prepare(fixture('intake'),'report_received','1','live'),/LIVE_DISABLED/);
  for(const [key,value] of [['event_id',''],['source','real'],['occurred_at','yesterday'],['event_type','approved']]){const b=fixture('intake');b[key]=value;assert.throws(()=>prepare(b,'report_received','1'));}
});
test('four attempts only; stable body/key with 1,3,10 seconds',()=>{
  let c=initial();const body=JSON.stringify(c.body),key=c.key;
  for(const seconds of [1,3,10]){c=advance(c,{statusCode:503});assert.equal(c.delay_seconds,seconds);assert.equal(c.key,key);assert.equal(JSON.stringify(c.body),body);}
  c=advance(c,{statusCode:503});assert.equal(c.stage,'failure_log');assert.equal(c.failure.error_code,'RETRY_EXHAUSTED');assert.equal(c.failure.attempts,4);
  c=advance(c,ok({recorded:true}));assert.equal(c.failed,true);assert.equal(c.more,false);
});
test('network errors and 429 retry, Retry-After honored within cap',()=>{
  assert.equal(advance(initial(),{error:'ECONNRESET'}).retry,true);
  assert.equal(advance(initial(),{statusCode:429,headers:{'retry-after':'5'}}).delay_seconds,5);
  assert.equal(advance(initial(),{statusCode:429,headers:{'retry-after':'120'}}).failure.error_code,'RETRY_AFTER_REQUIRES_OPERATOR');
});
test('401 403 404 409 422 fail on first attempt',()=>{for(const status of [401,403,404,409,422]){const c=advance(initial(),{statusCode:status,body:{code:'REJECTED'}});assert.equal(c.stage,'failure_log');assert.equal(c.failure.attempts,1);assert.equal(c.retry,false);}});
test('wrong acknowledgement never counted as success',()=>{assert.equal(advance(initial(),ok({accepted:true,event_id:'wrong',incident_id:'INC-1042'})).stage,'failure_log');});
test('both gates yield WAIT without delivery',()=>{for(const phase of ['awaiting_approval','awaiting_replacement']){const c=advance(prepare({},'dispatch','1'),ok({command_ids:[],phase}));assert.equal(c.result.status,'WAIT_FOR_HUMAN');assert.equal(c.more,false);}});
test('unapproved recommendation cannot pass as command',()=>{assert.throws(()=>commandCheck({command_id:'fake',incident_id:'INC-1042',state:'pending',approval_required:false},Date.now()),/UNAUTHORIZED/);});
test('failure sink unavailable still stops after bounded retries',()=>{let c=advance(initial(),{statusCode:403});for(let i=0;i<4;i++)c=advance(c,{statusCode:503});assert.equal(c.failed,true);assert.equal(c.more,false);assert.equal(c.failure.error_code,'HTTP_403');});
function claimed(){return {command_id:'fixture-INC-1042-v2',incident_id:'INC-1042',recommendation_version:2,action:'redispatch',authorization:{approval_id:'fixture-approval-2',actor:'fixture-coordinator',version:2},approved_resource_ids:['AMB-05','RESCUE-01'],new_assignments:[{assignment_id:'ASG-889',resource_id:'AMB-05'}],continuing_assignment_ids:['ASG-888'],superseded_assignment_ids:['ASG-887'],state:'claimed',claim_attempts:1,claim_token:'fixture-token',lease_expires_at:new Date(Date.now()+180000).toISOString(),created_at:'2026-09-20T10:01:00Z'};}
test('expired, continuing, superseded, duplicate and unapproved assignments blocked',()=>{
  for(const mutate of [c=>c.lease_expires_at='2020-01-01T00:00:00Z',c=>c.new_assignments[0].assignment_id='ASG-888',c=>c.new_assignments[0].assignment_id='ASG-887',c=>c.new_assignments.push({...c.new_assignments[0]}),c=>c.new_assignments[0].resource_id='AMB-99',c=>c.authorization.version=1]){
    const c=claimed();mutate(c);assert.throws(()=>commandCheck(c,Date.now()));
  }
});
test('claim and revalidation mismatches fail before receiver',()=>{
  let c=prepare({},'dispatch','test');c=advance(c,ok({command_ids:['fixture-INC-1042-v2']}));
  const wrong=claimed();wrong.command_id='different';assert.equal(advance(c,ok({command:wrong})).failure.error_code,'CLAIM_ID_MISMATCH');
  c=advance(c,ok({command:claimed()}));const stale=structuredClone(c.command);stale.authorization.actor='different';
  assert.equal(advance(c,ok({valid:true,command:stale})).failure.error_code,'REVALIDATION_MISMATCH');
});
test('replacement delivers only delta; callback retry reuses body and does not redeliver',()=>{
  let c=prepare({},'dispatch','test');c=advance(c,ok({command_ids:['fixture-INC-1042-v2']}));c=advance(c,ok({command:claimed()}));c=advance(c,ok({valid:true,command:c.command}));
  assert.equal(c.stage,'delivery');assert.deepEqual(c.body.new_assignments,[{assignment_id:'ASG-889',resource_id:'AMB-05'}]);
  c=advance(c,ok({simulated:true,command_id:c.command.command_id,delivery_reference:'simulated:receipt'}));const body=JSON.stringify(c.body),key=c.key;
  c=advance(c,{statusCode:503});assert.equal(c.stage,'callback');assert.equal(c.key,key);assert.equal(JSON.stringify(c.body),body);
  c=advance(c,ok({accepted:true,command_id:c.command.command_id}));assert.equal(c.result.status,'SIMULATED_DELIVERY_RECORDED');
});
test('delivery exhaustion reports failure and cannot continue to delivery again',()=>{
  let c=prepare({},'dispatch','test');c=advance(c,ok({command_ids:['fixture-INC-1042-v2']}));c=advance(c,ok({command:claimed()}));c=advance(c,ok({valid:true,command:c.command}));
  for(let i=0;i<4;i++)c=advance(c,{statusCode:503});assert.equal(c.stage,'failed_callback');assert.equal(c.body.outcome,'failed');
  c=advance(c,ok({accepted:true}));assert.equal(c.stage,'failure_log');c=advance(c,ok({recorded:true}));assert.equal(c.failed,true);
});
