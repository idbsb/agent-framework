# P1 implementation map

## 基线

目录 D:\Projects\agent-framework；分支 feature/p1-core-closure；HEAD 1b830af
（fix: correct parsing and matching P0 issues）；开始工作区干净。禁止远程同步、commit、部署和生产数据访问。

## 现有与缺口

| 领域 | 现有实现 | 缺口及复用方式 |
| --- | --- | --- |
| 候选发现 | src/emerging/emerging_job_detector.py:EmergingJobDetector.detect，配置化聚类、真实JD证据、透明评分 | 目前API只读outputs/emerging_jobs_v1.json；复用算法，新增显式运行；持久ID用seed JD anchor，不用排名编号 |
| 候选五要素 | 候选名称、核心/差异技能、完整evidence_records | 缺职责/场景及字段级证据；从真实字段抽取和聚合，不调用LLM |
| 人工review | 只有need_human_review提示，src无业务审批 | 新增明确candidate→pending_review→approved/rejected→published；人工定义与自动定义分存 |
| 版本 | config/version.yaml为静态数据/Schema版本，非业务版本 | src流程无候选/发布画像版本；新增一套共用SQLite版本/审核/发布记录，不使用或迁移旧演示数据库 |
| 岗位画像 | P0 MatchingEngine._build_profiles，required>=0.20，bonus>=0.15，最多15/10 | 保留P0算法；审核中的变化不触及正式画像；发布版通过岗位分析接口呈现 |
| 动态演化 | EvolutionAdapter只读组员正式JSON；独立模块按day分窗 | 保留原接口；新增按日快照对比、明确窗口样本和证据，最小样本复用3、新技能最低证据数复用2 |
| JD证据 | 冻结工作簿有JD编号、原始标题、企业、职责、技能、招聘来源、原链接、标准发布时间、采集时间 | DataLoader的mapped字段未包含时间；新证据适配器直接读同一工作簿真实列；发布时间/采集/首次见到不混写 |
| 前端 | EmergingPage静态候选卡/抽屉；EvolutionPage静态演化卡 | 增加独立闭环面板、统一证据卡、人工编辑/审核/发布/历史diff；不改整体UI |

## 最小新增结构

- `src/closure/`：schema、证据及定义聚合、共用持久化service。
- 项目内`data/p1_closure.sqlite3`（测试使用独立路径）：追加JD、版本快照、状态事件、发布指针。
- 冻结Excel/正式JSON只读；既有JSON接口和P0解析/评分保留，不把候选自动注入匹配算法。
- 草稿版本保存auto_definition/manual_definition/evidence snapshot/fingerprint/previous_version。
- 状态改变只增加revision和审计事件；内容/证据变化才新增version。expected_version+expected_revision防止并发覆盖。
- 人工文字是人工修订，不自动宣称已被算法验证；每个非空字段必须绑定真实JD证据，技能须存在正向证据。
- 缺职责/必备技能不可批准；加分/场景缺失允许保留空值，但批准时需明确确认缺口并填写说明。

## API计划（追加，不删除旧接口）

- `/api/closure/evidence`：追加本地JD（不覆盖冻结数据），GET按ID追溯。
- `/api/closure/discovery/run`：复用发现算法；候选列表/详情/版本/diff/人工定义/状态动作。
- `/api/closure/profiles/...`：按岗位运行更新、读取正式发布版本、读取/审核change set。
- 返回400/404/409/422区分非法动作、未找到、版本冲突、证据/定义校验。

## 动态更新规则

- 按既有day窗口构建快照；当前正式画像基线使用冻结数据最新有效日窗口并明确标记legacy_baseline。
- 新JD追加后显式运行更新，比较当前发布快照与最新窗口；同日为snapshot_revision，不称市场趋势。
- 任一比较窗口<3：insufficient_sample，不输出上涨/下降，不批准发布更新。
- 删除仅在双窗口样本充分且技能在新窗口证据数为0时进入removed；不把未达阈值等价于完全消失。
- 新增达到既有new_skill_min_count=2门槛；频率/required-preferred角色变化进入modified。
- 发布时间缺失可用采集时间参与窗口，但time_source必须标注；两者都缺失的记录只保留证据，不参与时间趋势。

## 测试计划

先新增unittest覆盖A01-A12、B01-B10、非法动作/版本/证据，确认缺失实现失败；再实现。
新增Node原生前端测试和本地浏览器8场景；完整重跑P0、已有unittest、集成QA、build。
测试导入仅用合成JD并隔离数据库；不修改真实JD/简历、正式输出或生产服务。
