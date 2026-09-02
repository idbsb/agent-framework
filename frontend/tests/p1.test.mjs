import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

let server;
before(async () => { server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom', optimizeDeps: { noDiscovery: true, include: [] } }); });
after(async () => { await server?.close(); });

test('unsafe evidence URLs are rejected; absolute HTTPS accepted', async () => {
  const { safeEvidenceUrl } = await server.ssrLoadModule('/src/closure.ts');
  for (const url of ['javascript:alert(1)', 'data:text/html,<script>', '//evil.test', 'https://u:p@evil.test', 'https:\\evil.test', 'https://good.test/\n']) assert.equal(safeEvidenceUrl(url), null);
  assert.equal(safeEvidenceUrl('https://jobs.example.test/1'), 'https://jobs.example.test/1');
});
test('evidence escapes HTML and links use noopener noreferrer', async () => {
  const { EvidenceList } = await server.ssrLoadModule('/src/components/ClosurePanel.tsx');
  const evidence = [{ job_id: 'j1', original_title: '<script>alert(1)</script>', responsibilities: '<img src=x onerror=alert(1)>', company: '<b>company</b>', url: 'https://jobs.example.test/1', time_source: 'collected_at_fallback' }, { job_id: 'j2', original_title: 'unsafe', url: 'javascript:alert(1)' }];
  const html = renderToStaticMarkup(React.createElement(EvidenceList, { evidence }));
  assert.ok(!html.includes('<script>') && !html.includes('<img'));
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.ok(!html.includes('href="javascript:'));
  assert.match(html, /采集时间回退/);
});
test('manual definition rendering escapes edits and labels insufficient fields', async () => {
  const { DefinitionView } = await server.ssrLoadModule('/src/components/ClosurePanel.tsx');
  const definition = { job_name: '<script>manual</script>', core_responsibilities: [], required_skills: [], preferred_skills: [], application_scenarios: [] };
  const html = renderToStaticMarkup(React.createElement(DefinitionView, { definition, label: '人工修订' }));
  assert.ok(!html.includes('<script>'));
  assert.match(html, /人工修订/);
  assert.match(html, /暂无足够职责证据/);
  assert.match(html, /场景证据不足/);
});

test('static job-analysis JSON stays on frontend origin with a separate API base', async () => {
  const { apiUrl } = await server.ssrLoadModule('/src/api.ts');
  assert.equal(apiUrl('/data/job_analysis_v1.json', 'http://127.0.0.1:8000'), '/data/job_analysis_v1.json');
  assert.equal(apiUrl('/api/jobs', 'http://127.0.0.1:8000'), 'http://127.0.0.1:8000/api/jobs');
});
