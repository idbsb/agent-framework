# P0 correctness work log

Baseline: local `fix/p0-correctness`, commit `5c97d32`, initially clean.

Scope: local correctness fixes only. No commit, remote synchronization, deployment, or production-data access.

## 已核实根因

| 问题 | 前端根因 | 后端根因 / 函数 | 建议修复 |
| --- | --- | --- | --- |
| P0-1 | `JDParsePage.tsx` 的 initial.bonus_skills_raw、`MatchPage.tsx` 的 initial.work_experience 未渲染但由 submit 展开；三个页面均自动加载示例 | `src/schemas.py` 的输入默认值为空，并未补示例 | 默认空值、显式加载/清空，所有业务字段可见 |
| P0-2 | 简历技能标签不过滤 accepted | `SkillIndex.extract_fields` 只按名称/alias 命中，accepted 恒 true | 通用上下文极性、只接受 affirmed、保留原文及位置 |
| P0-3 | 无 | `outputs/standard_skill_dictionary_v1.xlsx` 的 82 项标准技能及别名中均无 SQL/FastAPI；存在 MySQL/PostgreSQL，不能等价代替 SQL | 原始冻结工作簿不动，附加可审查增量词典，保持现有 ID |
| P0-4 越界 | 雷达轴最大 100，但不限制后端维度值 | `MatchingEngine.match` 的项目分母 min(3, len(required_ids)) 与分子定义不一致 | 项目必备技能覆盖率使用相同集合基数 |
| P0-4 删除涨分 | 无 | `SkillIndex.extract_fields` 按 skill_id 仅保留最高 confidence；相同时 skills_raw 先占位，projects 来源丢失 | 技能身份按集合计分，证据按来源和位置保留 |
| P0-5 | 没有信息缺失状态 | `MatchingEngine.match` 缺学历/经验赋 50；空要求 _ratio 返回100 | 不可评估返回 null + unknown，仅可评估维度权重归一化 |
| P0-6 | JD/Resume evidence 行仅显示百分比，简历所有技能均进画像 | `SkillIndex.extract_fields` 精确命中固定0.98、alias0.93、组合0.90 | 保留confidence兼容字段，明确规则命中强度而非掌握概率 |

## 测试基线与环境

- 后端原有框架：unittest（测试文件也可由 pytest 收集）。
- 前端没有已有 test/typecheck/lint 命令；build 为 `tsc -b && vite build`。
- 新增后端测试直接调用真实 API handler/services，无生产请求、无伪造评分 mock。
- 新增前端测试使用 Node 内置 test + 已有 React/Vite 做真实 SSR，不新增依赖。
- 初次运行缺少 FastAPI/PyYAML/Uvicorn 和 frontend/node_modules，未将依赖报错视为业务失败。
- 随后通过权限批准，按 requirements.txt 安装到本项目 .venv；按原 package-lock.json 安装前端依赖到本项目。未新增第三方业务依赖；仅有包源下载，不涉及 GitHub/生产服务。

## Red → Green 开发记录

1. 先新增20项后端回归和4项前端SSR回归，再运行原业务实现。
2. 后端首次有效运行42项（22原有+20新增），出现31条失败断言（包含subTest）和1条新字段缺失错误；原有22项全过。实际复现空简历10分、学历/经验50、项目133.33、来源丢失、SQL/FastAPI缺失和否定误判。文员JD在纯后端无污染，本来就通过；前端字段缺失/示例初始化断言失败，定位为请求端问题。
3. 前端首次遇到项目缓存写权限限制；权限批准后4项均进入业务断言并失败（初始表单非空、隐藏字段没有可编辑控件）。
4. 在确认失败后才修改实现。后端42项、前端4项转绿。
5. 补充3项后端边界测试；其中“不会使用Python”和“正在学习使用Docker”再次红灯，修复复合谓词后45项全绿。
6. 补充前端真实payload与HTML/置信度测试，6项全绿。build通过，只有现有大chunk体积警告。
7. 本地浏览器测试使用已有Playwright运行时和Edge，不新增依赖；前后端仅监听127.0.0.1，页面拦截所有非本地请求。

最终运行结果、六场景对照、限制和文件清单见 `p0_correctness_report.md`。
