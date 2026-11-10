// Executes the SAME embedded Code-node source against the local HTTP double.
// This is a fixture harness, NOT the n8n execution engine.
const fs=require('node:fs');
const path=require('node:path');
async function run(slug, input, options={}) {
  const w=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../workflows',slug+'.json')));
  const code=name=>w.nodes.find(n=>n.name===name).parameters.jsCode;
  const runId=options.executionId || 'harness-'+Date.now();
  if(!input && slug!=='dispatch')input=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../fixtures',slug+'.json')));
  let c=new Function('$json','$execution',code('Validate and lock fixture mode'))(input||{},{id:runId})[0].json;
  const evidence=[];
  for(let steps=0;steps<40;steps++){
    const before=c;
    let response;
    try {
      const raw=await fetch(c.base_url+c.path,{method:c.method,headers:{'X-Fixture-Actor':'automation','Content-Type':'application/json','Idempotency-Key':c.key},...(c.method==='POST'?{body:JSON.stringify(c.body)}:{}),signal:AbortSignal.timeout(5000),redirect:'error'});
      response={statusCode:raw.status,body:await raw.json(),headers:Object.fromEntries(raw.headers)};
    }catch{response={error:'NETWORK_ERROR'};}
    evidence.push({stage:before.stage,attempt:before.attempt,key:before.key,status:response.statusCode||0});
    c=new Function('$json','$',code('Check response and next stage'))(response,()=>({item:{json:before}}))[0].json;
    if(c.retry){if(!options.skipDelay)await new Promise(resolve=>setTimeout(resolve,c.delay_seconds*1000));continue;}
    if(c.more)continue;
    return {result:c.result||c.failure,failed:!!c.failed,evidence};
  }
  throw new Error('Harness hard limit reached');
}
if(require.main===module)run(process.argv[2]||'intake').then(r=>{console.log(JSON.stringify(r,null,2));if(r.failed)process.exitCode=1;}).catch(e=>{console.error(e.message);process.exitCode=1;});
module.exports={run};
