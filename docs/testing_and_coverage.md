# 单元测试与覆盖率说明

## 1. 结论

2026-09-03 在正式参赛代码上完成全量测试与覆盖率测量。后端和前端均使用真实覆盖率工具并设置 60% 自动失败门槛，不以“测试全部通过”替代覆盖率指标。

| 测试范围 | 用例结果 | 行/语句覆盖率 | 分支覆盖率 | 门槛结论 |
|---|---:|---:|---:|---|
| Python 后端与算法模块 | 134/134 PASS | 67.90% | 57.40% | coverage.py 综合覆盖率 65.49%，≥60% |
| React/TypeScript 前端 | 33/33 PASS | 70.76% | 64.45% | 行覆盖率 ≥60% |
| 合计 | 167/167 PASS | 两端分别独立达标 | 分语言披露 | PASS |

Python 的 `coverage.py` 在启用 branch mode 后，以语句与分支机会合并计算总覆盖率 65.49%；单独的语句覆盖率为 67.90%。前端 `c8` 的竞赛门槛采用行覆盖率 70.76%，同时披露分支覆盖率 64.45% 和函数覆盖率 56.81%，不隐藏低于 60% 的函数维度。

## 2. 覆盖范围

后端覆盖：

- `src/api/`：FastAPI 路由、错误处理、静态前端服务。
- `src/core/`：JD/简历解析、Evidence、匹配引擎。
- `src/closure/`：采集、审核、发布、权限、SQLite 和备份。
- `src/emerging/`：候选聚类、Evidence 校验和补充 JD 管线。
- `src/integration/`：图谱、演化、正式数据适配。
- `external_modules/graph_dynamic/src/`：图谱动态模块。

前端覆盖 `frontend/src/**/*.ts` 与 `frontend/src/**/*.tsx`，仅排除无运行逻辑的 TypeScript 声明文件 `vite-env.d.ts`。没有为提高数字而排除业务源文件。

## 3. 测试内容

Python 测试位于 `tests/`，覆盖冻结数据行数和哈希、字段 Schema、技能边界与否定语义、JD/简历解析、人岗匹配、API 校验、权限矩阵、审核发布、SQLite 重启恢复、图谱与演化适配、新岗位 Evidence、补充 49 条 JD 守恒以及静态前端服务。

前端测试位于 `frontend/tests/`，覆盖八个正式路由、初始表单安全、Evidence 转义、管理员令牌边界、实时请求重试与静态回退、生产 API 地址校验、生产构建和 bundle 中无后端密钥。ECharts 图谱页面采用浏览器生产测试验证渲染，Node SSR 冒烟项验证其模块可加载，避免把浏览器专用图表库的 SSR 互操作误报为产品故障。

## 4. 一键复现

首次安装开发依赖：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd frontend
npm ci
cd ..
```

执行全部测试并强制检查 60% 门槛：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_coverage.ps1
```

脚本任一步骤返回非零退出码都会立即失败。可分别执行：

```powershell
.venv\Scripts\python.exe -m coverage run -m unittest discover -s tests -p "test_*.py" -v
.venv\Scripts\python.exe -m coverage report
cd frontend
npm run test:coverage
```

## 5. 报告文件

| 文件 | 用途 |
|---|---|
| `reports/coverage/backend-coverage.json` | 后端机器可读明细 |
| `reports/coverage/backend-coverage.xml` | Cobertura XML，可供 CI/评审工具读取 |
| `reports/coverage/frontend-coverage-summary.json` | 前端机器可读汇总 |
| `reports/coverage/backend-html/index.html` | 后端本地 HTML 明细，由脚本生成 |
| `reports/coverage/frontend-html/index.html` | 前端本地 HTML 明细，由脚本生成 |
| `docs/testing_and_coverage.md` | 测试范围、口径、命令与结果说明 |

HTML 目录体积较大，默认不提交 Git，但一键脚本会在本地重新生成；JSON、XML、本文和 PDF 报告随参赛标签提交。

## 6. 审核提示

测试通过数只能说明已定义用例没有失败；覆盖率说明测试实际执行了多少源代码。评审时应同时核对终端中的 `Ran 134 tests ... OK`、前端 `tests 33 / pass 33`、后端 `TOTAL ... 65.49%` 与前端 `All files ... 70.76%`，并确认执行命令退出码为 0。
