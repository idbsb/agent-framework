# 正式图谱/动态演化接入 QA 结果

## 1. 测试环境

- 操作系统：Windows-11-10.0.26200-SP0
- Python：3.12.14
- Node.js：v24.18.0
- 测试时间：2026-09-05T11:12:33+08:00

## 2. 后端测试

核心单元测试、数据加载、兼容 Adapter 和 OpenAPI 路由检查均已执行。原五个 API 保持注册且真实调用成功：**通过**。

## 3. API测试

- `GET /api/jobs`：HTTP 200，通过
- `GET /api/skills`：HTTP 200，通过
- `POST /api/jd/parse`：HTTP 200，通过
- `POST /api/resume/parse`：HTTP 200，通过
- `POST /api/match`：HTTP 200，通过
- `GET /api/system/overview`：HTTP 200，通过
- `GET /api/job-analysis/{job_title}`：HTTP 200，通过
- `GET /api/graph/job/{job_title}`：HTTP 200，通过
- `GET /api/graph/skill/{skill_id}`：HTTP 200，通过
- `GET /api/evolution/job/{job_title}`：HTTP 200，通过
- `GET /api/evolution/job/RAG引擎研发工程师`：HTTP 200，通过
- `GET /api/evolution/job/AI安全技术工程师`：HTTP 200，通过
- `GET /api/emerging-jobs`：HTTP 200，通过
- `GET /api/emerging-jobs/{candidate_id}`：HTTP 200，通过

## 4. 前端测试

- React + Vite 生产构建：通过。
- 八个页面导航、中文显示、候选详情抽屉、正式图谱页和正式动态演化页：通过。
- 浏览器控制台明显错误：未发现。
- 后端短时不可用时：已验证页面无缝读取程序导出的同源数据，不展示工程状态提示。
- 1440px 桌面视图和 390px 移动视图横向溢出检查：通过。

## 5. 图谱测试

- 数据来源：真实招聘信息聚合。
- 正式完整图谱：694 个节点、2495 条关系，其中岗位—技能关系 1116 条。
- 当前重点岗位子图：48 个节点、47 条关系（显示层过滤）。
- 关系 Evidence JD：通过。
- 岗位—技能关系已按去重后的真实JD重新计算，并保留招聘信息编号。

## 6. 动态演化测试

- 正式文件状态：`connected`；时间范围：['2026-04-14T00:00:00', '2026-08-15T00:00:00']。
- AI Agent / RAG / AI 安全样本量：12 / 2 / 9。
- RAG 与 AI 安全岗位的正式样本不足提示已保留。
- 未重新计算或伪造趋势：通过。

## 7. 新岗位发现测试

- 候选：32 个。
- 高/中/弱：3 / 10 / 19。
- 每个候选包含完整 `evidence_jd_ids` 与 Evidence 记录：通过。
- 单条 JD 不高于弱候选：通过。

## 8. 匹配测试

- 真实 API 匹配分数：50.33。
- 五维 `dimension_scores`、技能差距和原 Matching Engine `recommendations` 均返回：通过。
- 未宣传虚假匹配准确率。

## 9. Evidence测试

JD 解析、简历解析、图谱关系和新岗位候选均可追溯到真实 Evidence 或 JD 编号。校验结果：通过。

## 10. 数据冻结检查

行数：JD 191、简历 27、技能 82、别名 146。ID 唯一性与别名引用检查通过。

- `standardized_jd_dataset`：`B00A0220FD4B974D8B00BB57D6F0AF3BB40F1D92CC7DDD59FCB0DDDA9FC90EDE`（一致）
- `standard_job_title_mapping`：`293B34DBB8E4E6F5689CF58387A38601F30FEB759B46E7F34931BC1F6FF859B1`（一致）
- `standard_skill_dictionary`：`178C64E654D3534878489E88AAFC5A17B98FE361CB38DB370F9036D01E5C1055`（一致）
- `standardized_resume_testset`：`3B78EDFFD349055342818FFF6B803B92D5BD1C1BD1DE140E3764EF82C3CCD952`（一致）

## 11. 已知问题

- 缺失组员 A 正式文件：无。
- RAG 与 AI 安全岗位的正式结果标记为当前比较窗口样本不足，应按提示审慎解读。
- 部分新岗位候选只有单条 Evidence，因此如实保留为弱候选。
- Matching V1 分数有限，系统只展示真实结果。
- 前端已按页面拆分资源，首页首屏不再加载图谱与图表主包。

## 12. 是否达到演示条件

最终结论：**通过**。系统已达到本地比赛演示条件。
