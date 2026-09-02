// Local production-mode rehearsal only. Never points at or writes to a deployed service.
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const https=require('node:https');
const {spawn,spawnSync}=require('node:child_process');
const {randomBytes}=require('node:crypto');
const {once}=require('node:events');
const {chromium}=require(process.env.P1_PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../..'),front=path.join(root,'frontend');
const api='http://127.0.0.1:8011',ui='https://p1-ui.test:5443';
const artifacts=path.join(root,'.codex_artifacts/p1-production');
const storage=fs.mkdtempSync(path.join(os.tmpdir(),'p1-production-'));
const secret=randomBytes(32).toString('hex');
const title=`P1合成生产流程验证员${Date.now()}`;
const states=[],pageErrors=[];
let server,backend,browser,page,item,automatic,firstEvidence,publicationFingerprint;
function command(exe,args,options={}) {
  const r=spawnSync(exe,args,{cwd:front,encoding:'utf8',...options});
  assert.equal(r.status,0,`${exe}: ${r.error||r.stderr||r.stdout}`);
}
async function startBackend(initialize) {
  const log=fs.openSync(path.join(artifacts,'backend.log'),'a');
  backend=spawn(process.env.P1_TEST_PYTHON||'python',['-m','uvicorn','src.api.app:app','--host','127.0.0.1','--port','8011','--workers','1'],{
    cwd:root,windowsHide:true,stdio:['ignore',log,log],env:{...process.env,RENDER:'false',P1_ENV:'production',
      P1_CLOSURE_WRITES:'1',P1_INITIALIZE_DB:initialize?'1':'0',P1_STORAGE_DIR:storage,
      P1_CLOSURE_DB:path.join(storage,'closure.sqlite3'),P1_ADMIN_TOKEN:secret,P1_ADMIN_NAME:'synthetic-admin',CORS_ORIGINS:ui}});
  fs.closeSync(log);
  for(let i=0;i<100;i++) {
    if(backend.exitCode!==null)throw new Error('Backend failed; see backend.log');
    try {if((await fetch(api+'/api/health/ready')).ok)return;}catch{}
    await new Promise(r=>setTimeout(r,200));
  }
  throw new Error('Backend readiness timed out');
}
async function stopBackend() {
  if(backend && backend.exitCode===null){const stopped=once(backend,'exit');backend.kill();await stopped;}
}
async function request(endpoint,body,authorized=true) {
  const response=await fetch(api+'/api'+endpoint,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',Origin:ui,
    ...(body&&authorized?{Authorization:`Bearer ${secret}`}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const data=await response.json();assert.equal(response.status,200,JSON.stringify(data));
  assert.equal(response.headers.get('cache-control'),'no-store');return data;
}
async function clickPost(label,suffix) {
  const [response]=await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith(suffix)),
    page.getByRole('button',{name:label,exact:true}).click()]);
  const data=await response.json();assert.equal(response.status(),200,JSON.stringify(data));return data;
}
async function action(name) {
  item=await request(`/closure/candidate/${item.id}/actions`,{action:name,expected_version:item.version,expected_revision:item.revision,
    reviewer:'untrusted-browser-actor',note:'合成测试证据已核验',acknowledge_gaps:true});
}
async function edit(names) {
  const definition=structuredClone(automatic);
  definition.required_skills=definition.required_skills.filter(s=>names.includes(s.skill_name));definition.preferred_skills=[];
  item=await request(`/closure/candidate/${item.id}/manual`,{definition,expected_version:item.version,expected_revision:item.revision});
}
async function verify(label,version,names) {
  const match=await request('/match',{job_title:title,resume:{skills_raw:'Python RAG',projects:'使用Python RAG开发服务'}});
  const graph=await request(`/graph/job/${encodeURIComponent(title)}`);
  const analysis=await request(`/job-analysis/${encodeURIComponent(title)}`);
  for(const value of [match,graph,analysis]){assert.equal(value.profile_source,'published_dynamic');assert.equal(value.profile_version,version);}
  assert.equal(match.profile_fingerprint,graph.profile_fingerprint);assert.equal(match.profile_fingerprint,analysis.profile_fingerprint);
  assert.deepEqual(graph.nodes.filter(n=>n.type==='skill').map(n=>n.name).sort(),names.toSorted());
  assert.equal(match.dimension_scores.required_skills,version===1?100:66.67);
  states.push({label,version,fingerprint:match.profile_fingerprint,skills:names,requiredScore:match.dimension_scores.required_skills});
  publicationFingerprint=match.profile_fingerprint;
}
before(async()=>{
  fs.mkdirSync(artifacts,{recursive:true});
  // Builds real Vite assets with a separate API origin, no development proxy.
  command(process.execPath,['node_modules/vite/bin/vite.js','build','--config','vite.config.ts'],{env:{...process.env,VERCEL:'0',VITE_API_BASE_URL:api}});
  const built=[];const visit=dir=>fs.readdirSync(dir,{withFileTypes:true}).forEach(entry=>entry.isDirectory()?visit(path.join(dir,entry.name)):built.push(path.join(dir,entry.name)));visit(path.join(front,'dist'));
  assert.ok(built.every(file=>!fs.readFileSync(file).includes(secret)),'runtime administrator token leaked into frontend build');
  const key=path.join(storage,'test.key'),cert=path.join(storage,'test.crt'),config=path.join(storage,'openssl.cnf');
  fs.writeFileSync(config,'[req]\ndistinguished_name=reqdn\n[reqdn]\n');
  command(process.env.P1_OPENSSL||'openssl',['req','-config',config,'-x509','-newkey','rsa:2048','-nodes','-keyout',key,'-out',cert,
    '-days','1','-subj','/CN=localhost']);
  server=https.createServer({key:fs.readFileSync(key),cert:fs.readFileSync(cert)},(req,res)=>{
    const pathname=decodeURIComponent(new URL(req.url,ui).pathname);
    const relative=pathname.startsWith('/assets/')?pathname.slice(1):'index.html';
    const target=path.resolve(front,'dist',relative);
    if(!target.startsWith(path.resolve(front,'dist')+path.sep)){res.writeHead(404);res.end();return;}
    if(pathname.startsWith('/data/')){res.writeHead(404,{'Content-Type':'application/json'});res.end('{}');return;}
    const mime=target.endsWith('.js')?'application/javascript':target.endsWith('.css')?'text/css':'text/html';
    res.writeHead(200,{'Content-Type':mime});fs.createReadStream(target).pipe(res);
  });
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(5443,'::',resolve);});
  await startBackend(true);
  browser=await chromium.launch({channel:'msedge',headless:true,args:['--host-resolver-rules=MAP p1-ui.test 127.0.0.1','--no-proxy-server']});
  const context=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1100}});
  await context.route('**/*',r=>['p1-ui.test','localhost','127.0.0.1'].includes(new URL(r.request().url()).hostname)?r.continue():r.abort());
  page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',e=>pageErrors.push(e.message));
});
after(async()=>{
  await browser?.close();await stopBackend();if(server)await new Promise(r=>server.close(r));
  fs.writeFileSync(path.join(artifacts,'results.json'),JSON.stringify({scope:'local production-mode rehearsal, not deployed',states,pageErrors,storage},null,2));
  // Keep synthetic SQLite for inspection; remove only generated TLS keys/certificate.
  for(const name of ['test.key','test.crt']){const file=path.join(storage,name);if(fs.existsSync(file))fs.unlinkSync(file);}
  assert.deepEqual(pageErrors,[]);
});
test('production auth and exact-origin preflight',async()=>{
  const endpoint=api+'/api/closure/evidence';
  let response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',Origin:ui},body:'{}'});
  assert.equal(response.status,401);
  for(const [origin,status] of [[ui,200],['https://evil.example.test',400]]){
    response=await fetch(endpoint,{method:'OPTIONS',headers:{Origin:origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'}});
    assert.equal(response.status,status);
    if(status===200)assert.equal(response.headers.get('access-control-allow-origin'),ui);
  }
});
test('real browser authentication, JD forms, discovery and manual edit',async()=>{
  await page.goto(ui+'/emerging');
  await page.getByLabel('管理员写入密钥').fill(secret);
  await clickPost('验证写入权限','/access/verify');
  assert.deepEqual(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length})),{local:0,session:0});
  await page.getByText('追加JD证据（不覆盖原始数据）',{exact:true}).click();
  for(let i=0;i<3;i++){
    const evidence={job_id:`PROD-SYN-${Date.now()}-${i}`,original_title:title,responsibilities:'维护合成生产验收服务',required_skills_raw:'Python RAG LangGraph Docker',published_at:'2026-08-31'};
    if(i===0)firstEvidence=evidence;
    for(const [label,key] of [['新JD编号','job_id'],['原始岗位名称','original_title'],['JD职责原文','responsibilities'],['必备技能原文','required_skills_raw'],['真实发布时间','published_at']])await page.getByLabel(label,{exact:true}).fill(evidence[key]);
    await clickPost('保存JD证据','/evidence');
  }
  const list=await clickPost('运行新岗位发现','/discovery/run');item=list.find(i=>i.auto_definition.job_name===title);assert.ok(item);
  automatic=structuredClone(item.auto_definition);
  await page.locator('.closure-candidate-list button').filter({hasText:title}).click();
  await page.getByRole('button',{name:'编辑五要素',exact:true}).click();
  for(const name of ['Docker','LangGraph'])await page.locator('.closure-editor fieldset label').filter({hasText:new RegExp('^'+name)}).locator('select').selectOption('excluded');
  item=await clickPost('保存人工修改','/manual');assert.deepEqual(item.auto_definition,automatic);
});
test('browser submit, approve and publish activate only the published snapshot',async()=>{
  const box=page.getByTestId('closure-detail');
  await box.getByLabel('审核人（可空）').fill('spoofed');
  await box.getByLabel('审核说明 / 驳回理由').fill('合成验收，已核验证据及缺口');await box.getByRole('checkbox').check();
  item=await clickPost('提交审核','/actions');
  assert.ok(!(await request('/jobs')).jobs.some(j=>j.standard_job_title===title));
  await box.getByLabel('审核说明 / 驳回理由').fill('合成验收，已核验证据及缺口');await box.getByRole('checkbox').check();
  item=await clickPost('批准','/actions');
  assert.ok(!(await request('/jobs')).jobs.some(j=>j.standard_job_title===title));
  assert.equal(item.reviewer,'synthetic-admin');
  item=await clickPost('发布','/actions');await verify('V1 published',1,['Python','RAG']);
  await page.reload();await page.locator('.closure-candidate-list button').filter({hasText:title}).click();
  await page.getByTestId('publication-status').filter({hasText:'V1'}).waitFor();
  await page.screenshot({path:path.join(artifacts,'published-after-refresh.png'),fullPage:true});
});
test('V2 pending and approved stay isolated; publishing switches both consumers',async()=>{
  await edit(['Python','RAG','LangGraph']);await action('submit');await verify('V2 pending',1,['Python','RAG']);
  await action('approve');await verify('V2 approved unpublished',1,['Python','RAG']);
  await action('publish');await verify('V2 published',2,['Python','RAG','LangGraph']);
});
test('V3 rejection does not affect matching or graph',async()=>{
  await edit(['Python','RAG','LangGraph','Docker']);await action('submit');await verify('V3 pending',2,['Python','RAG','LangGraph']);
  await action('reject');await verify('V3 rejected',2,['Python','RAG','LangGraph']);
});
test('actual API process termination and restart preserve JD, review and publication',async()=>{
  const history=await request(`/closure/candidate/${item.id}/versions`);const old=publicationFingerprint;
  await stopBackend();await startBackend(false);
  assert.deepEqual(await request(`/closure/candidate/${item.id}/versions`),history);
  assert.equal((await request(`/closure/evidence/${firstEvidence.job_id}`)).responsibilities,firstEvidence.responsibilities);
  await verify('after process restart',2,['Python','RAG','LangGraph']);assert.equal(publicationFingerprint,old);
  await page.goto(ui+'/match');await page.getByLabel('目标岗位',{exact:true}).selectOption({label:title});
  await page.getByLabel('技能清单',{exact:true}).fill('Python RAG');await clickPost('开始匹配','/match');
  await page.getByTestId('profile-source').filter({hasText:'V2'}).waitFor();
  await page.goto(ui+'/graph');await page.getByRole('combobox').selectOption({label:title});
  await page.getByTestId('profile-source').filter({hasText:'V2'}).waitFor();await page.locator('canvas').first().waitFor();
  await page.screenshot({path:path.join(artifacts,'graph-after-restart.png')});
});
test('unchanged P0 optional fallback handles 404, network and JSON parse failure',async()=>{
  for(const failure of ['404','network','json']){
    const route='**/data/job_analysis_v1.json';
    await page.route(route,r=>failure==='network'?r.abort():r.fulfill({status:failure==='404'?404:200,contentType:'application/json',body:failure==='json'?'<not-json>':'{}'}));
    await page.goto(ui+'/jobs');
    await page.locator('.toolbar select').first().selectOption({label:title});
    await page.getByTestId('profile-source').filter({hasText:'V2'}).waitFor();
    await page.getByTestId('published-profile').waitFor();
    await page.unroute(route);states.push({label:`optional fallback ${failure}`,profileVersion:2});
  }
  assert.deepEqual(pageErrors,[]);
});
