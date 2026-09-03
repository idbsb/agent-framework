// Real React SSR through the project's Vite/TypeScript pipeline. No mock state.
// Run: node --test tests/p0.test.mjs (uses only existing project dependencies).
import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

let server;
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', optimizeDeps: { noDiscovery: true, include: [] } });
});
after(async () => { await server?.close(); });

async function renderPage(name) {
  const { default: Page } = await server.ssrLoadModule(`/src/pages/${name}.tsx`);
  return renderToStaticMarkup(React.createElement(Page));
}

for (const page of ['JDParsePage', 'ResumeParsePage', 'MatchPage']) {
  test(`${page}: defaults contain no demo biography; explicit sample load only`, async () => {
    const html = await renderPage(page);
    const inputs = [...html.matchAll(/<input\b[^>]*\bvalue="([^"]*)"/g)];
    const textareas = [...html.matchAll(/<textarea\b[^>]*>([\s\S]*?)<\/textarea>/g)];
    assert.ok(inputs.length + textareas.length > 0);
    assert.ok([...inputs, ...textareas].every(match => match[1] === ''), 'initial form must be empty');
    assert.match(html, /加载示例/);
    assert.match(html, /清空/);
  });
}

test('JD bonus and match work experience are visible editable fields', async () => {
  const jd = await renderPage('JDParsePage');
  const match = await renderPage('MatchPage');
  assert.match(jd, /<label[^>]*>加分技能原文<textarea/);
  assert.match(match, /<label[^>]*>工作经历<textarea/);
});

test('resume page exposes an in-memory PDF DOCX TXT upload control', async () => {
  const html = await renderPage('ResumeParsePage');
  assert.match(html, /data-testid="resume-file"/);
  assert.match(html, /accept="[^"]*\.pdf[^"]*\.docx[^"]*\.txt/);
  assert.match(html, /最大 8MB/);
  assert.match(html, /不保存到服务器/);
});

test('actual payload builders clear all evidence and reject unrelated state', async () => {
  const { emptyForm, jdPayload, matchPayload, resumePayload } = await server.ssrLoadModule('/src/formPayloads.ts');
  const sample = { education: '本科', experience: '2年', work_experience: 'Python', projects: 'Docker', skills_raw: 'FastAPI' };
  const empty = emptyForm(sample);
  assert.deepEqual(matchPayload(empty, '目标').resume, { resume_id: 'RESUME-INPUT', target_job: '目标', education: '', experience: '', work_experience: '', projects: '', skills_raw: '' });
  assert.equal(resumePayload({ ...empty, hidden: 'Python' }, '').hidden, undefined);
  const jd = jdPayload({ original_job_title: '文员', responsibilities: '整理纸质档案', required_skills_raw: '不需要编程技能', bonus_skills_raw: '', education: '', experience: '', hidden: 'FastAPI' });
  assert.equal(jd.bonus_skills_raw, '');
  assert.equal(jd.hidden, undefined);
  assert.ok(!JSON.stringify(jd).includes('FastAPI'));
});

test('skill evidence escapes HTML, excludes non-affirmed tags and explains evidence strength', async () => {
  const { default: View } = await server.ssrLoadModule('/src/components/SkillEvidenceView.tsx');
  const skills = ['negated', 'planned', 'other_person', 'uncertain'].map((polarity, start) => ({
    skill_id: String(start), standard_skill_name: 'Python', polarity, accepted: false,
    confidence: 0.98, evidence: '<script>alert("synthetic")</script>', source_field: 'skills_raw', start,
    evidence_strength: 'weak', need_human_review: polarity === 'uncertain',
  }));
  const html = renderToStaticMarkup(React.createElement(View, { skills }));
  assert.ok(!html.includes('<script>'));
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /暂无可接受的正向技能证据/);
  assert.match(html, /不代表技能熟练度、岗位胜任概率或录用概率/);
  assert.match(html, /弱 Evidence/);
  assert.doesNotMatch(html, /98%|抽取置信度/);
  assert.match(html, /需人工复核/);
});
