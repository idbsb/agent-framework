import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
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

test('Render build rejects absent, insecure and non-root API URLs', async () => {
  const {spawnSync}=await import('node:child_process');
  for(const value of ['', 'http://api.example.test', 'https://api.example.test/api', 'https://localhost']) {
    const result=spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build','--config','vite.config.ts'],{
      encoding:'utf8',env:{...process.env,RENDER:'true',VERCEL:'',VITE_API_BASE_URL:value}
    });
    assert.notEqual(result.status,0,`unexpected success for ${value}`);
    assert.match(result.stderr,/VITE_API_BASE_URL/);
  }
});

test('valid production API base builds and backend-only admin token is absent from dist', async () => {
  const {spawnSync}=await import('node:child_process');
  const marker='TEST_ADMIN_TOKEN_MUST_NOT_ENTER_FRONTEND_BUNDLE';
  const result=spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build','--config','vite.config.ts'],{
    cwd:join(process.cwd()),encoding:'utf8',env:{...process.env,RENDER:'true',VERCEL:'',
      VITE_API_BASE_URL:'https://api.example.test',P1_ADMIN_TOKEN:marker}
  });
  assert.equal(result.status,0,result.stderr||result.stdout);
  const files=[];
  const visit=dir=>readdirSync(dir,{withFileTypes:true}).forEach(entry=>entry.isDirectory()?visit(join(dir,entry.name)):files.push(join(dir,entry.name)));
  visit(join(process.cwd(),'dist'));
  assert.ok(files.some(file=>file.endsWith('.js')));
  assert.ok(files.every(file=>!readFileSync(file).includes(marker)));
});
