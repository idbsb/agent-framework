# P1 核心业务闭环本地交付报告

> 本报告保留原本地交付历史。生产闭环属于同一 P1 的最终验收，当前部署要求见 [P1 生产部署与线上验收](p1_production_deployment.md)，本轮验证见 [生产就绪报告](p1_production_readiness.md)。历史中的本地限制或测试数量不代表本轮结果，也不表示线上 P1 已完成。

日期：2026-08-31。范围：agent-framework 的新岗位闭环、既有岗位更新闭环、证据追溯。等待人工验收，未提交。

阅读说明：第 1–18 节保留首次 P1 交付记录（包括当时的测试数量、Git 状态和限制）；本次最后一个集成闭环的实现、最终测试及最终 Git 状态以第 19 节为准。

## 1. 基线与现场保护

- 实际项目：`D:\Projects\agent-framework`，未访问旧项目或 GitHub。
- 开始分支：`feature/p1-core-closure`；开始工作区干净。
- HEAD：`1b830af fix: correct parsing and matching P0 issues`。
- 开始最近提交：`1b830af`、`5c97d32`、`9a45848`。
- 本地 `fix/p0-correctness` 也指向 `1b830af`；开发建立在 P0 修复上，没有切分支或撤销 P0。
- 完成后 HEAD、分支未改变。保留本地修改，不 commit/push/部署。

## 2. 原始能力、实际缺口及复用

详细定位见 `docs/p1_implementation_map.md`。

| 领域 | 本轮前 | 本轮实现 |
| --- | --- | --- |
| 新岗位发现 | 有真实 JD 确定性聚类算法；API/页面主要读取静态候选 JSON | 显式运行原算法，稳定候选 ID，五要素及字段证据，编辑/审核/发布/历史 |
| 候选定义 | 名称、核心/差异技能、发现评分和 JD evidence | 五要素结构，缺失证据为空，自动与人工定义分开 |
| 动态演化 | 正式演化文件只读展示；日窗口、最低样本 3 | 增量 JD、双窗口保护、change set、审核发布画像版本 |
| 版本/人工状态 | 静态 data/schema version；没有此业务持久化闭环 | 一套共用实体、内容版本、状态 revision、发布快照、审计事件 |
| 证据 | 工作簿已有来源、企业、原链接、发布时间和采集时间 | 全量追溯、字段支持 ID、技能原文/位置、时间来源及安全链接 |
| 岗位分析 | 冻结画像与图谱展示 | 另显示已人工发布的正式画像，明确不与冻结数据混用 |

架构仍是 React 19 / Vite / TypeScript + FastAPI / Python。未替换 UI、解析器、评分器、数据库产品或部署结构。

## 3. 新岗位五要素及证据规则

`src/closure/evidence.py` 负责规范化和定义聚合，复用 P0 的真实 SkillIndex。

| 字段 | 来源与规则 | 证据不足时 |
| --- | --- | --- |
| job_name | 原发现算法选取真实代表岗位名称；人工改名明确标为人工修订 | 不凭行业常识生成名称 |
| core_responsibilities | JD 职责原文按分隔符切片、规范化空白后聚合同文片段 | `[]`，UI 显示暂无足够职责证据 |
| required_skills | 正向 accepted/affirmed evidence，按不同 JD 计覆盖率；沿用候选核心比例 0.50、最多 12 项 | `[]`，不拿否定/计划/他人技能凑数 |
| preferred_skills | 排除必备项；原算法没有加分阈值，本轮明确新增“至少 2 条 JD 支持”，最多 10 项 | `[]`，不凭技能常识补全 |
| application_scenarios | 真实 industry / scenario / business_context 字段 | `[]`；冻结 JD 无这些字段，不从岗位名或企业名想象场景 |

技能包含 `skill_id / skill_name / coverage / evidence_count / supporting_job_ids / evidence_snippets`。不同 section 的证据可保留多条，但同一 JD 在覆盖率分子中只计一次。职责和场景包含文本、支持 JD ID、原字段及原文片段。名称也保存支持 JD ID。

人工摘要并不等于机器验证的事实：UI 明确注明人工修订，必须选取真实支持 JD；后端拒绝不存在或缺少对应字段的引用。技能必须有正向证据，覆盖率和技能名称由后端重新生成，不信任客户端修改的统计数。

批准时必须有名称、职责和必备技能；场景/加分技能缺失允许保持空列表，但必须主动勾选接受缺口并填写审核说明。没有为了字段完整而编造内容，未调用 LLM。

## 4. 编辑、审核与发布

流程：`candidate → pending_review → approved → published`；可驳回为 `rejected`，随后重新提交。

- 保存人工修改生成新的内容版本，`auto_definition` 原样保留，人工结果写入 `manual_definition`。
- 同样的定义再次保存不会增版；同样的自动证据再次发现也不会重置人工定义或审核状态。
- 每个动作检查 `expected_version + expected_revision`。旧页面提交返回 409，要求刷新。
- 审批/驳回记录审核时间、审核人（可空）、理由；动作有审计事件。
- `publish` 只允许作用于最新且已批准版本。不能跳过审批、重复发布或发布旧草稿。
- 审核状态变更增加 revision，不为了点击审核制造内容版本。
- 新证据产生新自动版本时不会冒用前版人工结论；前版人工定义留在历史中，新版重新审核。
- 已发布快照不被新候选、待审内容或驳回覆盖。

前端保留原候选卡片及详情抽屉，在原风格中追加闭环面板。可查看发现规则得分（不是真实性概率）、状态、JD/企业/来源数、版本，编辑五要素，审核和发布。

## 5. 版本与差异

持久候选 ID 基于发现簇的 seed JD anchor，而不是会随排序变化的 EMERGING 排名。原静态候选接口及原 ID 不修改，新闭环使用 `CAND-*` ID。

每个内容版本包含前版号、创建时间、证据快照、定义快照和 SHA-256 fingerprint。相同定义/证据不无意义增版。人工编辑增加内容版本，但与发布画像的 `profile_version` 分开：例如人工内容 V2 首次发布为发布画像 V1，UI 明确区分。

版本 diff 包含新增/删除/修改技能，名称、职责、场景是否改变，以及证据数量前后变化。历史版本只读。发布快照另行冻结保存。

若新聚类同时合并多个已经持久化的候选身份，返回 409 并事务回滚，保留旧结果；不擅自选择一个身份覆盖其他候选。这类合并需要后续人工整合流程。

## 6. 既有岗位 Change Set 与发布画像

- 追加 JD 不覆盖冻结工作簿。相同 ID/相同内容为幂等；相同 ID/不同内容返回 409。
- 前端显式“重新计算能力更新”；API 支持已有冻结数据中的标准岗位名称，当前 UI 沿用原来的三个重点岗位入口。
- 首次运行以冻结 JD 最新有效日窗口建立 `legacy_baseline`，明确是冻结数据基线，不伪装成人工批准。
- 沿用现有日窗口、最低 JD 数 3、新技能最低证据 2。采用当前正式发布快照与最新日窗口比较。
- 同日新增证据标记 `snapshot_revision`，不同日标记 `daily_window_comparison`，均不宣称长期市场趋势。
- 岗位技能角色阈值沿用 P0 配置：必备 0.20、加分 0.15，上限 15/10；未修改原评分配置。
- `added_skills`：前窗口未见且新窗口至少 2 条 JD 正向证据。
- `removed_skills`：双窗口样本充分且后窗口该技能证据为 0；不把频率略降或低于必备阈值直接解释为消失。
- `modified_skills`：频率或 required/preferred/observed 角色变化。
- 新技能只有一条支持时保存于 `withheld_skills`，不出现在待发布的必备/加分定义里。
- 每个变化保存 before/after 覆盖率、角色及前后真实 JD evidence。
- 任一窗口不足 3：`insufficient_sample`，增删改列表为空，不批准发布。相同正式证据：`no_changes`，不重复发布。

更新审核单默认为 pending_review；批准后还要显式发布，才产生新的正式画像 `profile_version`。驳回保持旧正式画像。审核和发布共用候选版本存储与状态机，没有另建一套互不相干的版本系统。

## 7. 证据追溯、时间与安全

证据保存 JD 编号、原始/标准标题、企业、原始来源名称、原始链接、职责与技能原文，以及原抽取 evidence。页面统一使用 EvidenceList，可从变更项、定义和发布快照找到 JD。

- `published_at / collected_at / first_seen_at` 分开；缺失保持 null。
- 有有效发布时间时优先使用；否则采集时间回退明确为 `collected_at_fallback`。
- 两者均无有效日期时不进入时间窗口比较，ID 列在 excluded_undated_job_ids。
- 未统一来源实体名称或改变来源统计口径，避免擅自扩大数据科学范围。
- 链接仅允许安全绝对 HTTP/HTTPS；拒绝 javascript/data/协议相对链接、凭证链接、控制字符和反斜杠等危险形式。
- 正常链接新窗口打开，设置 `rel="noopener noreferrer"`。本轮验收不会实际访问外部招聘网站。
- React 按文本渲染 JD 和人工输入，不使用 dangerouslySetInnerHTML。脚本样式合成输入没有执行。

## 8. 数据结构、持久化与兼容性

新增本地 SQLite companion store（标准库 sqlite3，无新依赖），默认路径 `data/p1_closure.sqlite3`，已被现有 .gitignore 规则忽略。

两张表：

- `evidence(id, payload)`：追加式 JD 记录，不覆盖原始数据。
- `entities(kind, id, payload)`：共用候选/画像实体，内部保留内容版本、发布快照、事件和稳定 anchor。

事务使用 `BEGIN IMMEDIATE`，写入同时有乐观版本校验。内容版本、发布快照保留历史；只有当前版本审核状态和 revision 更新。没有迁移、删除或覆盖任何现有数据库。

兼容边界：

- P0 taxonomy、extractor、匹配算法、权重及 API schema 未改变。
- 原新岗位/图谱/动态演化接口仍返回原正式 JSON 结果。
- 新发布画像通过新 endpoint 和岗位分析页的“人工审核发布画像”展示。启用本地闭环时原 job-analysis API 追加 published_profile，不删除原字段。
- 首次交付时，新发布画像尚不自动进入 P0 人岗匹配或岗位技能图谱。**该集成限制现已由第 19 节修复**；冻结文件仍不被覆盖。
- 更新接口不是定时后台任务：追加 JD 后由用户显式触发重新计算。

## 9. API 清单与错误处理

均为新增，除 job-analysis 的可选追加字段外不改旧 API：

| 方法 | 路径 | 能力 |
| --- | --- | --- |
| POST | /api/closure/evidence | 追加 JD |
| GET | /api/closure/evidence/{job_id} | 追溯原证据 |
| POST | /api/closure/discovery/run | 运行原发现算法并形成候选版本 |
| GET | /api/closure/candidates | 当前持久候选 |
| POST | /api/closure/profiles/run | 按 job_title 计算更新 |
| GET | /api/closure/{kind}/{identifier} | 最新内容版本 |
| GET | /api/closure/{kind}/{identifier}/versions | 内容历史、发布历史、审计 |
| GET | /api/closure/{kind}/{identifier}/published | 正式发布快照 |
| GET | /api/closure/{kind}/{identifier}/diff?before=1&after=2 | 版本差异 |
| POST | /api/closure/{kind}/{identifier}/manual | 候选五要素人工编辑 |
| POST | /api/closure/{kind}/{identifier}/actions | submit / approve / reject / publish |

kind 为 candidate/profile。非法动作或 kind 为 400；未知实体/岗位/版本为 404；并发冲突/非法状态/冲突 JD 为 409；定义、证据或请求形状不合法为 422；本地写入保护为 403。畸形 skill_id 数组也测试了 422，不落成 500。

本轮没有完整登录认证，因此**所有新写接口默认关闭**，仅在进程显式设置 `P1_CLOSURE_WRITES=1`、请求来自 loopback、且浏览器 Origin 合法时开放。该保护仅服务本地验收，不等同于生产权限系统。本轮未修改任何生产环境变量。

## 10. 修改文件清单

已有文件 6 个，改动均局部：

1. frontend/package.json：复用 Node 测试，收集 P0/P1 文件，串行隔离 Vite 测试端口。
2. frontend/src/api.ts：静态 /data 路径留在前端来源，避免独立 API base 拼错。
3. frontend/src/pages/EmergingPage.tsx：追加新岗位闭环面板。
4. frontend/src/pages/EvolutionPage.tsx：追加当前重点岗位更新面板。
5. frontend/src/pages/JobAnalysisPage.tsx：已发布画像视图；缺少可选静态 JSON 时处理 Promise 异常。
6. src/api/app.py：挂载 P1 router、领域错误 handler、可选发布快照。

新增文件 13 个：

- docs/p1_implementation_map.md
- docs/p1_core_closure_report.md
- src/closure/__init__.py
- src/closure/evidence.py
- src/closure/service.py
- src/api/closure.py
- frontend/src/closure.ts
- frontend/src/components/ClosurePanel.tsx
- frontend/src/components/closure.css
- tests/test_p1_closure.py
- tests/test_p1_api.py
- frontend/tests/p1.test.mjs
- frontend/tests/p1.browser.cjs

未改部署文件、lockfile、依赖列表、原始 JD/简历或冻结输出。未批量格式化项目。新增源文件的尾随空白检查无命中。

## 11. 测试先行记录

1. 新增闭环 unittest，先确认因 `src.closure` 不存在失败，再实现。
2. 追加同定义保存/无变化发布测试，先得到真实失败，再修复幂等性。
3. 新增 ASGI API 测试、React SSR 安全测试，先因新模块不存在失败，再接入。
4. 新增“单条新技能不进入发布定义”断言，先复现真实失败，再加入 withheld_skills。
5. 浏览器八场景业务先通过，但全局错误断言失败，记录了两个未处理静态数据 Promise 错误；确认原因是独立 API 地址及 checkout 缺少可选 JSON，局部修复后整轮通过。没有忽略错误或削弱断言。
6. 畸形 manual skill_id 测试先暴露 TypeError，再修为 422。

没有引入第二套测试框架：Python 使用既有 unittest；前端使用既有 Node test/Vite SSR；浏览器复用现有 Playwright/Edge 环境。不下载新依赖。

## 12. 新增测试与覆盖

Python 新增 30 个：26 个真实服务测试 + 4 个实际 ASGI API 测试。

| 验收要求 | 测试名称（test_p1_closure.py，除特别标注） |
| --- | --- |
| A01 | test_a01_five_elements |
| A02 / A03 | test_a02_no_invented_responsibilities / test_a03_no_invented_scenarios |
| A04 | test_a04_manual_preserves_auto |
| A05 / A06 / A07 | test_a05_approve_persists / test_a06_reject_persists / test_a07_publish_requires_approval |
| A08 | test_a08_identical_evidence_idempotent |
| A09–A11 | test_a09_a10_a11_new_evidence_version_and_diff |
| A12 | test_a12_evidence_trace |
| B01–B04 | test_b01_b02_b03_b04_changes |
| B05–B07 | test_b05_pending_does_not_change_publication / test_b06_approve_publish / test_b07_reject_preserves_profile |
| B08–B10 | test_b08_before_window_insufficient / test_b09_after_window_insufficient / test_b10_collection_fallback_labelled |
| 版本、P0及证据安全 | test_version_conflict_and_invalid_action / test_p0_negation_never_required / test_unbacked_manual_skill_rejected / test_duplicate_jd_does_not_overwrite / test_html_and_urls_are_data |
| 额外幂等与发布保护 | test_identical_manual_save_no_version / test_unchanged_profile_cannot_publish_another_version / test_same_day_evidence_revision_not_market_trend / test_published_snapshot_survives_new_candidate_evidence |
| API（test_p1_api.py） | test_http_validation_and_not_found / test_local_write_guard / test_real_api_discover_review_and_conflict / test_malformed_skill_id_returns_422_not_500 |

前端新增 4 个 SSR/实际路径构造测试：安全 URL；evidence HTML 转义与 rel；人工定义转义与缺失提示；独立 API 地址不劫持静态 JSON。另新增 8 个真实浏览器场景，见下节。

## 13. 完整验证结果

| 验证 | 结果 |
| --- | --- |
| Python 全量 unittest | **75/75 PASS**：原有 45（含 P0 23），新增 P1 30 |
| 前端 npm test | **10/10 PASS**：P0 6 + P1 4 |
| P0 浏览器 | **8/8 PASS**；空白、文员、否定、六技能、默认样例、删除技能对照、HTML、八页导航 |
| P1 浏览器 | **8/8 PASS**；页面未处理错误 0 |
| 集成 QA | **11/11 checks PASS**；14 个现有 API 实际本地 HTTP 200 |
| TypeScript / frontend build | **PASS**；实际命令 tsc -b && vite build |
| git diff --check | **PASS**，无空白错误 |

项目无额外 lint/typecheck/formatter 命令或相应配置；TypeScript 检查由 build 执行。构建仍提示大 chunk（约 1.44 MB 原始 JS），属既有打包性能问题，本轮不扩展优化。

P0 关键数值：空简历技能 0、总分 0；学历/经验为 null/unknown。示例综合分 40.67、项目分 26.67；只删除技能清单后综合分 37.33、项目分仍 26.67。否定技能不匹配，明确六技能全识别，SQL/FastAPI 保持正确。

冻结数据仍为 JD 191、简历 27、技能 82（运行时含 P0 扩展）；四个冻结文件 SHA-256 均与既有 QA 基线一致。

验收产物（均是本地、git ignored）：

- `.codex_artifacts/p1/browser-1788180023439/results.json`：最终八场景机器结果与截图；errors=[]。
- `.codex_artifacts/p1/published-profile-local.png`：已发布画像实际可见面板，已人工式视觉检查。
- `.codex_artifacts/p1/system-qa-final/正式图谱动态接入QA结果.md`：既有 QA 脚本输出。
- `.codex_artifacts/p0/browser-results.json`：本轮重跑 P0 浏览器结果。
- `.codex_artifacts/p1/e2e-final-20260831.sqlite3`：最终独立验收数据库，仅包含冻结数据引用及明确标记的合成测试增量。

QA 脚本模板中仍有移动端/后端关闭降级的固定描述；本轮未把这些模板文字当作独立实测证据。以上 PASS 数仅指实际运行的断言，不声称另做了完整移动端、降级或线上测试。

## 14. 八个本地端到端场景

运行的是实际 FastAPI + React + Edge，无生产 API 写入；新增 JD 全为合成验收数据。原有冻结真实 JD 仅被读取作为基线。

| 场景 | 本地实测结果 | 结论 |
| --- | --- | --- |
| 1 发现→五要素 | 通过实际表单追加证据，运行真实发现，候选 CAND-a88d1ba0d29d 内容 V1；五要素可见；缺失场景不编造 | PASS |
| 2 编辑→保留自动 | 人工改名后内容 V2；auto_definition 与 V1 完全一致 | PASS |
| 3 批准→发布 | pending_review→approved→published；内容 V2 发布为画像 V1；刷新后状态保持 | PASS |
| 4 新证据→版本diff | 内容 V3，previous_version=2；显示新增 LangGraph；发布画像 V1 未被待审 V3 替换 | PASS |
| 5 既有岗位新JD | 前窗口11条、后窗口3条；生成含新增 SQL 的 pending change set；正式基线仍 V1 | PASS |
| 6 批准并发布更新 | 正式画像 V2；岗位分析页可见“人工审核发布画像 V2” | PASS |
| 7 驳回后续变化 | 新审核单 rejected，正式 V2 的完整快照保持不变 | PASS |
| 8 样本不足 | 前窗口3、后窗口1；insufficient_sample，增删改列表为空，批准按钮禁用 | PASS |

浏览器外部请求全部阻断。原 CSS 的 Google Fonts 请求被拦截，未为验收获取外部字体。未访问真实招聘原链接。

## 15. Git 最终检查

`git diff --stat`（Git 不包含未跟踪新增文件的统计）：

```text
 frontend/package.json                  |  2 +-
 frontend/src/api.ts                    |  5 +++--
 frontend/src/pages/EmergingPage.tsx    |  2 ++
 frontend/src/pages/EvolutionPage.tsx   |  2 ++
 frontend/src/pages/JobAnalysisPage.tsx |  9 ++++++++-
 src/api/app.py                         | 20 +++++++++++++++++++-
 6 files changed, 35 insertions(+), 5 deletions(-)
```

另有上述 13 个新文件未跟踪；没有为生成 diff 而执行 git add。

`git diff --check`：exit 0；仅有 Windows LF/CRLF 提示，不是空白错误。

最终 `git status --short --untracked-files=all`：

```text
 M frontend/package.json
 M frontend/src/api.ts
 M frontend/src/pages/EmergingPage.tsx
 M frontend/src/pages/EvolutionPage.tsx
 M frontend/src/pages/JobAnalysisPage.tsx
 M src/api/app.py
?? docs/p1_core_closure_report.md
?? docs/p1_implementation_map.md
?? frontend/src/closure.ts
?? frontend/src/components/ClosurePanel.tsx
?? frontend/src/components/closure.css
?? frontend/tests/p1.browser.cjs
?? frontend/tests/p1.test.mjs
?? src/api/closure.py
?? src/closure/__init__.py
?? src/closure/evidence.py
?? src/closure/service.py
?? tests/test_p1_api.py
?? tests/test_p1_closure.py
```

## 16. Blocker、限制与 P2

- 当前会话最初可写工作区仍指向旧项目，创建新目录、Vite 缓存和 QA 目录曾遇权限阻断；经工具批准后在指定 agent-framework 内完成，未绕过限制。
- 已解决本轮阻断：可选静态 JSON 缺失引发未处理错误、Vite 多测试端口竞争、畸形人工输入 500、单条新技能漏入发布定义。
- 尚未引入生产认证、远程审批权限与部署；新写接口只面向本地显式开启。这是交付边界，不是生产上线声明。
- 首次交付遗留的“发布画像未自动联动匹配/岗位技能图谱”已在第 19 节完成；未扩展图谱筛选或重构图谱算法。
- 真实数据场景字段、发布时间覆盖不足仍存在；本轮只如实暴露，不宣称补齐数据质量。
- 跨源近重复 JD、来源实体统一、长期趋势科学性、大样本精度评估仍为 P2。本轮按不同 JD ID 计数，不宣称解决转载/伪重复。
- 聚类合并的人工身份整合、规模化分页/索引、生产多用户认证待后续处理。
- PDF/DOCX/OCR、图谱筛选、学习路径升级、LLM、数据库产品迁移、UI 整体改版均未实施。

## 17. 人工复核与本地重现

本轮启动的后端/前端服务已停止，8000/5173 无遗留监听。验收数据库和报告保留，未删除已有文件或测试记录。

如需复现同一界面，可由负责人在项目根目录启动：

```powershell
$env:P1_CLOSURE_WRITES='1'
$env:P1_CLOSURE_DB='D:\Projects\agent-framework\.codex_artifacts\p1\e2e-final-20260831.sqlite3'
.\.venv\Scripts\python.exe -B -X utf8 -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

前端目录另开终端：

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
npm run dev -- --strictPort
```

这份数据库含合成测试记录，不能当作真实市场成果。重新跑八场景应选择一个全新项目内 `.sqlite3` 路径，不要删除或覆盖已有验收库。

测试命令：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v
```

```powershell
npm test
npm run build
$env:P0_PLAYWRIGHT_MODULE='C:\Users\H\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright'
node --test tests/p0.browser.cjs
node --test tests/p1.browser.cjs
```

## 18. 安全确认

- 未 commit、未 push、未 pull/fetch/merge/rebase。
- 未创建 PR，未访问或修改 GitHub。
- 未部署 Vercel/Render，未修改部署配置或生产环境变量。
- 未访问/修改生产数据库，未写入线上正式数据。
- 未修改真实 JD、真实简历原始数据、冻结词典或冻结输出。
- 仅本地实现、合成数据测试和只读冻结数据验证。完成后停止，等待人工验收。

## 19. 发布画像下游生效机制

### 19.1 本次基线与只读定位

本次开始分支为 `feature/p1-core-closure`，HEAD 为 `1b830af`。开始时已有上轮 P1 的 6 个已跟踪修改文件和 13 个未跟踪文件，并非干净工作区；全部保留，没有覆盖、撤销或提交。仅完成发布画像下游接入，没有开始 P2。

| 原实现 | 集成缺口 | 本次接入 |
| --- | --- | --- |
| MatchingEngine 从静态 JD 聚合岗位必备/加分技能 | 已发布画像未参与评分 | 评分前调用统一有效画像服务 |
| GraphAdapter 从冻结图谱读取岗位—技能边 | 发布后图谱仍是旧关系 | 内存覆盖该岗位的能力边，不改冻结文件 |
| ClosureService 在 entities.payload.publications 保存发布快照 | 页面另行读取；没有统一下游选择 | 只读 repository 读取现有发布快照 |
| 岗位分析页独立显示发布结果 | 正式数据和展示结果可能不一致 | 与匹配/图谱共用服务及版本标识 |

### 19.2 Effective profile 选择规则

统一入口为 `src/core/effective_profiles.py` 的 `EffectiveJobProfiles.get_effective_job_profile`；持久化读取由 `src/closure/repository.py` 负责。页面不自行挑选版本。

1. 只从实体的 `publications` 发布快照中读取，同时要求 `status=published`、`origin=human_approved`，选最大 `profile_version`。
2. 计算更新时自动初始化的 `legacy_baseline` 不是人工 publish，不触发下游切换；无人工发布时继续原静态基线。
3. 候选的 draft/candidate、pending_review、approved 但未发布、rejected 内容版本均不参与读取。新草稿也不能覆盖旧发布快照。
4. 已发布快照存在时使用其中的人工定义（如有），否则使用自动定义。不读取最新未发布的人工编辑。
5. 标准岗位按原岗位标识匹配；新岗位按已发布名称接入。标准岗位画像优先于同名候选；多个候选发布为同名且无法明确身份时显式报错，不随意混合。
6. 每次业务请求读取当前发布快照，不缓存启动时的版本。发布后下一次请求即可生效，无需重启；关闭本地写开关也不关闭已发布画像的读取。
7. companion DB 不存在或岗位没有人工发布记录时，返回原静态画像；只读连接不会创建数据库。数据库损坏/读取失败等异常返回明确 503，不静默使用过期基线冒充最新画像。

匹配、岗位分析、岗位图谱统一追加 `profile_source`、`profile_version`、`profile_id`、`profile_fingerprint`。来源为 `published_dynamic` 或 `static_baseline`；静态基线版本为 null，不编造 V1。一次岗位分析请求将同一有效快照传给图谱，避免该请求内部重复选版。多岗位技能反向查询携带岗位版本映射及边的版本信息，而非假定全图只有一个版本。

### 19.3 人岗匹配如何使用发布版本

- 必备技能、加分技能从发布定义提取标准 ID，按 ID 去重；同一技能同时出现时必备优先。
- 保留原 P0“每个不同技能一次贡献”的评分设计，没有将多条 evidence 累加为多个满额贡献，没有另改评分权重。现有 frequency 字段用于缺口排序，coverage 用于图谱证据强度，不解释为本人掌握概率。
- 已有岗位的学历/经验要求保留静态基线字段；新岗位无这些证据时保持 unknown/null，不新增默认 50 分。
- 无发布画像时直接使用原静态匹配数据，自动测试逐字段比较原 P0 结果（仅排除新增来源元数据），不是只比较近似总分。
- P0 否定/计划/他人技能隔离、空表单、unknown、去重、项目及综合分边界均继续生效。

### 19.4 图谱如何使用发布版本

- 在静态图谱的内存副本上，仅替换目标岗位的 `Job_Skill / requires_skill / prefers_skill` 能力关系；发布定义不再包含的旧能力边不会残留。
- 企业、来源、其他岗位等非目标能力关系保留；未发布岗位继续原关系。新增已发布岗位可形成对应岗位节点。
- 正向岗位查询和反向技能查询都接入有效画像。动态边保留覆盖率、支持 JD、证据片段和发布版本标识。
- 原 `load()` 冻结读取接口和用于冻结数据 QA 的全量统计保持不变；运行时能力查询通过 `load_effective/for_job/for_skill` 接入。这不是重建或覆写图数据库。
- 匹配、图谱、岗位分析页统一展示后端返回的来源标签。图谱只在已有岗位下拉列表加入已发布岗位，没有增加筛选功能。
- 图谱 tooltip 改为 ECharts richText 文本渲染，避免人工名称或 evidence 被作为 HTML 执行；其他 React 转义与安全链接处理保留。

### 19.5 本次文件变更与兼容性

本次新增 6 个文件：

- `src/closure/repository.py`：既有发布快照的只读访问与数据库路径校验。
- `src/core/effective_profiles.py`：统一版本选择及匹配结构适配。
- `frontend/src/components/ProfileSourceBadge.tsx`：统一来源/版本标签。
- `tests/test_effective_profiles.py`：13 个后端回归测试。
- `frontend/tests/effective-profile.test.mjs`：2 个前端标签测试。
- `frontend/tests/effective-profile.browser.cjs`：4 个真实浏览器/HTTP 集成测试，覆盖六个版本状态。

本次修改已有文件（含上轮尚未跟踪的文件）12 个：

- `src/api/closure.py`：复用同一 companion DB 路径解析；不改本地写保护。
- `src/core/matching_engine.py`：匹配前解析有效画像，追加版本元数据。
- `src/schemas.py`：MatchResult 追加可兼容的来源/版本/ID/fingerprint 字段。
- `src/integration/graph_adapter.py`：岗位能力关系覆盖、反向查询和版本证据。
- `src/integration/system_data.py`：岗位分析共用同一有效画像。
- `src/api/app.py`：岗位列表与岗位分析接入、发布读取异常处理。
- `frontend/src/types.ts`：可选版本元数据类型。
- `frontend/src/pages/MatchPage.tsx`：展示当前匹配画像来源。
- `frontend/src/pages/GraphPage.tsx`：已发布岗位入口、来源标签、安全 tooltip。
- `frontend/src/pages/JobAnalysisPage.tsx`：展示服务器选择的发布快照。
- `frontend/src/components/ClosurePanel.tsx`：发布画像展示不再独立请求或挑选版本。
- `docs/p1_core_closure_report.md`：保留原交付记录并追加本节。

没有数据库 schema 变更、存储迁移、新依赖或新增 REST 路由。原 API 路径与已有字段保留，来源元数据为新增字段；有发布时岗位技能内容按本次需求变化，无发布时原 P0 行为不变。未修改 ClosureService 的编辑/审批/发布状态机、既有 P0/P1 测试、部署配置、锁文件或原始数据。

### 19.6 测试先行与新增测试

先新增实际服务回归测试，确认新有效画像模块缺失导致失败，再实现服务和接入；测试调用真实 ClosureService、MatchingEngine、GraphAdapter，使用隔离临时 SQLite，不用 mock 分数。后续补充数据库损坏测试，修正测试自身未关闭 SQLite 连接造成的 Windows 清理失败后通过。

13 个 Python 测试名称（`tests/test_effective_profiles.py`）：

```text
test_01_no_publication_matches_p0_exactly
test_02_published_v1_used_by_real_match
test_03_latest_v2_adds_langgraph_to_match
test_04_05_pending_approved_rejected_v3_do_not_change_downstream
test_06_preferred_and_p0_polarity_bounds
test_07_no_publication_graph_static_unchanged
test_08_graph_v2_and_reverse_skill_lookup
test_09_only_job_skill_edges_replaced
test_10_legacy_baseline_is_not_a_publish_action
test_11_missing_database_is_not_created_on_read
test_12_publish_visible_without_restart_and_with_writes_disabled
test_13_standard_profile_update_publishes_to_both_consumers
test_14_corrupt_store_does_not_silently_fallback
```

新增前端 2 个测试验证实际标签显示服务器选定的 published version，以及无发布时 static baseline/null。新增浏览器 4 个测试验证 V1、V2 待审/批准/发布、V3 待审/驳回和零页面错误，实际请求匹配、图谱及岗位分析并比较版本与 fingerprint。

首次新浏览器测试 API 状态断言通过，但图谱下拉定位超时；确认是包裹式 label 的精确文本定位不匹配后，改为页面唯一 combobox 定位，完整重跑 4/4 通过。没有忽略页面错误或削弱业务断言。

### 19.7 最终全部验证结果

| 验证 | 最终结果 |
| --- | --- |
| Python 全量 unittest | **88/88 PASS**（此前 75 全保留 + 新增 13） |
| 前端 npm test | **12/12 PASS**（此前 10 + 新增 2） |
| P0 Browser | **8/8 PASS** |
| 原 P1 Browser | **8/8 PASS** |
| 新发布画像 Browser | **4/4 PASS**，六状态断言及页面 errors=[] |
| 集成 QA | **11/11 checks PASS**，14 个既有接口本地 HTTP 200 |
| TypeScript + frontend build | **PASS**，tsc -b && vite build，2225 modules |
| git diff --check | **PASS**，exit 0，仅 Windows LF/CRLF 提示 |

本次新增测试共 19 个：Python 13 + 前端 2 + 浏览器 4。构建仍提示原有大 chunk（JS 1436.82 kB），不影响成功，本轮未扩展打包优化。

P0 浏览器在隔离、尚无人工发布的数据库上复测：空简历技能 0/总分 0；默认样例总分 40.67、项目分 26.67；删去技能清单后总分 37.33、项目分仍 26.67。原冻结数据仍为 JD 191、简历 27、冻结技能 82（运行时 84），四个冻结文件校验均未变化。

### 19.8 本地端到端版本切换

使用实际 FastAPI、React、Edge 和明确标记的合成岗位 `合成发布版本验证岗位1788182893242`。候选人正向技能仅 Python、RAG；V2 增加必备 LangGraph，V3 再编辑加入 Docker。没有重启服务促使版本切换。

| 当前操作后状态 | 匹配/图谱正式版本 | 必备技能匹配分 / 综合分 | 缺口 | 图谱技能 | 结果 |
| --- | --- | --- | --- | --- | --- |
| V1 已发布 | V1 | 100 / 100 | 无 | Python、RAG | PASS |
| V2 pending | V1 | 100 / 100 | 无 | Python、RAG | PASS |
| V2 approved，尚未 publish | V1 | 100 / 100 | 无 | Python、RAG | PASS |
| V2 published | V2 | 66.67 / 66.67 | LangGraph | Python、RAG、LangGraph | PASS |
| V3 pending | V2 | 66.67 / 66.67 | LangGraph | Python、RAG、LangGraph | PASS |
| V3 rejected | V2 | 66.67 / 66.67 | LangGraph | Python、RAG、LangGraph | PASS |

所有状态的匹配、岗位图谱、岗位分析均返回相同发布版本及 fingerprint。这里综合分采用原 P0 可评估维度归一化规则；新岗位学历/经验缺失仍为 unknown，并非宣称候选人真实能力达到 100%。V2 图谱截图已检查，可见 4 节点、3 关系、三项必备技能及“已发布画像 V2”。

本次本地机器结果与保留产物：

- `.codex_artifacts/p0/browser-results.json`：重跑原 P0 浏览器。
- `.codex_artifacts/p1/browser-1788182744552/results.json`：重跑原 P1 八场景。
- `.codex_artifacts/p1/downstream-1788182893242/results.json`：新增浏览器最终四测试及六状态结果，同目录保存匹配/图谱截图。
- `.codex_artifacts/p1/downstream-system-qa-final/正式图谱动态接入QA结果.md`：集成 QA 输出。仍遵守第 13 节关于模板文字与实际断言的区分。
- `.codex_artifacts/p1/downstream-integration-20260831.sqlite3`：原 P1 复测及首次新浏览器运行所用隔离数据库，保留未删除。
- `.codex_artifacts/p1/downstream-final-20260831.sqlite3`：新浏览器最终完整复测的隔离数据库，V2 发布、V3 驳回。

如需复现最终截图，按第 17 节启动方式将 `P1_CLOSURE_DB` 指向上述 downstream-final 数据库。只读取已发布结果不要求 `P1_CLOSURE_WRITES=1`；写开关仅供主动本地编辑/审批验收。新测试命令为 `node --test tests/effective-profile.browser.cjs`，仍使用既有 P0_PLAYWRIGHT_MODULE 环境。重跑完整写场景须另选新项目内数据库，不覆盖保留证据。

### 19.9 最终 Git 状态与范围检查

分支仍为 `feature/p1-core-closure`，HEAD 仍为 `1b830af`。下列为累计 P1 工作区统计，包含本次开始前已有修改，不将其冒充全部由本次新增。未执行 git add，因此 diff --stat 不计未跟踪文件。

```text
 frontend/package.json                  |  2 +-
 frontend/src/api.ts                    |  5 +--
 frontend/src/pages/EmergingPage.tsx    |  2 ++
 frontend/src/pages/EvolutionPage.tsx   |  2 ++
 frontend/src/pages/GraphPage.tsx       | 12 ++++---
 frontend/src/pages/JobAnalysisPage.tsx | 14 ++++++--
 frontend/src/pages/MatchPage.tsx       |  5 +--
 frontend/src/types.ts                  |  4 +--
 src/api/app.py                         | 23 ++++++++++++-
 src/core/matching_engine.py            | 20 ++++++++---
 src/integration/graph_adapter.py       | 61 +++++++++++++++++++++++++++++++---
 src/integration/system_data.py         | 19 ++++++++---
 src/schemas.py                         |  4 +++
 13 files changed, 146 insertions(+), 27 deletions(-)
```

最终 `git status --short --untracked-files=all`（13 个 tracked 修改、19 个 untracked 文件）：

```text
 M frontend/package.json
 M frontend/src/api.ts
 M frontend/src/pages/EmergingPage.tsx
 M frontend/src/pages/EvolutionPage.tsx
 M frontend/src/pages/GraphPage.tsx
 M frontend/src/pages/JobAnalysisPage.tsx
 M frontend/src/pages/MatchPage.tsx
 M frontend/src/types.ts
 M src/api/app.py
 M src/core/matching_engine.py
 M src/integration/graph_adapter.py
 M src/integration/system_data.py
 M src/schemas.py
?? docs/p1_core_closure_report.md
?? docs/p1_implementation_map.md
?? frontend/src/closure.ts
?? frontend/src/components/ClosurePanel.tsx
?? frontend/src/components/ProfileSourceBadge.tsx
?? frontend/src/components/closure.css
?? frontend/tests/effective-profile.browser.cjs
?? frontend/tests/effective-profile.test.mjs
?? frontend/tests/p1.browser.cjs
?? frontend/tests/p1.test.mjs
?? src/api/closure.py
?? src/closure/__init__.py
?? src/closure/evidence.py
?? src/closure/repository.py
?? src/closure/service.py
?? src/core/effective_profiles.py
?? tests/test_effective_profiles.py
?? tests/test_p1_api.py
?? tests/test_p1_closure.py
```

已检查没有全项目格式化、无关部署变更、新依赖或覆盖 P0/P1 成果。本次集成问题已解决；第 16 节其他生产认证、数据质量和 P2 边界不扩展。

本轮前后端本地验收服务已停止，保留数据库、截图和测试结果。未 commit、未 push、未部署，未访问 GitHub，未访问生产数据库或写入线上正式数据。完成后停止，等待人工验收。
