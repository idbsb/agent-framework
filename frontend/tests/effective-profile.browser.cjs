// Actual local publisher + matching + graph APIs and React pages; no service mocks.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.P0_PLAYWRIGHT_MODULE||'playwright');
const root='http://127.0.0.1:5173',api='http://127.0.0.1:8000/api';
const run=Date.now().toString(),title='合成发布版本验证岗位'+run;
const artifacts=path.resolve(__dirname,`../../.codex_artifacts/p1/downstream-${run}`);
let browser,page,context,item,automatic;
const states=[],errors=[];
async function request(endpoint,body){const r=await fetch(api+endpoint,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();assert.equal(r.status,200,JSON.stringify(data));return data;}
async function action(action){item=await request(`/closure/candidate/${item.id}/actions`,{action,expected_version:item.version,expected_revision:item.revision,reviewer:'本地验收',note:'合成数据，已核验证据与缺口',acknowledge_gaps:true});}
async function edit(names){const definition=structuredClone(automatic);definition.required_skills=definition.required_skills.filter(s=>names.includes(s.skill_name));definition.preferred_skills=[];item=await request(`/closure/candidate/${item.id}/manual`,{definition,expected_version:item.version,expected_revision:item.revision});}
async function verify(label,version,names,requiredScore){
  const match=await request('/match',{job_title:title,resume:{skills_raw:'Python RAG',projects:'使用Python RAG开发服务'}});
  const graph=await request(`/graph/job/${encodeURIComponent(title)}`);
  const analysis=await request(`/job-analysis/${encodeURIComponent(title)}`);
  assert.equal(match.profile_version,version);assert.equal(graph.profile_version,version);assert.equal(analysis.profile_version,version);
  assert.equal(match.profile_source,'published_dynamic');assert.equal(graph.profile_source,'published_dynamic');
  assert.equal(match.profile_fingerprint,graph.profile_fingerprint);assert.equal(match.profile_fingerprint,analysis.profile_fingerprint);
  assert.deepEqual(graph.nodes.filter(n=>n.type==='skill').map(n=>n.name).sort(),names.toSorted());
  assert.equal(match.dimension_scores.required_skills,requiredScore);
  assert.deepEqual(match.missing_skills,version===1?[]:['LangGraph']);
  states.push({label,profile_version:version,profile_source:match.profile_source,required_score:requiredScore,match_score:match.match_score,missing:match.missing_skills,graph_skills:names,fingerprint:match.profile_fingerprint});
  return {match,graph};
}
before(async()=>{fs.mkdirSync(artifacts,{recursive:true});browser=await chromium.launch({channel:'msedge',headless:true});context=await browser.newContext({viewport:{width:1440,height:1000}});await context.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(e.message));});
after(async()=>{await browser?.close();fs.writeFileSync(path.join(artifacts,'results.json'),JSON.stringify({title,states,errors},null,2));console.log('ARTIFACTS',artifacts);assert.deepEqual(errors,[]);});

test('V1 published: Python and RAG drive matching and graph',async()=>{
  for(let i=0;i<3;i++)await request('/closure/evidence',{job_id:`SWITCH-${run}-${i}`,original_title:title,responsibilities:'维护合成验证服务',required_skills_raw:'Python RAG LangGraph Docker',published_at:'2026-08-31'});
  const list=await request('/closure/discovery/run',{});item=list.find(i=>i.auto_definition.job_name===title);assert.ok(item);automatic=structuredClone(item.auto_definition);
  await edit(['Python','RAG']);await action('submit');await action('approve');await action('publish');
  await verify('V1 published',1,['Python','RAG'],100);
  await page.goto(root+'/match');await page.getByLabel('目标岗位',{exact:true}).selectOption({label:title});await page.getByLabel('技能清单',{exact:true}).fill('Python RAG');
  await page.getByRole('button',{name:'开始匹配',exact:true}).click();await page.getByTestId('profile-source').filter({hasText:'V1'}).waitFor();
  await page.screenshot({path:path.join(artifacts,'v1-match.png')});
});
test('V2 pending and approved do not change V1',async()=>{
  await edit(['Python','RAG','LangGraph']);await action('submit');
  await verify('V2 pending',1,['Python','RAG'],100);
  await action('approve');await verify('V2 approved not published',1,['Python','RAG'],100);
});
test('Only publishing V2 switches both APIs and visible pages',async()=>{
  // Keep one live page open: a fresh request must observe publication without server restart.
  await action('publish');await verify('V2 published',2,['Python','RAG','LangGraph'],66.67);
  await page.getByRole('button',{name:'开始匹配',exact:true}).click();await page.getByTestId('profile-source').filter({hasText:'V2'}).waitFor();
  await page.screenshot({path:path.join(artifacts,'v2-match.png')});
  await page.goto(root+'/graph');await page.getByRole('combobox').selectOption({label:title});
  await page.getByTestId('profile-source').filter({hasText:'V2'}).waitFor();await page.locator('canvas').first().waitFor();
  await page.screenshot({path:path.join(artifacts,'v2-graph.png')});
});
test('V3 pending and rejected leave V2 downstream unchanged',async()=>{
  await edit(['Python','RAG','LangGraph','Docker']);await action('submit');
  const pending=await verify('V3 pending',2,['Python','RAG','LangGraph'],66.67);
  await action('reject');const rejected=await verify('V3 rejected',2,['Python','RAG','LangGraph'],66.67);
  assert.deepEqual(pending,rejected);
});
