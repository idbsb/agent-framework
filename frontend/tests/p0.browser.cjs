// Optional real-browser regression runner, using an already installed Playwright.
// No dependency installation here. Requires local Vite :5173 + FastAPI :8000.
const { test, before, after, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const { chromium } = require(process.env.P0_PLAYWRIGHT_MODULE || 'playwright');

const base = 'http://127.0.0.1:5173';
// P2 integrity gate: opt into a fresh result path instead of overwriting old JSON.
const artifacts = path.resolve(process.env.P0_ARTIFACT_DIR || path.resolve(__dirname, '../../.codex_artifacts/p0'));
const results = [];
const pageErrors = [];
const blocked = [];
let browser, context, page, fullMatch;

before(async () => {
  fs.mkdirSync(artifacts, { recursive: true });
  browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--disable-background-networking'] });
});
beforeEach(async () => {
  context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (['127.0.0.1', 'localhost'].includes(url.hostname)) return route.continue();
    blocked.push(url.origin);
    return route.abort();
  });
  page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.setDefaultNavigationTimeout(15000);
  page.on('pageerror', error => pageErrors.push(error.message));
});
afterEach(async () => { await context?.close(); });
after(async () => {
  await browser?.close();
  fs.writeFileSync(path.join(artifacts, 'browser-results.json'), JSON.stringify({ results, pageErrors, blocked }, null, 2));
  assert.deepEqual(pageErrors, [], 'browser runtime errors');
  // Existing CSS imports Google Fonts. Keep it blocked, not fetched; do not
  // turn a P0 patch into a typography redesign. Any other origin is unexpected.
  assert.ok(blocked.every(origin => origin === 'https://fonts.googleapis.com'), 'unexpected non-local requests');
});

async function submit(endpoint, button) {
  const [response] = await Promise.all([
    page.waitForResponse(response => response.url().endsWith(endpoint) && response.request().method() === 'POST'),
    page.getByRole('button', { name: button, exact: true }).click(),
  ]);
  assert.equal(response.status(), 200);
  return { request: response.request().postDataJSON(), response: await response.json() };
}
async function record(id, value) {
  await page.screenshot({ path: path.join(artifacts, `${id}.png`), fullPage: true });
  results.push({ id, status: 'PASS', ...value });
  console.log(id, JSON.stringify(value.response));
}
function bounds(result) {
  assert.ok(result.match_score >= 0 && result.match_score <= 100);
  for (const value of Object.values(result.dimension_scores)) assert.ok(value === null || (value >= 0 && value <= 100));
}

test('Case 1: blank and cleared resume sends no hidden demo evidence', async () => {
  await page.goto(`${base}/match`);
  await page.getByRole('combobox').selectOption({ label: 'AI Agent开发工程师' });
  assert.ok((await page.locator('input,textarea').evaluateAll(nodes => nodes.map(node => node.value))).every(value => value === ''));
  await page.getByRole('button', { name: '加载示例', exact: true }).click();
  assert.ok(await page.locator('label').filter({ hasText: /^工作经历/ }).locator('textarea').inputValue());
  await page.getByRole('button', { name: '清空', exact: true }).click();
  const value = await submit('/api/match', '开始匹配');
  assert.equal(value.request.resume.work_experience, '');
  assert.equal(value.request.resume.skills_raw, '');
  assert.deepEqual(value.response.matched_skills, []);
  assert.equal(value.response.match_score, 0);
  assert.equal(value.response.dimension_scores.education, null);
  assert.equal(value.response.dimension_scores.experience, null);
  await page.getByText('学历：信息不足', { exact: false }).waitFor();
  await record('case1', value);
  await page.goto(`${base}/resume-parse`);
  const empty = await submit('/api/resume/parse', '分析简历');
  assert.deepEqual(empty.response.skills, []);
  results.push({ id: 'case1-empty-parse', status: 'PASS', ...empty });
});

test('Case 2: clerk JD contains no hidden bonus skill', async () => {
  await page.goto(`${base}/jd-parse`);
  await page.getByRole('button', { name: '加载示例', exact: true }).click();
  await page.getByRole('button', { name: '清空', exact: true }).click();
  await page.getByLabel('原始岗位名称', { exact: true }).fill('文员');
  await page.getByLabel('工作职责', { exact: true }).fill('整理纸质档案');
  await page.getByLabel('必备技能原文', { exact: true }).fill('不需要编程技能');
  const value = await submit('/api/jd/parse', '开始解析');
  assert.equal(value.request.bonus_skills_raw, '');
  assert.deepEqual(value.response.skills, []);
  await page.getByText('暂无可接受的正向技能证据').waitFor();
  await record('case2', value);
});

test('Case 3: negation is not a possessed skill', async () => {
  await page.goto(`${base}/resume-parse`);
  await page.getByLabel('技能清单', { exact: true }).fill('从未使用Python和Docker，不具备Java经验。仅掌握SQL。不会RAG和LangGraph。');
  const value = await submit('/api/resume/parse', '分析简历');
  assert.deepEqual(Object.fromEntries(value.response.skills.map(item => [item.standard_skill_name, item.polarity])), {
    Python: 'negated', Docker: 'negated', Java: 'negated', SQL: 'affirmed', RAG: 'negated', LangGraph: 'negated',
  });
  await page.locator('.tag-list').waitFor();
  assert.equal(await page.locator('.tag-list').innerText(), 'SQL');
  await record('case3', value);
});

test('Case 4: six explicit skills are all recognized', async () => {
  await page.goto(`${base}/resume-parse`);
  await page.getByLabel('技能清单', { exact: true }).fill('Python、FastAPI、LangGraph、RAG、MCP、Docker');
  const value = await submit('/api/resume/parse', '分析简历');
  assert.deepEqual(value.response.skills.map(item => item.standard_skill_name).sort(), ['Python', 'FastAPI', 'LangGraph', 'RAG', 'MCP', 'Docker'].sort());
  assert.ok(value.response.skills.every(item => item.accepted && item.polarity === 'affirmed'));
  await page.getByText('抽取置信度', { exact: false }).first().waitFor();
  await record('case4', value);
});

test('Case 5: explicitly loaded original match example is bounded', async () => {
  await page.goto(`${base}/match`);
  await page.getByRole('combobox').selectOption({ label: 'AI Agent开发工程师' });
  await page.getByRole('button', { name: '加载示例', exact: true }).click();
  const value = await submit('/api/match', '开始匹配');
  bounds(value.response);
  fullMatch = value;
  await page.getByText('项目经历：', { exact: false }).waitFor();
  await record('case5', value);
});

test('Case 6: removing only skills list cannot inflate project/total', async () => {
  assert.ok(fullMatch, 'Case 5 must have completed');
  await page.goto(`${base}/match`);
  await page.getByRole('combobox').selectOption({ label: 'AI Agent开发工程师' });
  await page.getByRole('button', { name: '加载示例', exact: true }).click();
  await page.locator('label').filter({ hasText: /^技能清单/ }).locator('textarea').fill('');
  const value = await submit('/api/match', '开始匹配');
  assert.deepEqual(value.request, { ...fullMatch.request, resume: { ...fullMatch.request.resume, skills_raw: '' } });
  bounds(value.response);
  assert.equal(value.response.dimension_scores.projects, fullMatch.response.dimension_scores.projects);
  assert.ok(value.response.match_score <= fullMatch.response.match_score);
  await page.getByText('项目经历：', { exact: false }).waitFor();
  await record('case6', value);
});

test('HTML-like evidence is displayed as text and does not execute', async () => {
  await page.goto(`${base}/resume-parse`);
  const text = '<img src=x onerror="window.p0Injected=true">掌握Python';
  await page.getByLabel('技能清单', { exact: true }).fill(text);
  const value = await submit('/api/resume/parse', '分析简历');
  await page.locator('.evidence-line').waitFor();
  assert.equal(await page.evaluate(() => window.p0Injected), undefined);
  assert.equal(await page.locator('.result-panel img').count(), 0);
  assert.ok((await page.locator('.evidence-line').innerText()).includes(text));
  await record('html-escape', value);
});

test('existing eight pages, formal graph/evolution and candidate drawer still render', async () => {
  for (const [route, title] of Object.entries({ '/': '数据驾驶舱', '/jobs': '岗位分析', '/graph': '能力图谱', '/evolution': '动态演化', '/emerging': '新岗位发现', '/jd-parse': 'JD智能解析', '/resume-parse': '简历智能分析', '/match': '人岗匹配' })) {
    await page.goto(`${base}${route}`);
    assert.equal(await page.locator('.topbar h1').innerText(), title);
    if (route === '/emerging') {
      await page.getByRole('button', { name: '查看完整证据' }).first().click();
      await page.locator('.detail-drawer').waitFor();
    }
    if (route === '/graph') {
      await page.locator('canvas').first().waitFor();
    }
    if (route === '/evolution') {
      await page.locator('.evolution-grid').waitFor();
      assert.match(await page.locator('.evolution-meta').innerText(), /样本量 12 条JD/);
    }
  }
  results.push({ id: 'eight-page-navigation', status: 'PASS' });
});
