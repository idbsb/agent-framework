import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

let server;
before(async () => { server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom', optimizeDeps: { noDiscovery: true, include: [] } }); });
after(async () => { await server?.close(); });

test('quality banner labels fallback, raw/independent evidence and sample threshold', async () => {
  const { QualitySummary } = await server.ssrLoadModule('/src/components/DataQuality.tsx');
  const html = renderToStaticMarkup(React.createElement(QualitySummary, { data: { raw_evidence_count: 2, independent_evidence_count: 1, exact_duplicate_count: 0, near_duplicate_group_count: 1, time_quality: { published_at_coverage: .5, time_quality: 'low', fallback_count: 1 } }, windows: { before: 1, after: 11, minimum: 3 } }));
  assert.match(html, /采集时间回退/);
  assert.match(html, /前窗口 1/);
  assert.match(html, /独立证据估计 1/);
  assert.match(html, /不代表统计显著/);
});

test('offline legacy evolution is fail-closed without both window metadata', async () => {
  const { safeEvolution } = await server.ssrLoadModule('/src/components/DataQuality.tsx');
  const result = safeEvolution({ growing_skills: ['Python'], declining_skills: ['Docker'] }, true);
  assert.deepEqual(result.growing_skills, []);
  assert.deepEqual(result.declining_skills, []);
  assert.equal(result.trend_status, 'insufficient_sample');
});

test('file capability UI never offers unsupported upload or pretends OCR is available', async () => {
  const { FileSupportNotice } = await server.ssrLoadModule('/src/components/FileSupportNotice.tsx');
  const html = renderToStaticMarkup(React.createElement(FileSupportNotice));
  assert.match(html, /PDF\/DOCX/);
  assert.match(html, /待批准/);
  assert.match(html, /disabled/);
  assert.match(html, /不会自动上传/);
});
