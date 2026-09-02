# P1 生产部署与线上验收

这是既有 P1 的最终验收要求，不是 P1.1 或 P2。所有改动归入 `feature/p1-core-closure` 的现有 PR。

代码、配置和本地测试就绪最多标记 `READY_FOR_PRODUCTION_DEPLOYMENT`；只有负责人配置 Vercel/Render、密钥、持久盘，真实部署并完成下面线上 E2E 后，才可判定 `P1 COMPLETE`。本文不是已部署证明。

## 部署结构与边界

- Vercel：`frontend` 为 Root Directory，Vite 构建，输出 `dist`；保留 SPA rewrite。
- Render：仓库根目录，Python API，合并后从 `main` 部署；一个付费实例、一个 worker、一个持久盘。
- 冻结 Excel/JSON 仍来自 Git checkout，只读；所有追加 JD、内容版本、审核事件、发布快照仍在同一 SQLite companion store 中。没有数据迁移、P2 引入或 P0 算法变更。
- matching、graph、job-analysis 继续复用已有 PublishedProfileRepository；只有人工 published 快照生效。所有 API 回应 `Cache-Control: no-store`，前端 GET 同样禁用缓存。
- 这是单管理员密钥方案，不是多用户登录或角色系统。持有密钥者均拥有 JD、编辑、审核和发布权限；由负责人保管，不发给普通访客。正式审核身份来自服务器，不能由表单冒充。
- 当前读取接口沿用公开访问语义（包括闭环证据与历史）；不要导入不应公开的 JD 或个人信息。

Render 免费实例不能挂持久盘，默认文件系统会在重启/重新部署时丢失；持久盘仅在运行时可用，不能在 build/pre-deploy 中初始化。带盘实例无法横向扩容，也不提供零停机部署。参见 [Render persistent disks](https://render.com/docs/disks)。

## Render 配置

仓库 `render.yaml` 给出目标配置；已有 Dashboard 服务不会因为编辑 YAML 就自动配置正确，负责人必须核对实际实例、磁盘和环境变量。

| 项目 | 生产值 / 要求 |
| --- | --- |
| branch | `main`，合并本 P1 PR 后部署 |
| plan | `starter` 或其他支持持久盘的付费实例 |
| disk mount | `/var/data/p1`，初始 1 GB，监测剩余空间 |
| P1_ENV | `production`；Render 环境始终启用生产保护，不能用 local 绕过 |
| P1_STORAGE_DIR | `/var/data/p1`，必须是真实挂载点 |
| P1_CLOSURE_DB | `/var/data/p1/closure.sqlite3`，必须在持久盘内，不能放 checkout 或临时目录 |
| P1_CLOSURE_WRITES | `1` 开放经鉴权写入；设 `0` 紧急关写，已发布数据仍可读取 |
| P1_ADMIN_TOKEN | 负责人生成的高熵随机密钥，至少 32 ASCII 字符，推荐 32 随机字节的 64 位十六进制值；仅存 Render secret |
| P1_ADMIN_NAME | 管理员审计名称，必填 |
| CORS_ORIGINS | 精确的正式 Vercel HTTPS origin；多个以逗号分隔，不接受通配符、路径或任意 preview 域名 |
| P1_INITIALIZE_DB | 常态必须 `0`；仅首次空盘初始化期间设 `1` |
| healthCheckPath | `/api/health/ready`，不能用 `/docs` 代替 |
| startCommand | `uvicorn src.api.app:app --host 0.0.0.0 --port $PORT --workers 1` |

首次启用顺序：

1. 负责人确认目标磁盘是新空盘；若有历史生产数据，先备份并迁入正确路径，禁止以初始化代替恢复。
2. 挂载持久盘、配置全部生产变量。仅此时把 `P1_INITIALIZE_DB=1` 用于首次启动，创建现有两张表；不导入本地合成测试库。
3. `/api/health/ready` 返回 200 后，立即改为 `P1_INITIALIZE_DB=0` 并重新部署。确认二次启动和健康检查成功，才开放正式使用。
4. DB 丢失、损坏或磁盘未挂载会启动失败或返回 503。禁止重新设 `P1_INITIALIZE_DB=1` 隐藏数据丢失。检查挂载并从备份恢复。

启动与健康检查验证生产配置、SQLite 结构与完整性、事务写权限、可解析的发布记录。健康响应不泄露密钥或本机路径。它不能替代云端磁盘实际生命周期验收。

## Vercel 配置与管理操作

- Production 环境设置 `VITE_API_BASE_URL=https://<实际Render域名>`：根地址，不带 `/api`、查询串或凭据。这是公开 API 地址，不是密钥。
- **禁止设置 `VITE_ADMIN_TOKEN`、`VITE_P1_ADMIN_TOKEN` 等任何包含密钥的前端变量**。Vite 会将公开环境变量写进构建资产。参见 [Vercel Vite documentation](https://vercel.com/docs/frameworks/frontend/vite)。
- Vercel build 环境缺少 API 地址、使用 HTTP、localhost 或 `/api` 后缀时构建失败，防止线上误用本地 Vite 代理。
- 设置或更换地址后重新构建部署。不要给未授权的 Preview 部署生产写入权限；生产 Render 的 CORS 只列正式站点。
- 新岗位/演化页提供“管理员写入密钥”。负责人手工输入并验证；密钥只在当前页面内存中保存，不写 localStorage、sessionStorage、URL 或构建文件。刷新后重新输入；“清除写入权限”清空当前页面凭据。
- 跨域 POST 使用 Authorization Bearer；CORS preflight 允许 Authorization/Content-Type。错误密钥返回 401，不可信 Origin 返回 403，写入开关关闭返回 403；版本冲突仍返回 409，输入错误仍返回 422。
- 不使用 cookie，也不把 CORS 当作身份认证。非浏览器 API 调用同样必须提供 Bearer。密钥轮换由负责人修改 Render secret 并重新部署，旧密钥随即失效。

## 备份、恢复与回滚

通过 SQLite backup API 做一致性备份，不能在运行中直接复制数据库主文件：

```sh
python -m src.closure.backup --source /var/data/p1/closure.sqlite3 --destination /var/data/p1/closure-backup-YYYYMMDD-HHMM.sqlite3
```

命令不覆盖任何现有目标文件，源库只读连接；检查完整性并报告 evidence/entity 数量。失败时不使用残留目标作为可恢复备份。由负责人定期执行，将成功备份复制到独立安全存储，并监测磁盘空间。同一盘上的备份不能防磁盘整体丢失。

恢复顺序：关写并停止服务；保留故障库用于调查；验证离线备份完整性和发布历史；将其恢复到上述固定路径；保持 `P1_INITIALIZE_DB=0` 重启；核对健康、JD ID、发布版本及 matching/graph fingerprint 后再开写。恢复会丢失备份之后的改动，必须由负责人确认。

代码回滚不能删除或重建持久盘。本次 SQLite schema 仍是既有两张表，无破坏迁移；若回滚到仅支持本地路径的旧 API，不能继续用于生产持久盘，需先关写和评估兼容性。不要用清空数据库处理版本冲突或错误发布；通过后续人工审核版本修正。

## 负责人线上 E2E 验收记录（全部待填写）

记录正式 Vercel URL、Render URL、main commit、前后端 deploy ID、磁盘名称/路径、日期和执行人；不要记录密钥。以下必须在真实正式网站执行，不能用本地结果替代：

1. 未授权访客 POST 被拒绝；管理员可在正式站点完成授权。观察浏览器请求确实到 Render，OPTIONS 成功。
2. 在页面追加可公开的真实 JD，保存后记录 JD ID；GET 读回一致、刷新后仍存在。按发现规则提供足够证据并显式运行发现，不能把单条 JD 强行认定为新岗位。
3. 编辑五要素，确认自动定义保留；提交审核。pending 不进入正式岗位匹配和图谱。
4. approve 后仍不生效；publish 后产生正式 profile_version V1，刷新后可见。matching、graph、job-analysis 均返回 `published_dynamic`、同一版本和 fingerprint。
5. 修改为 V2，pending 与 approved-unpublished 均继续使用 V1；publish 后三处切换至 V2，技能变化与真实证据一致。
6. 再产生一个版本并 reject；正式匹配及图谱继续使用 V2。
7. **负责人在 Render 实际 Restart 服务**。重启后读取新增 JD、内容版本、审核事件和 V2 发布快照，并在正式 Vercel 页面刷新验证；matching/graph 的版本、fingerprint 与重启前一致。
8. 做一次真实重新部署，确认仍挂同一持久盘、`P1_INITIALIZE_DB=0`，重复第 7 步数据核对。记录截图和非敏感响应。
9. 验证可选 job_analysis JSON 缺失/网络失败/非 JSON 不产生未处理 pageerror，不影响真实 API 发布画像；双管理员旧页更新返回 409，不覆盖新版本。
10. 负责人保存证据并签字；所有要求通过后，才能将状态改为 `P1 COMPLETE`。

## 本地复现

Python：`python -m unittest discover -s tests -v`。

前端（frontend 目录）：`npm ci`、`npm test`、`npm run build`。

生产模式浏览器：安装/指定现有 Playwright 和 Edge，确保 OpenSSL 可用；设置 `P1_TEST_PYTHON` 指向有 requirements 的 Python、`P1_PLAYWRIGHT_MODULE` 指向 Playwright 模块，必要时设置 `P1_OPENSSL`，从仓库根运行：

```sh
node --test frontend/tests/production.browser.cjs
```

该脚本只绑定本机 8011/5443，构建真实前端、创建临时自签证书与 checkout 外合成数据库，将测试域名映射到本机；运行真实 CORS/浏览器及 API 进程重启，保留 `.codex_artifacts/p1-production` 结果和临时合成数据库，不访问生产。测试暂将 ignored `frontend/dist` 构建为本地 API 地址；结束后正常重新 build，禁止上传该测试 dist 到 Vercel。

不修改或复制 P0 fallback/P0 browser regression；新增生产用例验证现有 fallback 的 404、网络失败和 JSON parse failure。P2 的 PDF/DOCX、规范化、near duplicate、评测和样本/时间增强均不在本 PR。
