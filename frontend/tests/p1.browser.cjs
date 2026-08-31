// Real local HTTP + React browser acceptance. Run against an isolated P1_CLOSURE_DB.
// Uses the already available Playwright, no dependency download; all external browser traffic blocked.
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.P1_PLAYWRIGHT_MODULE || process.env.P0_PLAYWRIGHT_MODULE || 'playwright');
const runId = Date.now().toString();
const artifactDir = path.resolve(__dirname, `../../.codex_artifacts/p1/browser-${runId}`);
const root = 'http://127.0.0.1:5173';
const api = 'http://127.0.0.1:8000/api';
const title = `本地合成量子轨道验证师${runId}`;
const jobTitle = 'AI Agent开发工程师';
const results = [], errors = [], blocked = [];
let browser, context, page, candidate, auto, publication;
async function request(endpoint, body) {
  const response = await fetch(api + endpoint, body ? { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) } : {});
  const data = await response.json();
  assert.equal(response.status, 200, JSON.stringify(data));
  return data;
}
function evidence(id, extra={}) {return {job_id:`P1-${runId}-${id}`,original_title:title,standard_job_title:'',responsibilities:'维护合成测试服务 <script>window.p1Injected=true</script>',required_skills_raw:'Python RAG',company:'合成验收企业',source:'本地合成测试',published_at:'2026-08-30',url:'https://example.test/jobs/synthetic',...extra};}
async function postButton(label, ending) {
  const [response] = await Promise.all([page.waitForResponse(r => r.request().method()==='POST' && r.url().endsWith(ending)),page.getByRole('button',{name:label,exact:true}).click()]);
  const body=await response.json();assert.equal(response.status(),200,JSON.stringify(body));return body;
}
async function record(scene, detail) {
  await page.screenshot({path:path.join(artifactDir,`${scene}.png`),fullPage:true});
  results.push({scene,...detail,result:'PASS'});console.log(scene,JSON.stringify(detail));
}
async function review(label, ending='/actions') {
  const box=page.getByTestId('closure-detail');
  await box.getByLabel('审核人（可空）').fill('本地合成验收员');
  await box.getByLabel('审核说明 / 驳回理由').fill('已核验支持证据，确认缺失场景与加分项保持空值');
  await box.getByRole('checkbox').check();
  return postButton(label,ending);
}
before(async()=>{
  fs.mkdirSync(artifactDir,{recursive:true});
  browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-background-networking']});
  context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route('**/*',route=>{const u=new URL(route.request().url());if(['127.0.0.1','localhost'].includes(u.hostname))return route.continue();blocked.push(u.origin);return route.abort();});
  page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',error=>errors.push(error.message));
});
after(async()=>{
  await browser?.close();
  fs.writeFileSync(path.join(artifactDir,'results.json'),JSON.stringify({results,errors,blocked},null,2));
  console.log('ARTIFACTS',artifactDir);
  assert.deepEqual(errors,[]);
  assert.ok(blocked.every(origin=>origin==='https://fonts.googleapis.com'),'unexpected non-local request');
});

test('Scene 1: append real form evidence, discover and display five elements',async()=>{
  await page.goto(root+'/emerging');
  await page.getByText('追加JD证据（不覆盖原始数据）',{exact:true}).click();
  const row=evidence('c0');
  for(const [label,key] of [['新JD编号','job_id'],['原始岗位名称','original_title'],['JD职责原文','responsibilities'],['必备技能原文','required_skills_raw'],['企业','company'],['来源','source'],['原始招聘链接','url'],['真实发布时间','published_at']]) await page.getByLabel(label,{exact:true}).fill(row[key]);
  await postButton('保存JD证据','/evidence');
  for(let i=1;i<3;i++)await request('/closure/evidence',evidence(`c${i}`));
  const list=await postButton('运行新岗位发现','/discovery/run');
  candidate=list.find(c=>c.auto_definition.job_name===title);assert.ok(candidate);
  await page.locator('.closure-candidate-list button').filter({hasText:title}).click();
  auto=candidate.auto_definition;
  for(const field of ['岗位名称','核心职责','必备技能','加分技能','典型行业应用场景'])assert.ok(await page.getByTestId('closure-detail').getByRole('heading',{name:field,exact:true}).count());
  assert.equal(await page.evaluate(()=>window.p1Injected),undefined);
  await record('scene1',{id:candidate.id,version:candidate.version,definitionFields:Object.keys(auto)});
});

test('Scene 2: manual editor preserves automatic definition',async()=>{
  await page.getByRole('button',{name:'编辑五要素',exact:true}).click();
  await page.getByLabel('修订岗位名称').fill(title+'（人工修订）');
  candidate=await postButton('保存人工修改','/manual');
  assert.deepEqual(candidate.auto_definition,auto);
  assert.equal(candidate.manual_definition.job_name,title+'（人工修订）');
  await record('scene2',{version:candidate.version,autoPreserved:true});
});

test('Scene 3: approve then publish with persistent version and status',async()=>{
  candidate=await postButton('提交审核','/actions');assert.equal(candidate.status,'pending_review');
  candidate=await review('批准');assert.equal(candidate.status,'approved');
  candidate=await postButton('发布','/actions');assert.equal(candidate.status,'published');
  publication=await request(`/closure/candidate/${candidate.id}/published`);
  assert.equal(publication.profile_version,1);
  await page.reload();await page.locator('.closure-candidate-list button').filter({hasText:title}).click();
  await page.getByTestId('publication-status').filter({hasText:'V1'}).waitFor();
  await record('scene3',{status:candidate.status,contentVersion:candidate.version,publishedVersion:publication.profile_version});
});

test('Scene 4: new evidence creates version and visible LangGraph diff',async()=>{
  for(let i=3;i<7;i++)await request('/closure/evidence',evidence(`c${i}`,{required_skills_raw:'Python RAG LangGraph'}));
  const list=await postButton('运行新岗位发现','/discovery/run');
  const next=list.find(c=>c.id===candidate.id);assert.ok(next);assert.equal(next.previous_version,candidate.version);
  await page.getByRole('button',{name:'查看与前版差异',exact:true}).click();
  await page.getByTestId('version-diff').filter({hasText:'LangGraph'}).waitFor();
  assert.deepEqual(await request(`/closure/candidate/${candidate.id}/published`),publication);
  await record('scene4',{version:next.version,previousVersion:next.previous_version,publishedUnchanged:true,addedSkill:'LangGraph'});
});

test('Scene 5: new existing-role JDs yield change set without replacing profile',async()=>{
  for(let i=0;i<3;i++)await request('/closure/evidence',evidence(`p${i}`,{original_title:jobTitle,standard_job_title:jobTitle,required_skills_raw:'Python SQL FastAPI',published_at:'2026-08-31'}));
  await page.goto(root+'/evolution');
  const item=await postButton('重新计算能力更新','/profiles/run');
  assert.equal(item.status,'pending_review');assert.equal(item.change_set.status,'ready');
  assert.ok(item.change_set.added_skills.length+item.change_set.modified_skills.length+item.change_set.removed_skills.length>0);
  const published=await request(`/closure/profile/${encodeURIComponent(jobTitle)}/published`);
  assert.equal(published.profile_version,1);assert.equal(published.origin,'legacy_baseline');
  assert.ok(!published.evidence.some(row=>row.job_id.startsWith('P1-'+runId)));
  await record('scene5',{status:item.status,beforeCount:item.change_set.before_count,afterCount:item.change_set.after_count,added:item.change_set.added_skills.map(s=>s.skill_name),publishedVersion:published.profile_version});
});

test('Scene 6: approve and publish makes profile V2 visible in job analysis',async()=>{
  await review('批准');await postButton('发布','/actions');
  publication=await request(`/closure/profile/${encodeURIComponent(jobTitle)}/published`);
  assert.equal(publication.profile_version,2);
  await page.goto(root+'/jobs');await page.getByTestId('published-profile').waitFor();
  assert.match(await page.getByTestId('published-profile').textContent(),/V2/);
  await record('scene6',{publishedVersion:publication.profile_version,visibleInJobAnalysis:true});
});

test('Scene 7: rejecting a subsequent change preserves V2',async()=>{
  for(let i=0;i<3;i++)await request('/closure/evidence',evidence(`r${i}`,{original_title:jobTitle,standard_job_title:jobTitle,required_skills_raw:'Python Docker',published_at:'2026-09-01'}));
  await page.goto(root+'/evolution');const item=await postButton('重新计算能力更新','/profiles/run');
  assert.equal(item.status,'pending_review');const rejected=await review('驳回');assert.equal(rejected.status,'rejected');
  assert.deepEqual(await request(`/closure/profile/${encodeURIComponent(jobTitle)}/published`),publication);
  await record('scene7',{status:rejected.status,publishedVersion:2,unchanged:true});
});

test('Scene 8: insufficient after-window sample prevents approval and trend claims',async()=>{
  await request('/closure/evidence',evidence('small',{original_title:jobTitle,standard_job_title:jobTitle,required_skills_raw:'LangGraph',published_at:'2026-09-02'}));
  const item=await postButton('重新计算能力更新','/profiles/run');
  assert.equal(item.change_set.status,'insufficient_sample');
  assert.deepEqual(item.change_set.added_skills,[]);assert.deepEqual(item.change_set.removed_skills,[]);assert.deepEqual(item.change_set.modified_skills,[]);
  assert.equal(await page.getByRole('button',{name:'批准',exact:true}).isDisabled(),true);
  await page.getByTestId('change-set').filter({hasText:'样本不足'}).waitFor();
  await record('scene8',{status:item.change_set.status,before:item.change_set.before_count,after:item.change_set.after_count,approvalDisabled:true});
});
