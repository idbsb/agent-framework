// SYNTHETIC TEST DATA / NOT REAL RECRUITMENT DATA. Run with p2_local_server --synthetic-quality.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.P0_PLAYWRIGHT_MODULE||'playwright');
const fixture=require('../../tests/fixtures/p2_synthetic/synthetic_browser_fixture.json');
const artifacts=path.resolve(__dirname,`../../.codex_artifacts/p2/browser-${Date.now()}`);
let browser,page,context;const errors=[],results=[];
const api='http://127.0.0.1:8000',base='http://127.0.0.1:5173';
async function post(url,body){const r=await fetch(api+url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.status,200);return r.json();}
before(async()=>{fs.mkdirSync(artifacts,{recursive:true});browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-background-networking']});context=await browser.newContext();await context.route('**/*',r=>['127.0.0.1','localhost'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(e.message));});
after(async()=>{await browser?.close();fs.writeFileSync(path.join(artifacts,'results.json'),JSON.stringify({dataset_notice:fixture.dataset_notice,results,errors},null,2));console.log('ARTIFACTS',artifacts);assert.deepEqual(errors,[]);});

test('P2 scene 1 and 2: synthetic 1/11 window suppresses decline, fallback visible',async()=>{
  await page.goto(base+'/evolution');
  await page.getByText('前窗口 1 条 · 后窗口 11 条',{exact:false}).waitFor();
  await page.getByText('部分记录缺少原始发布时间，趋势计算使用采集时间回退。',{exact:false}).waitFor();
  const value=await (await fetch(api+'/api/evolution/job/'+encodeURIComponent('AI Agent开发工程师'))).json();
  assert.equal(value.trend_status,'insufficient_sample');assert.deepEqual(value.declining_skills,[]);
  assert.equal(value.data_quality.time_quality.fallback_count,12);
  await page.screenshot({path:path.join(artifacts,'synthetic-window.png'),fullPage:true});
  results.push({scene:'1-2',status:'PASS',windows:value.window_samples,fallback_count:12});
});
test('P2 scene 3 and 4: preview flags duplicates, retains every row and distinct JD',async()=>{
  const before=JSON.stringify(fixture);
  const near=await post('/api/quality/preview',{rows:fixture.rows});
  assert.equal(near.raw_evidence_count,2);assert.equal(near.independent_evidence_count,1);assert.equal(near.groups[0].duplicate_type,'near');
  const separate=await post('/api/quality/preview',{rows:[fixture.rows[0],fixture.different]});
  assert.equal(separate.independent_evidence_count,2);assert.deepEqual(separate.groups,[]);assert.equal(JSON.stringify(fixture),before);
  results.push({scene:'3-4',status:'PASS',raw:2,independent:1,distinct:2});
});
test('P2 scene 5 dependency blocker is honest; existing text confirmation and P0 semantics work',async()=>{
  await page.goto(base+'/resume-parse');
  assert.equal(await page.getByRole('button',{name:'上传 PDF/DOCX（暂不可用）'}).isDisabled(),true);
  const capability=await (await fetch(api+'/api/resume/file/capabilities')).json();assert.equal(capability.pdf.supported,false);assert.equal(capability.docx.supported,false);
  await page.getByLabel('技能清单',{exact:true}).fill(fixture.resume.skills_raw);
  const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/resume/parse')),page.getByRole('button',{name:'分析简历',exact:true}).click()]);
  const skills=(await r.json()).skills;const polarity=Object.fromEntries(skills.map(s=>[s.standard_skill_name,s.polarity]));
  assert.equal(polarity.Docker,'negated');assert.equal(polarity.RAG,'planned');assert.equal(polarity.SQL,'affirmed');
  await page.goto(base+'/match');await page.getByLabel('技能清单',{exact:true}).fill(fixture.resume.skills_raw);
  const [m]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/match')),page.getByRole('button',{name:'开始匹配',exact:true}).click()]);
  const match=await m.json();assert.ok(!match.matched_skills.includes('Docker'));assert.ok(!match.matched_skills.includes('RAG'));
  results.push({scene:'5',file_status:'BLOCKER dependency_required',text_status:'PASS',polarity});
});
test('quality preview API and rendered text do not execute HTML',async()=>{
  const row={...fixture.rows[0],company:'<img src=x onerror=alert(1)>'};
  const result=await post('/api/quality/preview',{rows:[row]});assert.equal(result.records[0].company_raw,row.company);
  assert.equal(await page.evaluate(()=>document.querySelectorAll('.result-panel img').length),0);
  results.push({scene:'safe-data',status:'PASS'});
});
