# P0 正确性修复交付报告

日期：2026-08-31。状态：本地修复和验证完成，等待人工验收；未提交、未推送、未部署。

## 1. 项目基线及工作范围

- 实际目录：`D:\Projects\agent-framework`。
- 分支：`fix/p0-correctness`；开始 HEAD：`5c97d32`（deploy: add production API and CORS configuration）。结束未移动 HEAD。
- 开始工作区干净；未覆盖他人修改。没有访问旧仓库或 GitHub。
- 前端：frontend/src/pages、components，React 19 + TypeScript + Vite + ECharts。
- 后端：src/api/app.py → src/api/service.py → JDParser / ResumeParser / SkillIndex / MatchingEngine。
- 数据：DataLoader 只读冻结工作簿；本轮未更改数据库、部署文件、生产环境变量或原始 JD/简历数据。
- 按用户要求先运行失败回归，再修最小实现。过程见 `p0_correctness_worklog.md`。

## 2. P0 根因及修复

| 问题 | 经源码与失败测试确认的根因 | 修改位置及处理 |
| --- | --- | --- |
| 隐藏示例污染 | JDParsePage 的 initial 含未渲染 bonus_skills_raw；MatchPage 含未渲染 work_experience，submit 把 state 全展开；三个页面自动载入示例 | 三页默认空表单；增加显式加载示例和清空；bonus/work 字段可见可编辑；formPayloads 使用明确字段白名单。后端输入原本默认空，不新增演示回填 |
| 否定/计划/他人算本人技能 | SkillIndex.extract_fields 名称/别名命中后恒 accepted=True，无主体或极性 | skill_context.py 数据化中文提示规则；五类 polarity；只有 affirmed 且 accepted 才进入正向列表和评分；uncertain 人工复核 |
| SQL/FastAPI 漏识别 | 冻结词典82项及别名确实没有 SQL/FastAPI；有 MySQL/PostgreSQL，不能等价代替 SQL | 增量 JSON 补 SQL、FastAPI、Fast API；原82个ID不变。运行时共84项，冻结文件仍82项；禁止冲突覆盖 |
| 项目分133.33 | MatchingEngine.match 分母 min(3, 必备技能数)，分子却统计4个或更多技能 | 分子和分母使用同一个必备技能集合；4/15=26.67，不再4/3。未用简单截断掩盖错误 |
| 删除技能清单反而涨分 | extractor 按 skill_id 只保留一条最高置信度证据；同分时先出现的skills_raw覆盖来源，丢失projects | 按技能+字段+原文+命中位置保留证据；匹配身份和项目身份分别用集合去重；三个section可以保留三条Python证据但只算一次覆盖 |
| 缺学历/经验给50 | match 中缺失解析值直接赋50；空要求_ratio还会给100 | 不可评估维度为null/unknown；只按可评估权重归一化；输出可评估维度与完整度；页面明确“信息不足 / 待补充” |
| 98%误导 | 精确名称命中固定0.98，单别名0.93，组合别名0.90；UI只展示百分比 | 保留confidence字段；追加confidence_semantics；UI明确“抽取置信度”及非掌握概率/非准确率说明；非affirmed只在证据区按极性展示 |

附带必要适配：画像频次与首页 evidence_jd_count 按“每JD每技能最多一次”统计，避免保留多证据后引入计数膨胀。批量导出入口使用同一增量词典并接受null维度。未重构新岗位、演化或学习路径算法。

### 项目评分及综合评分定义

设 R 为去重后的必备技能集合，P 为项目段中 accepted 且 affirmed 的技能集合：

`projects = 100 × |P ∩ R| / |R|`；R为空时不可评估，返回null。

必备/加分技能也使用各自集合覆盖率；证据数量不是技能满额贡献次数。
设 E 为非null维度集合，w为原有配置权重：

`match_score = sum(score[d] × w[d], d∈E) / sum(w[d], d∈E)`。

E为空时返回0与人工复核提示、空evaluated_dimensions，不能解读为有充分证据的零匹配。
每个数值维度和总分都有Schema 0～100约束；覆盖率分子天然不超过分母。
学历/经验仍采用原有等级/年限比例，超过要求最多100；本轮没有把这些启发式规则宣称为科学校准后的掌握概率。

## 3. evidence 与接口兼容性

- 保留旧字段：skill_id、standard_skill_name、skill_type、confidence、evidence、source_field、accepted。
- 新增：polarity、matched_text、start/end、need_human_review、confidence_semantics。
- evidence为完整原始字段（含空白）；位置按Python Unicode码点、左闭右开，前端不拿它直接当UTF-16索引。
- 同技能多条证据不再压成一条。相互矛盾的affirmed/negated证据保留，但取消该技能自动接受并要求复核。
- dimension_scores允许null；新增dimension_status（met/not_met/unknown）、evaluated_dimensions、data_completeness。
- data_completeness=可评估维度数/5，不是简历真实性；技能证据覆盖为空可计0，学历/经验缺失或岗位要求无法判断则unknown。
- **兼容性注意：** 虽未删除字段，null维度、多evidence及evidence由短命中词变成全文均是语义变化；旧消费者必须适配。三页、评分聚合、首页计数和批量导出已适配；数据库无迁移。
- 原始冻结版本及哈希保留；增量ID为SKILL-P0-SQL、SKILL-P0-FASTAPI。正式纳入下一版工作簿前需要人工整合，不能重复加入。

## 4. 测试过程与结果

### 失败基线

- 修业务代码前，后端42项（原有22+首批新增20）中，原有22项全过；新增出现31条失败断言记录（包含subTest）及1条字段缺失错误。
- 真实复现：空匹配10分、学历/经验各50、项目133.33、SQL/FastAPI缺失、技能来源丢失、否定被接受。
- 文员JD纯后端没有演示污染，原本通过；前端SSR断言确实揭示了隐藏字段和自动示例初始化。
- 前端首批4项业务断言全部失败；修复后转绿。最初缺依赖/写缓存权限的错误未计为业务复现。
- 后补“不会使用Python”和“正在学习使用Docker”边界测试先失败，修正复合谓词后通过。

### 最终结果

| 验证 | 结果 |
| --- | --- |
| 后端原有unittest | 22/22 PASS |
| 新增后端P0 unittest | 23/23 PASS |
| 完整后端集合 | 45/45 PASS |
| 新增前端Node内置测试（真实React SSR、payload、转义） | 6/6 PASS |
| 新增浏览器测试（六场景+HTML+八页导航） | 8/8 PASS |
| 项目原有run_system_qa.py | 11项checks全部true；14次本地API调用均HTTP200 |
| TypeScript | build内的tsc -b通过；项目原本无独立typecheck/lint脚本 |
| frontend build | PASS，2221模块，JS约1420.20 kB，gzip约473.55 kB；保留>500kB chunk告警，不扩大范围拆包 |
| 页面脚本错误 | 最终浏览器pageErrors为空 |
| 冻结数据哈希 | 四份文件均与原QA基准一致 |

前端原本没有test脚本；新增npm test仅调用Node内置runner及项目已有React/Vite，不增加测试框架依赖。浏览器测试使用设备已有Playwright与Edge，不新增package dependency。

原有批量报告生成器 `src.core.evaluate_core` 会改写历史报告，未执行整批导出；这里只做null/词典必要兼容适配。不以本轮用例通过率宣称全系统解析准确率≥90%。

### 新增后端测试名称（23项）

```text
test_a01_empty_resume_no_demo_skills
test_a02_clerk_jd_no_hidden_bonus
test_a03_negation_and_sql
test_a04_six_explicit_skills
test_a05_evidence_sections_retained_without_duplicate_contribution
test_a06_empty_education_unknown
test_a07_empty_experience_unknown
test_a08_dimension_bounds
test_a09_total_bounds_for_formal_job_profiles
test_a10_removing_skill_list_cannot_create_project_credit
test_a11_negated_not_matched
test_a12_planned_not_matched
test_a13_other_person_not_matched
test_a14_html_evidence_preserved_as_data
test_parallel_context_scopes
test_uncertain_needs_review_even_with_complete_resume
test_aliases_and_word_boundaries
test_evidence_has_original_text_offsets_and_confidence_semantics
test_empty_requirements_do_not_grant_free_credit
test_unknown_normalization_is_explicit
test_auxiliary_verbs_do_not_cancel_negation_or_plans
test_conflicting_evidence_is_retained_for_review
test_runtime_extension_preserves_frozen_ids
```

前端6项：JD/Resume/Match默认表单分别为空；bonus/work字段可编辑；真实payload构造清空与白名单；技能证据HTML转义/极性过滤/置信度文案。浏览器8项名称及断言见frontend/tests/p0.browser.cjs。

## 5. 六个本地黑盒对照

旧结果来自已有线上验收记录，本轮没有访问线上重测。修复后结果来自本地浏览器真实表单→FastAPI→真实解析/匹配服务。

| 场景 | 旧线上结果 | 本地修复后 | 结论 |
| --- | --- | --- | --- |
| 1 空白简历/匹配 | 清空可见字段仍带隐藏经历，Python进入结果，总分13.33 | 主动加载后清空，work_experience与所有技能/经历字段真空；matched=[]、总分0、学历/经验null unknown；空简历解析skills=[] | PASS |
| 2 文员JD | 隐藏bonus带入向量数据库 | bonus_skills_raw为空、skills=[]；不出现FastAPI/向量数据库 | PASS |
| 3 否定简历 | Python/Docker/Java/RAG/LangGraph被接受，SQL漏掉 | 五项negated/accepted=false；只有SQL affirmed进入正向标签 | PASS |
| 4 六技能正例 | FastAPI漏掉，5/6 | Python/FastAPI/LangGraph/RAG/MCP/Docker均affirmed，6/6 | PASS |
| 5 原匹配样例 | 项目0，总分36.67 | 主动加载示例，项目26.67（4/15），总分40.67 | PASS |
| 6 仅删除技能清单 | 项目133.33，总分53.33 | 请求仅skills_raw变化；项目仍26.67，总分37.33，不反向涨分 | PASS |

Case6总分降低的明确原因：Prompt Engineering只有技能清单证据，删除后必备覆盖由6/15变为5/15；项目证据未变，4/15保持不变。

额外：脚本样式HTML在浏览器中按文本显示，没有插入img元素或执行onerror；八页导航、图谱canvas、演化卡片和候选详情抽屉均可呈现。
首次浏览器运行的失败来自加载示例后精确label定位及对演化页面误用canvas断言；按实际DOM修正测试后全过，未为此更改业务结果。

## 6. 修改/新增文件

已有文件修改16项：

```text
.gitignore                                      本地npm缓存排除
docs/data_interface.md                          多证据/null/增量词典接口说明
frontend/package.json                          npm test入口，无依赖变化
frontend/src/pages/JDParsePage.tsx               空状态、可见bonus、显式示例、证据展示
frontend/src/pages/ResumeParsePage.tsx           空状态、显式示例、极性/置信度展示
frontend/src/pages/MatchPage.tsx                 可见work、空状态、null维度展示
frontend/src/types.ts                           evidence字段类型
src/api/service.py                             加载运行时增量词典
src/core/evaluate_core.py                       导出null兼容及统一词典
src/core/matching_engine.py                     去重覆盖评分、unknown、归一化
src/core/resume_parser.py                       矛盾证据/uncertain人工复核
src/core/skill_extractor.py                     上下文、全文、位置、多evidence
src/data_loader.py                             冻结词典之外的显式增量加载
src/integration/system_data.py                  每JD技能唯一计数、区分冻结/运行时数量
src/schemas.py                                 极性、证据及null维度契约
tests/run_system_qa.py                          可指定新报告目录，保留历史QA
```

新增9项：

```text
config/skill_dictionary_extensions.json
docs/p0_correctness_worklog.md
docs/p0_correctness_report.md
frontend/src/components/SkillEvidenceView.tsx
frontend/src/formPayloads.ts
frontend/tests/p0.test.mjs
frontend/tests/p0.browser.cjs
src/core/skill_context.py
tests/test_p0_regressions.py
```

本地忽略产物：.venv、frontend/node_modules、frontend/.npm-cache、frontend/dist、.codex_artifacts/p0（截图、请求/响应、原QA报告）；这些不包含真实个人简历输入。

## 7. Git 最终检查

`git diff --stat`（只统计已跟踪文件；新增文件另列如上）：

```text
 .gitignore                             |  1 +
 docs/data_interface.md                 | 21 ++++++++++++++
 frontend/package.json                  |  1 +
 frontend/src/pages/JDParsePage.tsx     | 12 ++++----
 frontend/src/pages/MatchPage.tsx       | 13 +++++----
 frontend/src/pages/ResumeParsePage.tsx | 12 ++++----
 frontend/src/types.ts                  |  2 +-
 src/api/service.py                     |  2 +-
 src/core/evaluate_core.py              | 14 +++++----
 src/core/matching_engine.py            | 52 ++++++++++++++++++++--------------
 src/core/resume_parser.py              | 12 +++++++-
 src/core/skill_extractor.py            | 19 +++++++++----
 src/data_loader.py                     | 20 +++++++++++++
 src/integration/system_data.py         |  8 ++++--
 src/schemas.py                         | 17 +++++++++--
 tests/run_system_qa.py                 |  4 ++-
 16 files changed, 152 insertions(+), 58 deletions(-)
```

`git diff --check`：通过，无空白错误；Git仅提示将来可能LF→CRLF转换。

`git status --short`：

```text
 M .gitignore
 M docs/data_interface.md
 M frontend/package.json
 M frontend/src/pages/JDParsePage.tsx
 M frontend/src/pages/MatchPage.tsx
 M frontend/src/pages/ResumeParsePage.tsx
 M frontend/src/types.ts
 M src/api/service.py
 M src/core/evaluate_core.py
 M src/core/matching_engine.py
 M src/core/resume_parser.py
 M src/core/skill_extractor.py
 M src/data_loader.py
 M src/integration/system_data.py
 M src/schemas.py
 M tests/run_system_qa.py
?? config/skill_dictionary_extensions.json
?? docs/p0_correctness_report.md
?? docs/p0_correctness_worklog.md
?? frontend/src/components/SkillEvidenceView.tsx
?? frontend/src/formPayloads.ts
?? frontend/tests/
?? src/core/skill_context.py
?? tests/test_p0_regressions.py
```

未暂存、未切换分支、未自动commit。outputs、requirements.txt、package-lock.json、render.yaml、frontend/vercel.json及生产配置均无diff；无大面积无关格式化。

## 8. 复测方法与证据

项目根目录：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -X utf8 -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

另一个终端在frontend目录：

```powershell
npm test
npm run build
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev -- --strictPort
```

浏览器测试需已有Playwright运行时；本机：

```powershell
$env:P0_PLAYWRIGHT_MODULE = 'C:\Users\H\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright'
node --test tests/p0.browser.cjs
```

八页浏览器检查通过后，根目录运行原有集成QA（仅本地API）：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 tests/run_system_qa.py --browser-qa-passed --report-dir .codex_artifacts/p0/system-qa
```

证据：`.codex_artifacts/p0/browser-results.json`、case1～case6.png、html-escape.png；`.codex_artifacts/p0/system-qa/system_qa_results_graph_dynamic_v2.json`。
交付前已停止本轮启动的本地前后端进程，不留自动执行任务。

## 9. 限制及未扩展的P1/P2事项

- 中文规则覆盖本轮给定语法及补充边界，不是通用自然语言理解保证；长距离指代、复杂嵌套否定、英文否定仍需独立语料评测。
- 学历等级与经验年限仍为原启发式解析，复杂学历/日期区间文本需要后续独立校准；本轮只纠正未知值默认加分。
- 文员JD已无技能污染，但标题预测仍给低匹配强度候选“AI应用研究员”（0.16、需人工复核）；通用岗位拒识/域外分类属于后续范围，本轮未改标题算法。
- 图谱和动态演化正式静态产物未重新生成，新增技能不意味着已补齐静态图谱节点；后续按正式版本流程整合。
- PDF/DOCX/OCR、新岗位五要素/审批版本、动态演化优化、全景筛选、学习路径升级和独立≥90%评测均未实施。
- 原CSS含Google Fonts请求，浏览器复测全程阻断并记录；没有因字体而联网。本轮未改主题/字体。
- ECharts主包较大告警保留。新增示例按钮沿用现有布局，未整体改版。
- 安装依赖及测试缓存写入曾遇权限/依赖阻塞，已通过批准解决；无剩余执行阻塞。

## 10. 安全确认

**未 commit；未 push/pull/fetch/merge/rebase；未修改GitHub；未部署Vercel/Render；未修改生产环境变量；未访问或修改生产数据库；未写入线上正式数据。**

发生的网络操作仅为经权限批准下载项目原有依赖；所有业务API验证只到127.0.0.1，浏览器非本地请求均被阻断。
本轮不进行自动提交或后续部署，停止等待人工验收。
