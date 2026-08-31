# P2 数据科学性与输入能力增强报告

日期：2026-08-31。项目：D:\Projects\agent-framework。
**本轮已交付数据科学性增强与独立评测框架；PDF/DOCX 实际解析因现有依赖缺失未实现，仅交付接口边界和明确支持状态。不能将本报告解释为文件解析全部完成或业务准确率达标。**

## 1. 基线、原问题与范围

- 分支：feature/p2-enhancement；开始工作区干净。
- HEAD：0f0c88a feat: complete P1 core job profile closure。
- 最近五次提交：0f0c88a、1b830af、5c97d32、9a45848、4280d7f。没有切换、同步或改写分支。
- 保留 P0 正确性、P1 审核发布闭环及 effective profile 下游机制。
- 原静态演化 Adapter 直接信任 artifact 分类；AI Agent 前窗 1 条、后窗 11 条仍可能显示下降。P1 新更新闭环已有双窗口保护，本轮没有重构它。
- 原时间信息混在 artifact meta 中；来源存在明显等价写法；没有只读近重复检测/独立证据估计。
- 没有可用 PDF/DOCX 解析依赖；存在旧人工参考字段，但不等于独立真实评测集。
- 没有扩展 OCR、LLM、图谱筛选、学习路径、数据库产品、部署或整体 UI。

## 2. 数据安全与完整性 Gate

开始前识别并记录 63 个现有数据类文件：Excel/CSV/JSON/NDJSON/SQLite/PDF/DOCX 范围内实际存在的文件，包括旧验收 JSON 和 5 个旧验收数据库。依赖、Git、构建输出及明确测试目录排除。保守清单也覆盖未修改的配置 JSON。

- 完整 before：docs/p2_data_integrity_before.md。
- 完整 after：docs/p2_data_integrity_after.md。
- **63/63 个原文件路径、大小、SHA-256 一致；0 个修改；0 个删除。**
- 原有业务数据文件集合未增加或减少。额外 6 个 JSON 都是新的 ignored 验收输出，after 清单单列其路径。
- 新增合成数据全部在 tests/fixtures/p2_synthetic，文件名带 synthetic，元数据/说明含 SYNTHETIC TEST DATA / NOT REAL RECRUITMENT DATA。
- 新 fixture 不含真实个人姓名、电话、邮箱、身份证，不冒充真实企业招聘。BOSS 字符串仅测试既有来源别名。
- 所有写库测试使用 tempfile/TemporaryDirectory。浏览器后端通过 tests/p2_local_server.py 强制选择全新项目内临时库；没有使用旧业务库或旧验收库。
- 原 P0 浏览器允许指定全新 P0_ARTIFACT_DIR，避免覆盖旧 browser-results.json。P1 原脚本每次使用新时间戳目录。
- 既有测试仍只读冻结数据做兼容检查；本轮新增逻辑案例使用合成输入。无原始数据写回、导入、迁移、重排或清洗覆盖。
- 原始数据保护是哈希实测结论，不仅是 Git 状态推断。

## 3. 动态演化与时间语义

统一只读逻辑在 src/quality/science.py，接入 src/integration/evolution_adapter.py。

- 复用现有 artifact 的 config.min_jd_count=3；无该字段时工程兼容默认值也是 3。guard_evolution 接收明确 minimum 参数并有测试。没有修改现有配置文件。
- 从 records 的时间窗口和 JD数量读取前后窗口，不能用支持 JD 总数替代。两窗任一不足、缺失或窗口样本计数冲突，返回 insufficient_sample。
- 返回 window_samples.before/after/minimum；不足时增长、新增、稳定、下降分类均不输出。历史行也做保护，避免客户端绕过聚合字段误用。
- 样本充分时只保留原记录已有的分类和频率，不重新创造长期市场结论。达到 3 条仅为工程保护，不代表统计显著。
- 前端静态 fallback 可能尚无已验证双窗口元数据：明确隐藏趋势分类，并显示原因；不改写静态 JSON。
- P1 Change Set 的既有双窗口保护与发布审批逻辑完全保留。

质量读取通过现有 DataLoader 的只读工作簿入口，但不走会 trim 原文的 P1 normalize_record。source/company 原始空白、非法日期和原始 first_seen 值保留在内存派生记录中；源文件不动。

- published_at：有效标准招聘发布时间。
- collected_at：采集时间。
- first_seen_at：首次发现时间，缺失保持 null；当前冻结表无对应列时不伪造。
- 发布时间有效则优先，否则仅以有效采集时间作为 collected_at_fallback；两者无效为 unknown，不拿 first_seen 冒充招聘日期。
- 日期校验拒绝非法尾缀，不仅截取前 10 字符。
- 输出 total_jobs、published_at_count、fallback_count、unknown_time_count、published_at_coverage、time_quality。
- 时间质量：空数据 unknown；全部有效发布 high；覆盖率≥现有 0.60 门槛为 medium；其余 low。这是可解释工程标签，不是统计置信区间。
- 页面明确显示“部分记录缺少原始发布时间，趋势计算使用采集时间回退”。

## 4. 来源、企业与重复检测

### 名称规范化

- 来源最小映射仅为现有数据中的 BOSS直聘官方招聘 → BOSS直聘；未知来源保持原值（规范化字段可去首尾空白）。
- 企业仅 Unicode NFKC 全半角、首尾/重复空白、大小写规范化。
- 不删除法律后缀，不推断集团/子公司关系，不合并不确定企业。
- 原值保存在 source_raw/company_raw，规范化值另存 source_normalized/company_normalized；不替换原字段或原数据。
- 来源统计变化仅在新增派生质量报告中展示，旧 overview 原始来源计数、P1 confidence 和评分不改。

### Exact / near duplicate

- 比较职责、必备技能原文、加分技能原文三段文本。
- 先要求明确相同的规范化企业和标题；未知企业不猜测合并，不同企业即使职责相似也保持分开。
- 原三段文本完全一致为 exact（在相同企业/标题条件下）；仅标点空白等变化、规范化正文高度相似为 near。
- NFKC + 大小写 + 去非字母数字字符，构造字符二元组，使用 Jaccard。
- 默认阈值 0.90，独立常量并可作为函数参数配置；是工程初始值，未经过真实市场校准。
- Complete linkage 要求组内每对都达到门槛，避免 A≈B、B≈C 却 A≠C 的链式过度合并。顺序按原 ID 排定，稳定可复现。
- 输出 group ID、duplicate_type、score、canonical_candidate_id、所有支持原 job_id。
- canonical_candidate 只是代表候选，不删除、不自动 merge、不改 job_id/raw text/source。
- raw_evidence_count 为所有原行数；independent_evidence_count 为保守组数估计，不等于已验证统计独立性。
- exact_duplicate_count 为完全重复的冗余条数，near_duplicate_group_count 为含非完全相同正文的重复组数，报告中明确单位。

当前冻结 JD 只读结果见 docs/p2_data_quality_report.md：191 条；有效发布时间 93；回退 97；无有效时间 1；发布覆盖率 48.6911%；来源 30→29；企业 105→105；exact 冗余 0、near 组 0、独立估计 191。**未检出重复不等于无转载。**
当前质量报告覆盖 191 条冻结 JD，不混入临时测试增量；旧演化 artifact meta 是不同版本/子集的分母，不与当前覆盖率混算。

## 5. PDF/DOCX：支持边界、依赖 proposal 与安全

检查本项目 .venv 和 requirements.txt：没有 pypdf、pdfplumber、PyMuPDF、python-docx、reportlab、python-multipart。没有 npm/pip install，也没有借其他运行时库伪装项目已经支持。

已交付：
- parse_file(filename, mime, content) 接口边界及能力查询 API。
- 扩展名与 MIME 一致性检查、拒绝宏扩展名/路径式文件名、5 MiB 文件体限制、空文件错误。
- API 以分块读取限制总长度；只在内存中处理，不创建文件或写数据库。
- 合法非空 PDF/DOCX 当前返回 501 / DEPENDENCY_REQUIRED，而非空文本解析成功。
- 非法类型 415、空文件 422、超大文件 413；保留现有纯文本解析 API。
- 简历页面显示禁用的 PDF/DOCX 入口和依赖待批准说明，不会自动上传；现有文本仍可编辑后主动解析/匹配。

**未实现/未宣称通过：文本型 PDF 或 DOCX 内容提取、文件结构化预览、文件确认后匹配、扫描件 OCR_REQUIRED 检测、压缩包/页数/抽取文本上限的实际解析验证。** MAX_TEXT_CHARS=100000 仅为未来 adapter 契约，当前全部文件未进入解析，不将它冒充已验证的长文本保护。
不执行宏、脚本、附件或外链；当前不调用任何文档解析引擎。

Dependency proposal（待人工决定，不自动安装）：

| 包名 | 用途 | 为什么需要 | 替代方案 |
| --- | --- | --- | --- |
| pypdf | 文本型 PDF 提取 | 标准库无可靠 PDF 解析，不能用简单正则冒充 | 继续粘贴文本；或团队批准已评审的等价 PDF 库 |
| python-docx | DOCX 段落/表格文本提取 | 需成熟文档结构处理和明确资源限制 | 继续文本；标准库 zip/xml 方案需要另行实现防 zip bomb/结构校验，不在本轮伪装完成 |
| python-multipart（可选） | 常规 multipart 上传 | 当前缺失；本轮原始二进制 API 不依赖它 | 保持二进制 body，不必为接口额外安装 |

未来真正接入必须：文本提取→可编辑预览→P0 polarity→用户确认→既有匹配；无文本 PDF 提示 OCR_REQUIRED，不安装 OCR；加上损坏/加密/恶意文档与解压、页数、超长文本资源保护。

## 6. 独立量化评测框架

evaluation/ 与业务 extractor/matching 分离。只输入 gold/predictions，不从 gold 改抽取规则，不按 ID 返回标准答案，不改原标签。

- 技能用同一记录内的 (skill, polarity) 集合计算 TP/FP/FN，重复证据不重复计数。
- Precision=TP/(TP+FP)，Recall=TP/(TP+FN)，F1=2TP/(2TP+FP+FN)。
- 另提供 affirmed-only 指标；gold negated 预测 affirmed 会成为正向 FP，绝非正向 TP。
- 字段 education/experience/job_title 等通用字段支持 Exact Match/Accuracy；字段缺失代表未标注，显式 null 代表标注 unknown；预测缺字段不自动等于 null 正确。
- 缺预测样本保留为错误，额外预测技能计 FP；重复 ID、空技能名、非法极性拒绝。
- 零分母为 null，不将空 gold/空预测说成 100%。
- 输出每条错误的 ID、FP、FN、字段 gold/prediction 和字段存在状态，不选择有利子集。
- CLI 仅向 stdout 输出，不覆盖业务文件。

仓库**存在** 27 条标准化测试简历及修订后人工参考字段；旧设计明确这不是完整技能 Gold Standard，当前规则也复用正式数据。因此不能声称仓库完全没有标注，也不能把它当独立真实业务评测集。没有修改、重标、追加或挑选其标签，没有把参考技能字符串自动变成五极性真值。

**BLOCKER / 独立真实标注数据及其来源、任务适用性、训练/验证隔离待团队提供或确认。**
**当前未产生真实业务准确率结论。Synthetic regression result ≠ Real-world accuracy。没有 ≥90% 声明。**

合成算术示例故意设置一个 Docker 极性错误：TP=1、FP=1、FN=1，因此 P/R/F1 各 0.5，错误案例显示误报 affirmed 和漏报 negated。这仅验证评测程序数学，不是系统业务成绩。

## 7. API 与 UI 变化

新增只读/无持久化接口：
- GET /api/quality/report：当前冻结数据质量派生结果。
- POST /api/quality/preview：请求中的独立数据计算，不导入任何数据；重复/非法 ID 422。
- GET /api/resume/file/capabilities：真实支持状态。
- POST /api/resume/file/preview?filename=...：有界二进制接口，当前依赖缺失返回明确错误，不匹配、不存储。

原 evolution API 追加 trend_status、window_samples、data_quality，保护不充分的旧分类；原匹配/画像发布 API 与评分 schema 未改。
Dashboard 和 Evolution 只增加质量区块；Resume 页面只增加诚实的文件支持提示。无导航、整体样式、图谱或部署重构。

## 8. 测试先行与结果

先增加质量/评测测试，确认缺少新模块而失败；再实现。新增前端提示及文件边界测试同样先失败后通过。没有引入新测试框架。

唯一旧行为断言修正：
- test_system_integration 原本要求 AI Agent sample_insufficient=False，与本轮修复目标直接冲突。
- 全量测试先真实失败，再将该断言改为 sample_insufficient=True，并增加精确 1/11/3 及 declining_skills=[] 检查。
- run_system_qa 对应条件同步加强。没有更改原始演化 JSON 或 Gold。
- P0/P1 核心测试和发布版本切换测试未削弱；P0 浏览器仅新增可配置结果目录。

新增后端 **38 项**：
- test_p2_quality.py：20 项，A01–A15、原始值保留、空正文、未知窗口、实际 Adapter 只读接入等。
- test_p2_evaluation.py：11 项，C01–C07、unknown/缺字段、空集合、重复 ID 与非法极性。
- test_p2_input.py：7 项，能力状态、非法/空/超大文件、依赖缺失、实际 ASGI 二进制拒绝、只读预览校验。
- P2-B01/B02/B06/B07/B08 的“从文件提取”场景因缺依赖未执行；文本 polarity 已在原 P0 及新浏览器验证，不冒充文件验收。

前端新增 3 项，浏览器新增 4 项（文件项只验证 blocker 提示及原文本流程），本轮新增自动测试共 **45 项**。

| 验证 | 结果 |
| --- | --- |
| Python 全量 | **126/126 PASS**，既有 88 + 新增 38 |
| 前端 npm test | **15/15 PASS**，既有 12 + 新增 3 |
| P0 Browser | **8/8 PASS** |
| P1 Browser | **8/8 PASS** |
| P1 effective profile Browser | **4/4 PASS** |
| P2 Browser | **4/4 PASS**；不是 PDF/DOCX 解析通过 |
| 集成 QA | **11/11 checks PASS**，14 个旧 API 本地 HTTP 200 |
| TypeScript + frontend build | **PASS**，tsc -b && vite build，2227 modules |
| 数据污染 gate | **63/63 hash 一致，0 修改** |
| git diff --check | **PASS**，exit 0，只有 Windows LF/CRLF 提示 |

没有项目现成 lint/typecheck 独立脚本；TypeScript 由 build 完成。构建保留既有大 chunk 提示（约 1439.88 kB），未扩展性能改版。
QA 原模板含移动端/后端关闭等固定说明，本轮只把实际断言视为证据，不将模板文字当另行实测。

P0 空白技能/总分为 0；unknown 仍不计默认分。默认样例总分 40.67、项目 26.67；删技能清单后总分 37.33、项目仍 26.67。P1 发布 V2 后匹配/图谱切换、V3 pending/rejected 仍保持 V2。

## 9. 六个 P2 本地端到端场景

| 场景 | 实际结果 |
| --- | --- |
| 1 前窗口少量 JD | 合成 1→11、阈值3；insufficient_sample、无下降，页面明确显示两窗计数；PASS |
| 2 发布时间缺失 | 合成12条全部 collected_at_fallback；页面显示回退说明与0%发布时间覆盖；PASS |
| 3 近重复两条 | 保留2条原记录，near group1、独立估计1；PASS |
| 4 明确不同 JD | 不分到同组，独立估计2；PASS |
| 5 文件→预览→确认→匹配 | **BLOCKER：缺解析依赖，未执行实际文件链路**。禁用入口/错误状态验证通过；原文本手动输入→解析/确认→匹配保持 Docker negated、RAG planned、SQL affirmed |
| 6 评测算术 | 实际 CLI 输入合成 gold/prediction，TP=1、FP=1、FN=1、P/R/F1=.5，错误详情正确；PASS，仅数学验证 |

P2 浏览器使用 tests/p2_local_server.py --synthetic-quality，把真实 Adapter 的数据源替换为临时合成窗口，不改生产代码/原文件。浏览器外部 URL 全阻断；未打开真实招聘链接。synthetic-window.png 已视觉检查：无下降技能、双窗口、fallback 与独立证据提示可见。

结果路径（均为 ignored 派生验收输出）：
- .codex_artifacts/p2/p0-regression-20260831/browser-results.json
- .codex_artifacts/p1/browser-1788186643592/results.json
- .codex_artifacts/p1/downstream-1788186750807/results.json
- .codex_artifacts/p2/browser-1788186754324/results.json
- .codex_artifacts/p2/system-qa-final-20260831/正式图谱动态接入QA结果.md

## 10. 修改与新增文件

修改 9 个已跟踪文件：
- frontend/src/pages/DashboardPage.tsx：质量报告区块。
- frontend/src/pages/EvolutionPage.tsx：窗口/时间质量提示及旧静态降级保护。
- frontend/src/pages/ResumeParsePage.tsx：文件支持边界。
- frontend/tests/p0.browser.cjs：结果目录可配置，避免覆盖旧记录。
- src/api/app.py：挂载只读质量及能力 API。
- src/integration/evolution_adapter.py：旧演化双窗口保护。
- src/integration/system_data.py：只读质量入口及原值读取。
- tests/run_system_qa.py：加强 P2 样本约束断言。
- tests/test_system_integration.py：更正并加强旧不安全样本断言。

新增 29 个文件（也是最终全部 untracked 文件）：

```text
docs/p2_data_integrity_after.md
docs/p2_data_integrity_before.md
docs/p2_data_quality_report.md
docs/p2_enhancement_report.md
evaluation/README.md
evaluation/__init__.py
evaluation/__main__.py
evaluation/metrics.py
frontend/src/components/DataQuality.tsx
frontend/src/components/FileSupportNotice.tsx
frontend/tests/p2.browser.cjs
frontend/tests/p2.test.mjs
src/api/quality.py
src/core/resume_files.py
src/quality/__init__.py
src/quality/__main__.py
src/quality/loader.py
src/quality/science.py
tests/fixtures/p2_synthetic/.gitignore
tests/fixtures/p2_synthetic/README.md
tests/fixtures/p2_synthetic/synthetic_browser_fixture.json
tests/fixtures/p2_synthetic/synthetic_fixture.py
tests/fixtures/p2_synthetic/synthetic_gold.json
tests/fixtures/p2_synthetic/synthetic_predictions.json
tests/p2_integrity.py
tests/p2_local_server.py
tests/test_p2_evaluation.py
tests/test_p2_input.py
tests/test_p2_quality.py
```

没有真实 JD/简历、SQLite、node_modules、dist、日志、下载文件或结果缓存进入待提交清单。唯一新增 JSON 为明确位于测试目录的 synthetic fixtures。

## 11. 最终 Git 检查

分支 feature/p2-enhancement，HEAD 0f0c88a，未 commit。

git diff --stat（不含未跟踪文件）：

```text
 frontend/src/pages/DashboardPage.tsx   |  2 ++
 frontend/src/pages/EvolutionPage.tsx   |  6 ++++--
 frontend/src/pages/ResumeParsePage.tsx |  3 ++-
 frontend/tests/p0.browser.cjs          |  3 ++-
 src/api/app.py                         |  2 ++
 src/integration/evolution_adapter.py   | 15 ++++++++++++---
 src/integration/system_data.py         |  7 ++++++-
 tests/run_system_qa.py                 |  5 ++++-
 tests/test_system_integration.py       |  6 +++++-
 9 files changed, 39 insertions(+), 10 deletions(-)
```

git diff --check：exit 0。
git status：以上 9 个 tracked 修改，29 个 untracked 文件；无暂存文件。
git ls-files --others --exclude-standard：与第10节完整新增列表一致。
未批量格式化；未修改依赖/lockfile、部署、正式配置或 P0/P1 存储与评分模块。

## 12. 尚待团队决定与 P3

- **P2 blocker**：批准解析库后，才能实现真实 PDF/DOCX 提取、结构化预览及确认闭环；当前不声称完成此项。
- **评测 blocker**：独立真实标注集、来源授权、任务定义和数据隔离待团队提供/确认；无真实业务准确率结论。
- 后续 P3：近重复阈值的独立校准、跨企业转载复核、来源实体治理、时间数据补充、统计显著性研究、规模化索引/性能；本轮不展开。
- 生产认证/审批权限、部署、多用户并发硬化、OCR、LLM、UI整体改版不在本轮。
- 本地前后端验收服务均已停止，8000/5173 无残留监听。合成临时目录由测试管理，旧数据库均未动。

## 13. 安全确认

- 未自行搜索外部业务数据，未访问 GitHub 获取数据。
- 未下载 JD、真人简历或数据集，未爬取招聘网站，未添加网络数据。
- 未修改任何原始业务 Excel、JSON 或现有业务数据库；63 项哈希实测一致。
- 新测试输入仅 synthetic / temporary data；既有回归只读原冻结数据，写库只在隔离临时库。
- 未安装依赖、未 commit、未 push、未创建 PR、未部署。
- 未访问生产数据库、未修改生产环境变量、未运行生产写接口。
- 没有伪造 ≥90% 指标；文件能力缺口和真实标注 blocker 如实保留。

完成本轮可交付范围后停止，等待人工验收。

