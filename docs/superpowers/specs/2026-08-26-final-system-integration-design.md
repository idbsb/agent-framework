# 挑战杯最终系统集成设计

## 目标与边界

在不重构已通过 QA 的 Parser、Matching Engine、公共 Schema 和冻结数据的前提下，新增新岗位发现、组员 A 数据兼容层、多页面前端、增量 API 和系统级 QA，形成可本地稳定演示的完整系统。

冻结的四个正式 Excel 只读使用，并在实施前后记录 SHA-256。所有新增公共接口只增加字段或路由，不删除、重命名原有字段与路由。

## 总体架构

系统采用三层结构：

1. 数据与算法层：现有 `DataLoader`、JD Parser、Resume Parser、Matching Engine 保持不变；新增 `src/emerging/` 负责新岗位候选计算。
2. 兼容与接口层：Graph Adapter 优先读取未来正式 `knowledge_graph_v1.json`，当前只把组员 A 已有正式岗位—技能关系表转换为前端兼容结构；Evolution Adapter 只读取未来正式文件，缺失时返回“数据尚未接入”。FastAPI 以新增路由暴露数据。
3. 展示层：React、Vite、TypeScript 与 ECharts 构建八个页面。运行时优先访问 FastAPI；图谱、新岗位等只允许降级到程序生成的真实静态 JSON。

## 新岗位发现

候选从真实 JD 的岗位名称、标准技能集合和岗位画像差异中产生，不使用外部 API，不由大模型创造名称。算法使用确定性的标题字符特征、标准技能 Multi-Hot/Jaccard 相似度和连通聚类，重点观察无正式岗位真值的 12 条 JD，同时允许有真实重复证据的其他组合进入候选池。

`EmergingScore` 为 0–100 分，权重来自 `config/emerging_job_config.yaml`，组成包括标题新颖性、技能新颖性、簇一致性、Evidence 数量、来源多样性、企业多样性和近期信号。缺失时间不补造近期信号。单条 JD 强制归为弱候选/待观察，不能成为高置信候选。

每个候选完整保留 `evidence_jd_ids`、代表标题、核心技能、差异技能、来源数、企业数、代表 Evidence、与已有岗位关系、原因与人工复核标记。候选名称优先选取簇内真实原始岗位标题。Excel 和 JSON 内容来自同一次检测结果。

## 组员 A 数据适配

Graph Adapter 的数据源优先级为：

1. `knowledge_graph_v1.json`；
2. 当前组员 A 的正式岗位技能关系 Excel。

第二种来源只做字段转换，不新增、推导或补全关系，并在响应和页面中标记“由组员A现有正式关系表转换”。缺少的正式图谱文件记录到最终交付说明。

Evolution Adapter 只读取 `key_job_evolution_v1.json` 或约定的正式替代文件。当前缺失时返回可用但无数据的状态对象，API 为正常响应，页面显示“动态演化数据尚未接入”，不计算任何趋势。

## API 设计

原有以下路由保持兼容：

- `POST /api/jd/parse`
- `POST /api/resume/parse`
- `POST /api/match`
- `GET /api/jobs`
- `GET /api/skills`

新增只读路由：

- `GET /api/system/overview`
- `GET /api/job-analysis/{job_title}`
- `GET /api/graph/job/{job_title}`
- `GET /api/graph/skill/{skill_id}`
- `GET /api/evolution/job/{job_title}`
- `GET /api/emerging-jobs`
- `GET /api/emerging-jobs/{candidate_id}`

未生成的数据使用明确的状态字段和说明，不以 500 错误或假数据替代。前端开发端口通过最小 CORS 配置访问 FastAPI。

## 前端设计

前端包含八个路由：数据驾驶舱、岗位分析、岗位能力图谱、动态演化、新岗位发现、JD 智能解析、简历智能分析、人岗匹配。技能差距和学习路径合并在人岗匹配页，直接展示 Matching Engine 的结果与 recommendations。

视觉采用深色科技数据平台风格，但以信息层级和可读性为主。图谱默认按岗位和 Top 技能过滤，不一次显示全部节点。解析与匹配页面提供可直接用于现场演示的表单、结果卡片和 Evidence 展开区域。

API 不可用时页面显示“后端服务未启动，请启动FastAPI服务。”；图谱或演化数据缺失时显示对应模块状态，不白屏。所有 KPI 从真实 API 或程序输出计算。

## 启动与部署

后端使用 Uvicorn，前端使用 Vite。提供 `start_system.bat` 分别启动两个本地服务。部署说明面向 Windows，列出 Python、Node、依赖安装、数据位置和常见错误。本阶段不部署线上站点，不制作 PPT、视频或答辩稿。

## 验证策略

测试覆盖：冻结文件哈希与 ID 一致性、原五个 API、所有新增 API、候选 Evidence 约束、单条候选置信度上限、图谱来源标记、演化缺失状态、前端构建、页面路由、中文文本、后端不可用提示，以及一次真实 JD 解析、简历解析和人岗匹配闭环。

最终测试报告明确记录已知限制：当前图谱为组员 A 正式 Excel 的兼容转换，动态演化尚未接入正式数据，新岗位候选不等同于国家正式职业分类中的新职业。
