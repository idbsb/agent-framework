# 三组岗位技能 Agent（持续更新版 V4）

本框架对应比赛下一阶段的最小闭环：

`真实 JD 导入 → 技能抽取 → 岗位画像 → 简历匹配 → 人工复核/反馈 → 下一轮重算`

当前版本优先保证真实 JD 可持续更新、技能可重新提取、页面刷新不丢结果，并完成一份简历与一类岗位的匹配闭环。

## 特点

- SQLite 保存统一数据结构：岗位、技能、岗位-技能关系、岗位画像、简历、评估和人工反馈。
- `SkillExtractionAgent` 以可审计的技能词典抽取结果；每条技能都记录命中原文和置信度。
- `ProfileAgent` 按 JD 出现频次及权重汇总岗位画像。
- `MatchAgent` 输出已匹配技能、缺失技能、匹配分数和可执行的改进建议。
- `ReviewAgent` 的确认/驳回/新增技能反馈会进入库中；后续运行会优先采用已确认或人工新增的技能，降低被驳回技能的可信度。
- 预留 `LLMExtractor` 接口：后续接入模型时只替换抽取器，不需要改变数据层、画像层和匹配层。
- 以 `job_id/JD编号` 为唯一标识：新编号新增、已有编号更新、完全相同的数据跳过。
- 更新 JD 时重新计算自动抽取技能，同时保留人工确认、驳回和补充记录。
- 导入概况和最近一次操作结果保存到 SQLite，刷新网页或重新打开程序仍能看到。
- 提供 Excel/JSON 网页入口以及 JSON 更新 API，便于第一组后续持续推送数据。

## 快速开始

最简单的使用方式：双击交付包中的 `岗位技能Agent_持续更新版.exe`，浏览器会自动打开中文操作页；无需使用终端。

网页支持直接同时导入第一组的 `重点岗位真实JD库.xlsx` 和 `岗位名称标准化表V1.1.xlsx`：标准化表用于把原始岗位名归入标准岗位、岗位簇和技术领域，真实 JD 库随后自动提取技能。未匹配的岗位会在结果中列出，交由第一组补充标准化规则。

如需使用命令行，在本目录执行：

```powershell
python -m agent_framework.cli init
python -m agent_framework.cli import-jobs --file ..\evidence_records.json
python -m agent_framework.cli build-profile --cluster "AI Agent开发工程师"
python -m agent_framework.cli match --cluster "AI Agent开发工程师" --resume "Python；LangGraph；RAG；向量数据库；Docker；FastAPI"
```

也可以用 `python -m unittest discover -s tests -v` 验证核心闭环。

## 开发环境与组员协作

```powershell
git clone https://github.com/idbsb/challenge-cup-job-skill-agent.git
cd challenge-cup-job-skill-agent
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python launch.py
```

源代码协作流程、分支和数据保密要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。真实 Excel、简历、SQLite 数据库和打包 exe 不进入 GitHub。

## 增量更新规则

每条 JD 必须有稳定的 `JD编号`（或 `job_id`、`id`）。系统按编号判断：

1. 编号不存在：新增岗位并提取技能。
2. 编号已存在、内容变化：更新岗位并重新提取自动技能。
3. 编号和内容都相同：记为“无变化”，不重复写入。
4. 更新不会删除第一组已经做出的人工复核记录。

网页首页会持续显示岗位总数、岗位簇数量、技术领域数量、技能数量，以及最近导入的新增/更新/无变化数量。

## 数据导入约定

JSON 可直接传数组，也可使用 `{"jobs": [...]}`。中文字段可使用第一组已有字段：`id`、`原始岗位名`、`岗位簇`、`企业`、`发布时间`、`职责摘要`、`技能摘要`、`学历经验`、`url`、`来源`、`状态`；未知字段会保留在 `raw_json`，不丢失来源证据。接口细节见 [API接口说明.md](API接口说明.md)。

## 人工复核示例

```powershell
python -m agent_framework.cli review --job-id AGENT001 --skill "RAG" --decision confirm --reviewer "第一组"
python -m agent_framework.cli review --job-id AGENT001 --skill "Kubernetes" --decision add --reviewer "第一组"
python -m agent_framework.cli build-profile --cluster "AI Agent开发工程师"
```

`confirm`、`reject`、`add` 分别代表确认、驳回和人工补充。每次写入均带时间、审核人和原因，可用于比赛展示中的“反馈—校验”证据链。

## 建议的三组协作方式

1. 第一组持续将已核验 JD 导出为 JSON 并导入本框架。
2. 第三组运行抽取、画像和匹配；把低置信度与人工反馈汇总交给第一组复核。
3. 第二组用稳定的岗位画像标注简历的高/中/低匹配结果，再用 `match` 的结果进行回测。

数据库默认位于程序旁的 `data/challenge_cup.db`。给组员共享新版程序时，如需连同已有数据一起共享，应把整个文件夹一起发给对方；不要只发送 exe。
