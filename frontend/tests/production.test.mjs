import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
let server;
before(async () => {server = await createServer({server:{middlewareMode:true,hmr:false},appType:'custom',optimizeDeps:{noDiscovery:true,include:[]}});});
after(async () => {await server?.close();});
test('administrator token is limited to closure writes and can be cleared', async () => {
  const access=await server.ssrLoadModule('/src/closureAccess.ts');
  const api=await server.ssrLoadModule('/src/api.ts');
  const previous=globalThis.fetch; const calls=[];
  globalThis.fetch=async (url,options) => {calls.push({url,options});return {ok:true,json:async()=>({})};};
  try {
    access.setClosureCredential('synthetic-token');
    await api.postJson('/api/closure/evidence',{});
    await api.postJson('/api/match',{});
    await api.getJson('/api/closure/candidates');
    access.setClosureCredential('');
    await api.postJson('/api/closure/actions',{});
    assert.equal(calls[0].options.headers.Authorization,'Bearer synthetic-token');
    assert.equal(calls[1].options.headers.Authorization,undefined);
    assert.equal(calls[2].options.headers,undefined);
    assert.equal(calls[2].options.cache,'no-store');
    assert.equal(calls[3].options.headers.Authorization,undefined);
  } finally {globalThis.fetch=previous;access.setClosureCredential('');}
});

test('every successful closure write is followed by an uncached authoritative GET without the token', async () => {
  const access=await server.ssrLoadModule('/src/closureAccess.ts');
  const api=await server.ssrLoadModule('/src/api.ts');
  const previous=globalThis.fetch; const calls=[];
  globalThis.fetch=async (url,options={}) => {
    calls.push({url,options});
    return {ok:true,json:async()=>options.method==='POST'?{id:'synthetic-id'}:{id:'authoritative-id'}};
  };
  try {
    access.setClosureCredential('synthetic-token');
    const result=await api.postThenGet('/api/closure/evidence',{},written=>`/api/closure/evidence/${written.id}`);
    assert.equal(result.id,'authoritative-id');
    assert.deepEqual(calls.map(call=>call.options.method||'GET'),['POST','GET']);
    assert.equal(calls[0].options.headers.Authorization,'Bearer synthetic-token');
    assert.equal(calls[1].options.headers,undefined);
    assert.equal(calls[1].options.cache,'no-store');
  } finally {globalThis.fetch=previous;access.setClosureCredential('');}
});

test('resume upload uses multipart form data without forcing a content-type header', async () => {
  const api=await server.ssrLoadModule('/src/api.ts');
  const previous=globalThis.fetch; let call;
  globalThis.fetch=async (url,options) => {call={url,options};return {ok:true,json:async()=>({file_name:'resume.txt'})};};
  try {
    const file=new File(['Python'], 'resume.txt', {type:'text/plain'});
    await api.postFile('/api/resume/extract',file);
    assert.equal(call.url,'/api/resume/extract');
    assert.equal(call.options.method,'POST');
    assert.ok(call.options.body instanceof FormData);
    assert.equal(call.options.headers,undefined);
  } finally {globalThis.fetch=previous;}
});

test('resume analysis retries one transient network disconnect before reporting failure', async () => {
  const api=await server.ssrLoadModule('/src/api.ts');
  const previous=globalThis.fetch; let calls=0;
  globalThis.fetch=async () => {
    calls+=1;
    if(calls===1) throw new TypeError('network connection closed during service wake-up');
    return {ok:true,json:async()=>({resume_id:'RESUME-INPUT',skills:[]})};
  };
  try {
    const result=await api.postJson('/api/resume/parse',{});
    assert.equal(calls,2);
    assert.equal(result.resume_id,'RESUME-INPUT');
  } finally {globalThis.fetch=previous;}
});

test('live GET retries a transient Render wake-up failure before using fallback', async () => {
  const api=await server.ssrLoadModule('/src/api.ts');
  const previous=globalThis.fetch; let calls=0;
  globalThis.fetch=async (url) => {
    calls+=1;
    if(calls===1) return {ok:false,status:503,json:async()=>({})};
    return {ok:true,status:200,json:async()=>({available:true,source:url})};
  };
  try {
    const result=await api.getJson('/api/evolution/job/test','/data/evolution_status.json');
    assert.equal(calls,2);
    assert.equal(result.fallback,false);
    assert.equal(result.data.available,true);
  } finally {globalThis.fetch=previous;}
});

test('live GET uses static data only after all retry attempts fail', async () => {
  const api=await server.ssrLoadModule('/src/api.ts');
  const previous=globalThis.fetch; const calls=[];
  globalThis.fetch=async (url) => {
    calls.push(url);
    if(url==='/data/evolution_status.json') return {ok:true,status:200,json:async()=>({static:true})};
    return {ok:false,status:503,json:async()=>({})};
  };
  try {
    const result=await api.getJson('/api/evolution/job/test','/data/evolution_status.json');
    assert.equal(calls.at(-1),'/data/evolution_status.json');
    assert.ok(calls.length>=3);
    assert.equal(result.fallback,true);
  } finally {globalThis.fetch=previous;}
});

test('Render build rejects insecure and non-root external API URLs', async () => {
  const {spawnSync}=await import('node:child_process');
  for(const value of ['http://api.example.test', 'https://api.example.test/api', 'https://localhost']) {
    const output=mkdtempSync(join(tmpdir(),'challenge-cup-invalid-build-'));
    try {
      const result=spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build','--config','vite.config.ts','--outDir',output],{
        encoding:'utf8',env:{...process.env,RENDER:'true',VERCEL:'',VITE_API_BASE_URL:value}
      });
      assert.notEqual(result.status,0,`unexpected success for ${value}`);
      assert.match(result.stderr,/VITE_API_BASE_URL/);
    } finally { rmSync(output,{recursive:true,force:true}); }
  }
});

test('Render same-origin production build stays isolated from committed dist and test hosts', async () => {
  const {spawnSync}=await import('node:child_process');
  const marker='TEST_ADMIN_TOKEN_MUST_NOT_ENTER_FRONTEND_BUNDLE';
  const output=mkdtempSync(join(tmpdir(),'challenge-cup-production-build-'));
  try {
    const result=spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build','--config','vite.config.ts','--outDir',output],{
      cwd:join(process.cwd()),encoding:'utf8',env:{...process.env,RENDER:'true',VERCEL:'',
        VITE_API_BASE_URL:'',P1_ADMIN_TOKEN:marker}
    });
    assert.equal(result.status,0,result.stderr||result.stdout);
    const files=[];
    const visit=dir=>readdirSync(dir,{withFileTypes:true}).forEach(entry=>entry.isDirectory()?visit(join(dir,entry.name)):files.push(join(dir,entry.name)));
    visit(output);
    assert.ok(files.some(file=>file.endsWith('.js')));
    assert.ok(files.every(file=>!readFileSync(file).includes(marker)));
    assert.ok(files.every(file=>!readFileSync(file).includes('api.example.test')));
  } finally { rmSync(output,{recursive:true,force:true}); }
});

test('committed production bundle contains no placeholder API origin', () => {
  const files=[];
  const visit=dir=>readdirSync(dir,{withFileTypes:true}).forEach(entry=>entry.isDirectory()?visit(join(dir,entry.name)):files.push(join(dir,entry.name)));
  visit(join(process.cwd(),'dist'));
  assert.ok(files.every(file=>!readFileSync(file).includes('api.example.test')));
});
