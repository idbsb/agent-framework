import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = (path) => readFile(new URL(`../src/${path}`, import.meta.url), "utf8");

test("commercial theme uses a light content surface and shared design tokens", async () => {
  const css = await source("styles.css");
  assert.match(css, /--bg:\s*#f5f7fa/i);
  assert.match(css, /--surface:\s*#ffffff/i);
  assert.match(css, /--sidebar:\s*#171a21/i);
  assert.match(css, /--brand:\s*#10b981/i);
  assert.match(css, /prefers-reduced-motion/);
});

test("job seeker navigation excludes developer-facing product placeholders", async () => {
  const layout = await source("components/Layout.tsx");
  assert.match(layout, /求职数据概览/);
  assert.match(layout, /岗位能力与智能匹配平台/);
  assert.match(layout, /职涌 · 求职决策智能体/);
  assert.doesNotMatch(layout, /TALENT GRAPH|Evidence-bound AI|MULTI-SOURCE TALENT INTELLIGENCE/);
});

test("all production pages exclude numbered hero labels and internal demo copy", async () => {
  const pages = ["DashboardPage", "JobAnalysisPage", "GraphPage", "EvolutionPage", "EmergingPage", "JDParsePage", "ResumeParsePage", "MatchPage", "MultiSourcePage", "JobChangesPage"];
  const content = (await Promise.all(pages.map((name) => source(`pages/${name}.tsx`)))).join("\n");
  assert.doesNotMatch(content, /index="0[1-8]"|ADAPTER READY|Evolution Adapter|真实API|现场演示|Matching Engine recommendations|直接调用Matching Engine|组员A/);
});

test("resume capability view shows evidence strength instead of mastery-like percentages", async () => {
  const evidence = await source("components/SkillEvidenceView.tsx");
  const page = await source("pages/ResumeParsePage.tsx");
  assert.match(evidence, /Evidence强度|证据强度/);
  assert.doesNotMatch(evidence, /Math\.round\(item\.confidence \* 100\)|抽取置信度.*%/);
  assert.match(page, /工作经历/);
  assert.match(page, /能力覆盖率/);
  assert.match(page, /缺失技能/);
});

test("dashboard presents the complete competition workflow without an internal batch card", async () => {
  const dashboard = await source("pages/DashboardPage.tsx");
  assert.match(dashboard, /多源数据采集/);
  assert.match(dashboard, /新岗位发现与定义/);
  assert.match(dashboard, /既有岗位能力更新/);
  assert.match(dashboard, /动态能力图谱/);
  assert.match(dashboard, /精准匹配与差距分析/);
  assert.doesNotMatch(dashboard, /最近一次图谱更新|新增JD|batch_update/);
});

test("multi-source and job-change pages describe market evidence instead of an import batch", async () => {
  const content = `${await source("pages/MultiSourcePage.tsx")}\n${await source("pages/JobChangesPage.tsx")}`;
  assert.doesNotMatch(content, /本批新增JD|本次数据更新|6份增量工作簿/);
  assert.match(content, /当前观察样本|多源证据/);
});
