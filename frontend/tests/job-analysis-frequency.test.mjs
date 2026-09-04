import { before, after, test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "vite";

let server;
before(async () => { server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: "custom", optimizeDeps: { noDiscovery: true, include: [] } }); });
after(async () => { await server?.close(); });

test("small samples show evidence counts without a misleading percentage", async () => {
  const page = await server.ssrLoadModule("/src/pages/JobAnalysisPage.tsx");
  assert.equal(page.formatSkillFrequency({ evidence_jd_count: 1, sample_size: 1, frequency: 1 }, true), "1条JD提及");
  assert.equal(page.formatSkillFrequency({ evidence_jd_count: 2, sample_size: 2, frequency: 1 }, true), "2条JD提及");
});

test("adequate samples retain traceable numerator, denominator and percentage", async () => {
  const page = await server.ssrLoadModule("/src/pages/JobAnalysisPage.tsx");
  assert.equal(page.formatSkillFrequency({ evidence_jd_count: 3, sample_size: 5, frequency: 0.6 }, false), "3/5 · 60%");
});
