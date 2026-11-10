const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const logic = fs.readFileSync(path.join(__dirname, 'workflow_logic.js'), 'utf8').replace(/if \(typeof module[^\n]+/, '');
const envelope = (type, id, payload, extra = {}) => ({schema_version: 1, event_id: 'demo-run-01-' + id, event_type: type, occurred_at: '2026-09-20T10:00:00Z', source: 'synthetic-demo', correlation_id: 'demo-run-01', ...extra, payload});
const fixtures = {
  intake: envelope('report_received', 'report-01', {source_report_id: 'synthetic-report-01', channel: 'synthetic', originalText: 'Water entering Krishna Apartments Block C. My grandmother cannot walk.', originalLanguage: 'en', receivedAt: '2026-09-20T10:00:00Z'}),
  obstruction: envelope('road_obstruction', 'roadblock-01', {assignment_id: 'ASG-887', resource_id: 'AMB-02', previous_eta_minutes: 6, eta_minutes: 24, reason_code: 'road_blocked'}, {incident_id: 'INC-1042', expected_version: 1}),
  completion: envelope('response_completed', 'complete-01', {assignment_ids: ['ASG-888', 'ASG-889'], evidence: 'simulated responder completion'}, {incident_id: 'INC-1042', expected_version: 2}),
};
for (const [name, body] of Object.entries(fixtures)) fs.writeFileSync(path.join(root, 'fixtures', name + '.json'), JSON.stringify(body, null, 2) + '\n');
const configs = [ ['intake', 'report_received', '01 Intake'], ['dispatch', 'dispatch', '02 Authorized dispatch and replacement'], ['obstruction', 'road_obstruction', '03 Road obstruction'], ['completion', 'response_completed', '04 Completion'] ];
for (const [slug, kind, label] of configs) {
  const nodes = [], connections = {};
  const node = (name, type, parameters, x, y, extra = {}) => {nodes.push({id: crypto.createHash('sha256').update(slug+name).digest('hex').slice(0,32), name, type: 'n8n-nodes-base.'+type, typeVersion: {httpRequest:4.2, if:2.2, code:2, webhook:2, wait:1.1}[type] || 1, position:[x,y], parameters, ...extra});};
  const edge = (a,b,index=0) => {connections[a] ||= {main:[]}; connections[a].main[index] ||= []; connections[a].main[index].push({node:b,type:'main',index:0});};
  const code = (name,js,x,y) => node(name,'code',{jsCode:js},x,y);
  const ifNode = (name,field,x,y) => node(name,'if',{conditions:{options:{caseSensitive:true,leftValue:'',typeValidation:'strict',version:2},conditions:[{id:field,leftValue:'={{ $json.'+field+' }}',rightValue:'',operator:{type:'boolean',operation:'true',singleValue:true}}],combinator:'and'},options:{}},x,y);
  node('Manual trigger','manualTrigger',{},0,0);
  if (kind !== 'dispatch') {
    code('Synthetic example', 'return [{json:'+JSON.stringify(fixtures[slug])+'}];',200,0);
    edge('Manual trigger','Synthetic example'); edge('Synthetic example','Validate and lock fixture mode');
    node('Synthetic webhook','webhook',{httpMethod:'POST',path:'reliefmesh-fixture-'+slug,responseMode:'lastNode',options:{}},0,240,{webhookId:'reliefmesh-fixture-'+slug});
    edge('Synthetic webhook','Validate and lock fixture mode');
  } else edge('Manual trigger','Validate and lock fixture mode');
  code('Validate and lock fixture mode', logic+'\nreturn [{json:prepare($json.body ?? $json, '+JSON.stringify(kind)+', $execution.id)}];',420,0);
  code('Request context','return $input.all();',650,0);
  node('Fixture HTTP operation','httpRequest',{method:'={{ $json.method }}',url:'={{ $json.base_url + $json.path }}',sendHeaders:true,headerParameters:{parameters:[{name:'X-Fixture-Actor',value:'automation'},{name:'Idempotency-Key',value:'={{ $json.key }}'}]},sendBody:true,specifyBody:'json',jsonBody:'={{ JSON.stringify($json.body) }}',options:{timeout:5000,redirect:{redirect:{followRedirects:false}},response:{response:{fullResponse:true,neverError:true,responseFormat:'json'}}}},870,0,{onError:'continueRegularOutput',retryOnFail:false});
  code('Check response and next stage',logic+"\nreturn [{json:advance($('Request context').item.json, $json)}];",1090,0);
  ifNode('Retry transient only','retry',1320,0);
  node('Bounded retry delay','wait',{resume:'timeInterval',amount:'={{ $json.delay_seconds }}',unit:'seconds'},1320,-230,{webhookId:'reliefmesh-fixture-wait-'+slug});
  ifNode('Next authorized step','more',1550,100);
  ifNode('Failed','failed',1770,170);
  node('Explicit failure','stopAndError',{errorMessage:'={{ JSON.stringify($json.failure) }}'},1990,50);
  code('Result or WAIT FOR HUMAN',"return [{json:$json.result || {status:'FAILED', failure:$json.failure}}];",1990,280);
  node('Read me','stickyNote',{content:'# FIXTURE ONLY — live disabled\n'+(kind==='dispatch' ? 'One poll → claim → validate lease/version → SIMULATED delivery → result.\nNo command: WAIT FOR HUMAN, then stop. Run again AFTER a separate coordinator approval. Same graph handles gate #2. Continuing responders are excluded.' : 'Synthetic source → validate originals/IDs → local backend contract double → receipt.\nThe test double owns state. No AI call or approval in n8n.')+'\n\nHTTP steps: max 4 attempts, waits 1/3/10s; 4xx stop (except 429). Failure is saved in execution data. Nothing contacts a real responder.',height:280,width:560},480,380);
  edge('Validate and lock fixture mode','Request context');edge('Request context','Fixture HTTP operation');edge('Fixture HTTP operation','Check response and next stage');edge('Check response and next stage','Retry transient only');edge('Retry transient only','Bounded retry delay',0);edge('Bounded retry delay','Request context');edge('Retry transient only','Next authorized step',1);edge('Next authorized step','Request context',0);edge('Next authorized step','Failed',1);edge('Failed','Explicit failure',0);edge('Failed','Result or WAIT FOR HUMAN',1);
  const workflow={id:'ReliefMeshFixture'+slug,name:'ReliefMesh FIXTURE '+label,active:false,nodes,connections,settings:{executionOrder:'v1',saveDataErrorExecution:'all',saveDataSuccessExecution:'all',executionTimeout:600},pinData:{},versionId:crypto.randomUUID(),tags:[]};
  // Deterministic exports: version changes only when content changes.
  workflow.versionId = crypto.createHash('md5').update(JSON.stringify(nodes)).digest('hex').replace(/(.{8})(.{4})(.{4})(.{4})(.{12})/,'$1-$2-$3-$4-$5');
  fs.writeFileSync(path.join(root,'workflows',slug+'.json'),JSON.stringify(workflow,null,2)+'\n');
}
console.log('Built four inactive FIXTURE workflows. Live execution is disabled.');
