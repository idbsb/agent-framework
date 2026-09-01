# P1 Production Closure Report

日期：2026-09-01  
工作目录：`D:\Projects\agent-framework-p1-prod`  
分支：`feature/p1-core-closure`  
代码状态：本地改动，未 commit、未 push、未部署  
结论：`READY_FOR_PRODUCTION_DEPLOYMENT`（仅表示代码侧可交给负责人部署，不表示线上已完成）

## 1. Production Gap Map

| 范围 | 审计前状态 | 本轮闭环结果 |
|---|---|---|
| Vercel → Render | `VITE_API_BASE_URL` 已支持公开 Render HTTPS 根地址；本地为空时走 Vite proxy | 保留并通过 Vercel-like 正/反向构建测试 |
| 写权限 | 已有 production Bearer Token，但缺失和错误 Token 均为 401 | 统一 dependency；关写 403、缺失 401、错误 403、正确 Token 放行 |
| loopback | 本地写入只允许 `127.0.0.1` / `::1` 和本地 Vite origin | 保留本地保护；production 使用 Bearer + exact Origin，不匿名开放 |
| 前端写后状态 | create/edit/action/discovery/update 直接采用 POST 响应 | 全部改为 POST 成功后无缓存 GET authoritative state；GET 不带 Token |
| 错误状态 | 多数直接显示后端 detail | 区分关写、缺认证、错误 Token、不可信 Origin、版本冲突、存储不可用和网络不可用 |
| SQLite 路径 | 本地默认文件；production 已支持可配置 companion DB | 保留现有等价变量 `P1_CLOSURE_DB`，生产路径固定在 Persistent Disk 内 |
| 重启验证 | 已有 browser process restart，但 Python 层证据不够集中 | 新增 Service A → Service B 同一 temp file 的 JD/review/publication/matching/graph 全链断言 |
| secret / bundle | Token 仅内存的方向正确 | 新增真实 Vercel-like build + dist marker scan；Token 只在 closure POST header |
| 部署文档 | 有说明文档但缺用户指定 checklist | 新增 `docs/p1_production_deployment_checklist.md` |
| clean checkout | 既有报告不能替代本轮验证 | detached clean worktree + fresh `npm ci` 全量复测通过 |

## 2. 原 P1 为什么只能本地闭环

P1 原始安全边界是 `P1_CLOSURE_WRITES=1` 加 loopback client/origin 检查，没有登录、JWT、session、管理员账户或 API key。它可以阻止局域网/互联网远程写，却不能识别正式线上管理员；若简单删除 loopback，任何互联网用户都能 create/edit/approve/reject/publish。因此原方案只能作为本机验收闭环，不能作为 production write authorization。

## 3. Loopback 原因与位置

位置为 `src/api/closure.py` 的统一写入 dependency。本地模式要求 request client 为 `127.0.0.1` 或 `::1`，浏览器 Origin 只能是 `http://127.0.0.1:5173` / `http://localhost:5173`。production 模式不信任 `X-Forwarded-For` 冒充 loopback，改为服务器端 Bearer Token，并对浏览器 Origin 做精确 allowlist。

## 4. 新生产写入安全模型

- 公共读 API 保持匿名可读。
- `P1_CLOSURE_WRITES != 1`：所有 closure 写请求 403。
- production + 无 Authorization：401，并返回 Bearer challenge。
- production + header scheme/credential 缺失：401。
- production + Bearer Token 错误：403。
- production + valid Token：允许 create、discovery/update、manual edit、submit、approve、reject、publish。
- production 浏览器 Origin 必须精确存在于 `CORS_ORIGINS`；非浏览器调用无 Origin 时仍必须通过 Bearer。
- 审核人由服务器 `P1_ADMIN_NAME` 绑定，客户端提交的 reviewer 不能伪造审计身份。
- Token 用 constant-time `secrets.compare_digest` 比较；非法请求不会变成 500。

## 5. Admin Token 方案

项目没有可复用登录/JWT/session，因此使用最小管理员 Token：`P1_ADMIN_TOKEN`。生产要求至少 32 个无空白 ASCII 字符；只存 Render secret。前端由管理员运行时手工输入，只保存在当前模块内存，刷新后清空。Token 仅附加到 `/api/closure/...` POST；所有 GET 与非 closure POST 都不携带。

## 6. Secret 安全

未硬编码或提交真实 Token、password、database credential、Render secret、Vercel secret。`.env.example` 与文档仅有占位规则。测试只使用 `TEST_ADMIN_TOKEN...`、randomBytes 或明确 synthetic credential。对 frontend source、真实 `frontend/dist`、backend source、tests、docs、git diff 执行 credential-pattern scan：未发现私钥、云 access key、长 Bearer secret 或带凭据 DB URL。Vercel-like build 把 `P1_ADMIN_TOKEN=TEST_ADMIN_TOKEN_MUST_NOT_ENTER_FRONTEND_BUNDLE` 放在构建环境，扫描所有 dist 文件确认 marker 不存在。

## 7. 持久化方案

采用 SQLite + Render Persistent Disk，不引入 PostgreSQL，也没有 `DATABASE_URL`。Repository 使用文件连接；事务采用 `BEGIN IMMEDIATE`，异常 rollback，成功 commit，连接 finally close；SQLite connection timeout 为 10 秒；schema 初始化使用 `CREATE TABLE IF NOT EXISTS`，幂等且不 seed、不覆盖、不 DROP、不 DELETE。并发目标限定单 Render instance / 单 uvicorn worker。

## 8. `P1_CLOSURE_DB`（等价 P1 DB path）

- 未配置时，本地仍为 `data/p1_closure.sqlite3`。
- 本地显式路径必须是 checkout 内 `.sqlite3` companion file。
- production 要求 `P1_STORAGE_DIR` 和 `P1_CLOSURE_DB` 均为绝对路径；DB 必须位于 storage 内且扩展名为 `.sqlite3`。
- 服务安全创建 DB parent directory。只有 production 新库且 `P1_INITIALIZE_DB=1` 时可做首次空库 schema bootstrap；已有生产库缺 schema 时拒绝静默修复。

## 9. Render Persistent Disk 准备

`render.yaml` 已声明：service plan starter、1 instance、1 worker；disk `p1-closure-data`，1 GB，mount `/var/data/p1`；`P1_STORAGE_DIR=/var/data/p1`；`P1_CLOSURE_DB=/var/data/p1/closure.sqlite3`。这只是 repository-side Blueprint readiness，不代表 Render 控制台已创建或挂载 Disk。负责人必须按 checklist 核对真实 mount，首次空盘短暂启用初始化，成功后立即恢复 `P1_INITIALIZE_DB=0`。

## 10. CORS

生产由 `CORS_ORIGINS` 配置精确 HTTPS origins；拒绝空值、`*`、HTTP、localhost、路径、query、fragment 或嵌入凭据。`allow_credentials=false`，允许 GET/POST/OPTIONS 及 Content-Type/Authorization。local 模式自动支持两个 5173 localhost origins。production browser 验证正式 origin preflight 200 且返回精确 ACAO；恶意 origin 不获授权。

## 11. Frontend API Config

`frontend/src/api.ts` 使用 `VITE_API_BASE_URL`。本地为空时相对 `/api` 由 Vite proxy 到 `127.0.0.1:8000`；Vercel build 必须提供公开 Render HTTPS 根地址，不得带 `/api`、localhost、HTTP、path、query 或 credentials。Vercel 只配置该公开地址，不配置 `P1_ADMIN_TOKEN`。正向和错误配置构建测试均通过。

## 12. API 权限矩阵

| API 类型 | writes=0 | production 无 Token | 错误 Token | valid Token |
|---|---:|---:|---:|---:|
| public GET | 200（按资源状态） | 200 | 200 | 200 |
| create/edit/discovery/update/actions | 403 | 401 | 403 | 进入业务校验并可成功 |
| approve/publish | 403 | 401 | 403 | 状态机允许时 200 |

版本冲突 409、输入/证据错误 422、数据库不可写/不可用 503；前端分别展示可行动提示。

## 13. Reload Persistence

所有 closure GET 使用 `cache: no-store`。新增 `postThenGet`：POST 成功后必须执行 authoritative GET；Token 只在 POST。create 重新 GET evidence；discovery/update 重新 GET candidate/profile；manual edit 与 submit/approve/reject/publish 重新 GET detail。production browser publish 后执行真实 `page.reload()` 并从 API 恢复 published V1/V2，页面 storage 中 Token 为 0，刷新后需重新授权。

## 14. Restart Persistence

Python `test_prod_13_to_20...` 使用 temporary file DB：Service A 添加 synthetic JD、人工 edit、submit、approve、publish；Service B 用同一文件重新创建，验证 evidence、history、review、publication 存在，并通过 FastAPI dependency 重建后的 GET 读取。production browser 真实终止 uvicorn 进程，以 `P1_INITIALIZE_DB=0` 重启，再验证同一 JD、版本历史、published fingerprint、matching 和 graph。

## 15. Published Effective Profile

`PublishedProfileRepository` 只读取 publication `status=published` 且 `origin=human_approved`，按最大 `profile_version` 选择 latest published。没有人工 published 时保持 static baseline；legacy baseline 不冒充人工 publish。reader 每次从 SQLite 读取，不使用进程内 publication cache。

## 16. Matching

MatchingEngine 继续使用现有 P0 评分逻辑，只替换 effective profile source。测试证明 V1/V2 publish 后 `profile_source=published_dynamic`、version/fingerprint 更新；pending、approved-unpublished、rejected 均保持上一 published。未重写评分算法。

## 17. Graph

GraphAdapter 与 matching 共用同一 EffectiveJobProfiles reader。测试证明 graph 与 match 的 profile_version / fingerprint 一致；仅正式 Job_Skill edges 使用 published snapshot，其他图谱边不被修改；pending、approved-unpublished、rejected 不改变 graph。

## 18. 新增 / 强化 Production Tests

- PROD-01～03：关写 403、无 Token 401、错误 Token 403。
- PROD-04～09：valid admin create/edit/approve/publish；匿名 approve/publish 拒绝。
- PROD-10～12：public read 正常、响应不含 Token、Vercel-like dist 不含 Token。
- PROD-13～20：repository/service restart、latest published 与三个未发布状态隔离、matching/graph latest published。
- PROD-21～23：local origin、production exact origin、恶意 origin 无 CORS 授权。
- PROD-24～25：API base env 正/反向构建；坏 auth/storage/env fail closed 并给出清晰 503/构建错误。
- 前端新增 POST→GET 顺序与 GET 无 Token、no-store 断言。

## 19. P0 Regression

全部 Python P0 regression 通过。P0 Browser 8/8，exit 0。clean worktree 不存在 ignored `/data/job_analysis_v1.json`；JobAnalysisPage 对 404/network/invalid JSON 均安全降级，production browser `pageErrors=[]`，没有 uncaught error。没有重新设计 P0 fallback。

## 20. P1 Regression

P1 Browser 8/8；新岗位五要素、manual edit、review、approve/publish、版本 diff、既有岗位更新、rejected isolation、insufficient sample 均通过。Effective-profile Browser 4/4；production-like Browser 7/7。

## 21. Clean Worktree

从 HEAD `4537e07` 创建 detached clean worktree `D:\Projects\agent-framework-p1-prod-clean-20260901`，只复制本轮候选改动；开始时没有 `.venv`、node_modules、dist、data SQLite 或 ignored runtime artifacts。`npm ci --offline` 因缺少 zrender cache 明确失败，随后经批准按 package-lock 执行 fresh `npm ci`（80 packages，0 vulnerabilities），没有复用开发目录 node_modules。clean 结果：Python 104/104；frontend 16/16；build exit 0；P0 8/8；P1 8/8；effective 4/4；production 7/7；Integration QA 11/11。

## 22. Frontend Build / TypeScript

开发 worktree 和 clean worktree 的 `npm run build` 均 exit 0，2227 modules transformed。唯一提示为既存的单 bundle 大于 500 kB warning，不影响正确性，也未在本轮做 P3 UI / bundle 重构。Vercel-like valid API base build 同样通过。

## 23. Production-like E2E

完全本地、无生产连接：随机测试 Token、temp storage、temp SQLite、本地 HTTP API 8011、本地自签 HTTPS UI 5443。覆盖管理员解锁 → create synthetic JD → authoritative reload → edit → submit/approve → publish 前 match/graph 不变 → publish 后同时切换 → page reload → API process restart → 数据仍在 → V2 publish → V3 pending/rejected 保持 V2。7/7 pass，pageErrors=[]。

## 24. 业务数据 Hash

对 31 个受 Git 跟踪的业务 JSON/Excel/CSV/DB 类文件，与 clean HEAD worktree逐文件重新计算 SHA-256：`DATA_HASH_CHANGED=0`。

| 文件 | Size | SHA-256 |
|---|---:|---|
| `outputs/standardized_jd_dataset_v1.xlsx` | 179341 | `B00A0220FD4B974D8B00BB57D6F0AF3BB40F1D92CC7DDD59FCB0DDDA9FC90EDE` |
| `outputs/standardized_resume_testset_v1.xlsx` | 17346 | `3B78EDFFD349055342818FFF6B803B92D5BD1C1BD1DE140E3764EF82C3CCD952` |
| `outputs/standard_skill_dictionary_v1.xlsx` | 19794 | `178C64E654D3534878489E88AAFC5A17B98FE361CB38DB370F9036D01E5C1055` |
| `outputs/standard_job_title_mapping_v1.xlsx` | 20617 | `293B34DBB8E4E6F5689CF58387A38601F30FEB759B46E7F34931BC1F6FF859B1` |

## 25. Secret Scan

Source/tests/docs/diff credential-pattern scan：0 matches。dist admin scan：测试 marker 0 matches；bundle 不含 `P1_ADMIN_TOKEN` 或 synthetic backend credential。允许出现的只有变量名、占位说明及明显测试值。未发现 `.env`、production SQLite、private key、日志、coverage 或 credential file 被 Git 跟踪/列为 untracked。

## 26. `git diff --stat`

生成本报告前，tracked code diff 为 6 files，163 insertions、16 deletions：`frontend/src/api.ts`、`ClosurePanel.tsx`、两个 production tests、`src/api/closure.py`、`tests/test_p1_production.py`。另有两个指定新文档尚未跟踪：deployment checklist 与本报告。最终人工 review 应以工作区实时 `git diff --stat` 和 `git status` 为准。

## 27. `git diff --check`

Exit 0，无 trailing whitespace / conflict marker error。Git 在 Windows 提示未来可能 LF→CRLF；这是 line-ending warning，不是 diff-check failure，未批量改写全仓换行。

## 28. `git status`

分支保持 `feature/p1-core-closure`，未移动 HEAD。完成前状态为 6 个 modified code/test 文件和 2 个新 docs 文件；无 staged change。未出现 production SQLite、JD、resume、`.env`、secret、logs、coverage、dist、node_modules 或临时文件。

## 29. 负责人部署时必须完成

按 `docs/p1_production_deployment_checklist.md`：审核/合并 PR #2；在 Render 实际创建并核对 `/var/data/p1` Persistent Disk；负责人生成并设置 `P1_ADMIN_TOKEN`；设置管理员名、DB path、CORS、write switch；仅首次空盘临时初始化后恢复为 0；验证 health/public read/auth/CORS；在 Vercel 只设置 `VITE_API_BASE_URL`；部署后由负责人执行 `SYNTHETIC_PRODUCTION_ACCEPTANCE` 浏览器验收与 Render restart persistence。Codex 不代跑线上步骤。

## 30. 尚存 Blocker

代码侧无 blocker，状态为 `READY_FOR_PRODUCTION_DEPLOYMENT`。平台侧尚未执行的 Persistent Disk 创建/挂载、secret/env 配置、Render/Vercel 部署和线上 E2E 是负责人部署任务，不是本报告声称已完成的事项。若负责人无法提供真实 Persistent Disk、精确正式 origins 或安全管理员 Token，则部署必须保持 BLOCKED，不得开放匿名写入。

## 最终范围确认

未修改 P2；未修改 P3；未搜索外部招聘数据；未新增真实 JD；未修改原始 Excel；未修改原始 JSON；未修改业务数据库；未连接生产数据库写数据；未泄露 secret；未部署；未 commit；未 push。
