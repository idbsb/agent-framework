import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "vite";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";

let server;

before(async () => {
  server = await createServer({
    server: { middlewareMode: true },
    appType: "custom",
    optimizeDeps: { noDiscovery: true, include: [] },
  });
});

after(async () => {
  await server?.close();
});

const routes = [
  ["/", "真实招聘数据"],
  ["/jobs", "看懂目标岗位真正需要什么"],
  ["/evolution", "关注岗位能力要求的变化"],
  ["/emerging", "发现正在形成的新岗位机会"],
  ["/jd-parse", "职位解析"],
  ["/resume-parse", "简历分析"],
  ["/match", "人岗匹配"],
];

for (const [path, expectedText] of routes) {
  test(`route ${path} renders its production page`, async () => {
    const { default: App } = await server.ssrLoadModule("/src/App.tsx");
    const html = renderToStaticMarkup(
      React.createElement(MemoryRouter, { initialEntries: [path] }, React.createElement(App)),
    );
    assert.match(html, new RegExp(expectedText));
    assert.doesNotMatch(html, /TypeError|ReferenceError|页面崩溃/);
  });
}

test("graph route module loads for the browser-rendered ECharts page", async () => {
  const graph = await server.ssrLoadModule("/src/pages/GraphPage.tsx");
  assert.equal(typeof graph.default, "function");
});
