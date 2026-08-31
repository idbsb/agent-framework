import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
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

test('Vercel build rejects absent, insecure and non-root API URLs', async () => {
  const {spawnSync}=await import('node:child_process');
  for(const value of ['', 'http://api.example.test', 'https://api.example.test/api', 'https://localhost']) {
    const result=spawnSync(process.execPath,['node_modules/vite/bin/vite.js','build','--config','vite.config.ts'],{
      encoding:'utf8',env:{...process.env,VERCEL:'1',VITE_API_BASE_URL:value}
    });
    assert.notEqual(result.status,0,`unexpected success for ${value}`);
    assert.match(result.stderr,/VITE_API_BASE_URL/);
  }
});
