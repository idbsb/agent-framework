# 多源异构数据驱动的岗位与能力图谱构建智能系统

本项目面向挑战杯比赛演示，以真实招聘 JD、标准岗位体系和标准技能库为基础，形成以下完整链路：

`真实JD → JD解析 → 岗位/技能标准化 → 岗位能力图谱 → 动态演化接口 → 新岗位候选发现`

`简历文本 → Resume Parser → 能力画像 → 人岗匹配 → 技能差距 → 学习路径`

当前系统基于 191 条真实招聘 JD、82 个标准技能和 27 份标准化测试简历构建。所有数字由正式数据或程序输出读取，不使用最终演示 Mock Data。

## 系统架构

- 算法层：`src/core/` 中已有 JD Parser、Resume Parser、Matching Engine 和技能抽取保持兼容。
- 数据层：`src/data_loader.py` 只读加载四个冻结正式 Excel，并提供 SHA-256 与 ID 校验。
- 新岗位发现：`src/emerging/` 使用真实标题、标准技能组合、聚类一致性和多源 Evidence 生成候选。
- 兼容层：`src/integration/` 读取组员 A 的图谱/演化成果。正式 JSON 缺失时，图谱只转换已有正式关系表；演化明确返回未接入状态。
- 接口层：FastAPI 提供解析、匹配、图谱、演化、新岗位和系统概览接口。
- 展示层：React + Vite + TypeScript + ECharts 构建八个页面。

## 数据来源

正式数据位于 `outputs/`：

- `standardized_jd_dataset_v1.xlsx`
- `standard_job_title_mapping_v1.xlsx`
- `standard_skill_dictionary_v1.xlsx`
- `standardized_resume_testset_v1.xlsx`

这些文件视为冻结数据，程序只读使用。图谱兼容数据来自 `组员图谱动态/重要岗位技能分析表.xlsx`，页面和 API 会明确标记“由组员A现有正式关系表转换”。

## 功能模块

1. 数据驾驶舱：真实 JD、岗位、技能、图谱、简历、来源和热门技能。
2. 岗位分析：职责、必备技能、加分技能、技能频率和能力画像。
3. 岗位能力图谱：按重点岗位过滤、拖拽、缩放、节点详情和 Evidence JD。
4. 动态演化：正式结果 Adapter；当前缺失时展示“动态演化数据尚未接入”。
5. 新岗位发现：候选评分、置信等级、真实标题、技能与完整 Evidence。
6. JD 智能解析：现场粘贴 JD，输出岗位预测、技能和证据。
7. 简历智能分析：现场粘贴简历文本，输出能力画像和证据。
8. 人岗匹配：五维评分、技能差距、优势技能、优先补足技能和已有学习建议。

## 环境要求

- Windows 10/11
- Python 3.11–3.12
- Node.js 20 或更高版本
- npm 10 或更高版本

## 安装

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

## 启动

Windows 可直接双击 `start_system.bat`。

后端：

```powershell
.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm run dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。FastAPI 文档位于 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

## 使用方法

- 首页确认数据服务状态和真实性说明。
- 在岗位分析、能力图谱和动态演化页选择重点岗位。
- 在新岗位发现页打开候选详情，核对 `evidence_jd_ids` 和原始 JD 证据。
- 在 JD、简历和匹配页使用默认演示文本，或替换为现场文本后提交。
- 后端未启动时，静态展示模块降级到程序生成的真实 JSON；交互解析与匹配会给出明确提示。

## 数据更新

不要覆盖冻结 V1 数据。新增数据应创建新版本并更新 `config/data_sources.yaml`。随后依次执行：

```powershell
.venv\Scripts\python.exe -m src.emerging.export_emerging
.venv\Scripts\python.exe -m src.integration.export_frontend_data
cd frontend
npm run build
```

后续补入 `knowledge_graph_v1.json` 或 `key_job_evolution_v1.json` 后，Adapter 会优先读取正式文件，前端页面无需修改。

## 目录结构

```text
agent_framework/
├─ config/                 算法权重与数据源配置
├─ docs/                   部署、交付和接口说明
├─ frontend/               React + Vite 前端
├─ outputs/                冻结数据与程序输出
├─ reports/                分析和系统测试报告
├─ src/
│  ├─ api/                 FastAPI 接口
│  ├─ core/                已通过 QA 的核心算法
│  ├─ emerging/            新岗位候选发现
│  └─ integration/         图谱/演化/前端数据 Adapter
├─ tests/                  单元与系统测试
└─ start_system.bat        Windows 一键启动
```

## API

保留原接口：

- `POST /api/jd/parse`
- `POST /api/resume/parse`
- `POST /api/resume/extract`（PDF、DOCX、TXT，最大 8MB，仅内存解析）
- `POST /api/match`
- `GET /api/jobs`
- `GET /api/skills`

新增接口：

- `GET /api/system/overview`
- `GET /api/job-analysis/{job_title}`
- `GET /api/graph/job/{job_title}`
- `GET /api/graph/skill/{skill_id}`
- `GET /api/evolution/job/{job_title}`
- `GET /api/emerging-jobs`
- `GET /api/emerging-jobs/{candidate_id}`

## 当前局限

- 当前只有组员 A 的三个重点岗位正式关系 Excel，尚未接入完整 `knowledge_graph_v1.json`。
- `key_job_evolution_v1.json` 尚未提供，因此不展示或计算任何趋势。
- 当前新岗位结果是招聘市场候选观察，不能等同于国家正式职业分类中的“新职业”。
- 单条 JD 一律为弱候选；部分 JD 缺少正式发布时间，近期信号按缺失处理。
- Matching V1 直接展示真实结果，不宣传不存在的高准确率。

## P1 生产部署与最终验收

P1 的线上生产闭环仍需负责人部署验收；本地测试通过不等于 P1 COMPLETE。

配置、首次持久库初始化、管理员权限、备份及线上验收步骤见 [P1 生产部署说明](docs/p1_production_deployment.md)。

## 免费公开部署（不使用 Vercel）

比赛展示使用一个 Render 免费 Web Service 同时提供前端和 API。该模式支持公开查询、文件简历解析、匹配和展示，但关闭无法持久化的在线 SQLite 写入。部署方法和限制见 [Render 免费部署说明](docs/render_free_deployment.md)。

## 参赛软件材料

- [源代码及版本说明](docs/source_code_and_version.md)
- [部署说明](docs/deployment_guide.md)
- [单元测试与覆盖率说明](docs/testing_and_coverage.md)

完整覆盖率可执行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_coverage.ps1`；Python 与前端均设置 60% 自动失败门槛。
