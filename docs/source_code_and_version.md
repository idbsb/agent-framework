# 源代码及版本说明

## 1. 项目与版本

| 项目 | 内容 |
|---|---|
| 项目名称 | 多源异构数据驱动的岗位与能力图谱构建智能系统 |
| 代码仓库 | https://github.com/idbsb/agent-framework |
| 仓库可见性 | Public（公开仓库） |
| 正式分支 | `main` |
| 正式系统源代码基线 | `5d6bbaa6103c13f9bef5c1ea1649a906356073ac` |
| 参赛版本标签 | `competition-final-v1.0` |
| 在线演示 | https://agent-framework-g8ij.onrender.com/ |
| 材料整理日期 | 2026-09-03 |

`competition-final-v1.0` 是最终参赛包的固定入口。源代码基线 commit 对应本次材料整理前已经部署并完成生产验证的正式业务版本；参赛标签同时包含覆盖率工具、测试报告和交付文档。评审时应优先检出该标签，避免受到赛后继续开发的影响。

```bash
git clone https://github.com/idbsb/agent-framework.git
cd agent-framework
git checkout competition-final-v1.0
```

## 2. 源代码目录

| 目录 | 内容 |
|---|---|
| `src/api/` | FastAPI 应用、接口路由及服务装配 |
| `src/core/` | JD 解析、简历解析、技能抽取和人岗匹配核心逻辑 |
| `src/closure/` | 岗位画像审核、发布、存储与备份闭环 |
| `src/emerging/` | 新岗位候选发现和 Evidence 校验 |
| `src/integration/` | 图谱、动态演化及前端数据适配层 |
| `external_modules/graph_dynamic/src/` | 组员图谱与动态演化模块源代码 |
| `frontend/src/` | React、TypeScript、Vite 与 ECharts 前端源码 |
| `tests/` | Python 单元、接口、回归与系统测试 |
| `frontend/tests/` | 前端组件、路由、接口容错与生产构建测试 |
| `config/` | 数据源、字段映射、匹配权重与版本配置 |
| `scripts/` | 数据基线、交付报告及覆盖率执行脚本 |

## 3. 技术栈

- 后端：Python 3.12、FastAPI、Pydantic、Uvicorn、SQLite、openpyxl。
- 前端：React 19、TypeScript 5、Vite 7、ECharts 6。
- 测试：Python `unittest` + `coverage.py`，Node Test Runner + `c8`。
- 部署：Render Web Service；FastAPI 同域提供 API 和已构建的 React 静态文件。

## 4. 启动与验证入口

后端启动：

```powershell
.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

前端开发启动：

```powershell
cd frontend
npm run dev
```

完整测试与覆盖率：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_coverage.ps1
```

详细安装、环境变量及生产部署步骤见 `docs/deployment_guide.md`；覆盖率口径和结果见 `docs/testing_and_coverage.md`。

## 5. 可执行程序说明

本项目是浏览器访问的 Web 系统，不是桌面软件，因此不额外提供 Windows `.exe`。评审交付物为可复现源代码、前端生产构建 `frontend/dist/`、依赖锁文件、部署说明和在线演示地址。该形式符合“可执行程序（如有）”的要求，并避免将 Web 服务错误封装为不可审查的桌面程序。

## 6. 完整性核验

```bash
git rev-parse competition-final-v1.0
git status --short
```

第一条命令用于确认固定参赛版本；第二条命令在全新检出后应无输出。评审材料中的密钥均为占位符，实际管理员令牌、数据库文件和本机 `.env` 不进入 Git。
