import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
let server;
before(async()=>{server=await createServer({server:{middlewareMode:true},appType:'custom',optimizeDeps:{noDiscovery:true,include:[]}});});
after(async()=>{await server?.close();});
test('shared profile label displays server-selected published version, not draft state',async()=>{
  const {default:Badge}=await server.ssrLoadModule('/src/components/ProfileSourceBadge.tsx');
  const html=renderToStaticMarkup(React.createElement(Badge,{info:{profile_source:'published_dynamic',profile_version:2}}));
  assert.match(html,/已发布画像 V2/);assert.ok(!html.includes('静态基线'));
});
test('no publication label reports real recruitment aggregation with no fabricated version',async()=>{
  const {default:Badge}=await server.ssrLoadModule('/src/components/ProfileSourceBadge.tsx');
  const html=renderToStaticMarkup(React.createElement(Badge,{info:{profile_source:'static_baseline',profile_version:null}}));
  assert.match(html,/真实招聘信息聚合/);assert.ok(!html.includes('V1'));
});
test('job analysis labels current JD aggregate without implying a manual publication',async()=>{
  const {default:Badge}=await server.ssrLoadModule('/src/components/ProfileSourceBadge.tsx');
  const html=renderToStaticMarkup(React.createElement(Badge,{info:{profile_source:'jd_aggregate',profile_version:null}}));
  assert.match(html,/真实招聘信息聚合/);assert.ok(!html.includes('已审核'));
});
