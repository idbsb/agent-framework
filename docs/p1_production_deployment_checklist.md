# P1 Production Deployment Checklist

适用范围：PR #2 合并到 `main` 后，由负责人在 Render / Vercel 人工部署。本文不代表线上已部署，任何合成验收数据都不得从开发环境上传到生产。

## A. Render 后端

### A1. 服务与持久盘

- 使用仓库根目录 `render.yaml` 创建或更新 Web Service；运行时为 Python，`uvicorn src.api.app:app --host 0.0.0.0 --port $PORT --workers 1`。
- 核对实例数为 1、worker 为 1。当前 SQLite 方案不支持多个实例共享同一数据库文件。
- `render.yaml` 已声明名为 `p1-closure-data` 的 1 GB Persistent Disk，mount path 为 `/var/data/p1`。
- 必须在 Render 控制台确认 Disk 已实际创建、附加到本服务且挂载到 `/var/data/p1`。仓库声明不等于平台资源已存在。
- 数据库文件固定为 `/var/data/p1/closure.sqlite3`。不要放在 checkout、`/tmp` 或其他 ephemeral filesystem。

### A2. Render 环境变量

负责人逐项配置并核对：

| 变量 | 生产值 / 规则 | Secret |
|---|---|---|
| `P1_ENV` | `production` | 否 |
| `P1_CLOSURE_WRITES` | 正常管理员写入时为 `1`；紧急关写时改为 `0` | 否 |
| `P1_STORAGE_DIR` | `/var/data/p1` | 否 |
| `P1_CLOSURE_DB` | `/var/data/p1/closure.sqlite3`；这是本项目的可配置 P1 DB path | 否 |
| `P1_INITIALIZE_DB` | 常态为 `0`；仅首次确认空盘时临时设 `1` | 否 |
| `P1_ADMIN_TOKEN` | 负责人自行生成的高熵随机 ASCII Token，至少 32 字符；只存 Render secret | **是** |
| `P1_ADMIN_NAME` | 审核记录采用的责任人/管理员标识 | 建议按敏感配置管理 |
| `CORS_ORIGINS` | 精确正式 Vercel HTTPS origin，例如 `https://example.vercel.app`；多个值逗号分隔 | 否 |
| `PYTHON_VERSION` | 与 `render.yaml` 一致的 `3.12.13` | 否 |

禁止把 `P1_ADMIN_TOKEN` 写进 Git、Render build command、Vercel、`VITE_*`、URL、日志或前端源码。Token 由负责人在安全终端生成；本文不提供也不保存实际值。

### A3. 首次空盘初始化

1. 先确认 `/var/data/p1` 是新挂载的空 Persistent Disk，且没有需要恢复的旧库。
2. 临时设置 `P1_INITIALIZE_DB=1`，保持其他变量完整，部署一次。
3. 请求 `GET /api/health/ready`，必须返回 HTTP 200，正文包含 `status=ready`、`storage=ok`。
4. 立即把 `P1_INITIALIZE_DB` 改回 `0` 并重新部署。
5. 再次检查 readiness。只有第二次启动仍为 200，才允许继续。

如果库文件已存在但 schema 缺失/损坏，服务会失败关闭；不得重新开启初始化来掩盖数据丢失，应停止写入并从经过验证的备份恢复。启动不会 seed demo JD、创建默认岗位、DROP 表或 DELETE 数据。

### A4. Render 验证

- `GET /api/health/ready` 为 200。
- 不带 Token 的公共读 API（如 `GET /api/jobs`）为 200。
- `P1_CLOSURE_WRITES=0` 时写 API为 403，但读 API不受影响。
- 开写后，不带 `Authorization` 的写请求为 401；错误 Bearer Token 为 403；正确 Token 才允许写。
- 不可信 Origin 不应获得 `Access-Control-Allow-Origin`；正式 Vercel origin 的 preflight 应允许 `Authorization`、`Content-Type`。
- 响应正文、响应头及服务日志中不得出现管理员 Token 或数据库凭据。

## B. Vercel 前端

- Project Root 指向 `frontend`（或确保构建命令在该目录执行）。
- Production 环境配置 `VITE_API_BASE_URL=https://<正式-Render-HTTPS-域名>`，必须是根地址：不带 `/api`、路径、查询参数、凭据或尾随业务路径。
- 不要在 Production 使用 localhost、个人 IP、临时预览 API 地址或 HTTP。
- **绝对不要在 Vercel 配置 `P1_ADMIN_TOKEN`，也不要创建任何 `VITE_*ADMIN*TOKEN*` 变量。** Vite 的客户端变量会进入 bundle。
- Preview 部署不要加入生产 `CORS_ORIGINS`，除非负责人明确把某个固定 preview origin 纳入受控验收。
- 构建必须完成 TypeScript 与 Vite build；缺少或错误的生产 API base URL 应直接构建失败。

管理员在浏览器运行时手工输入 Token。Token 只驻留当前 React 页面内存；不进入 localStorage、sessionStorage、IndexedDB、URL 或读请求。刷新后需要重新输入，这是预期行为。

## C. 部署顺序

1. PR #2 经负责人审核后合并到 `main`。
2. 在 Render 创建/核对 Persistent Disk 与全部环境变量。
3. 按 A3 仅对首次空盘执行一次显式初始化，再恢复 `P1_INITIALIZE_DB=0`。
4. 部署 Render，确认 readiness、公共读、认证矩阵与 CORS。
5. 在 Vercel 配置唯一公开变量 `VITE_API_BASE_URL`，部署前端。
6. 打开正式 Vercel URL，完成下面的人工 browser smoke / acceptance。
7. 验收后保留审计记录；按运维流程建立 SQLite 在线备份与恢复演练。

## D. 部署后正式验收（仅负责人执行）

1. 打开正式 Vercel URL，确认读页面正常。
2. 未解锁时尝试写入，确认被拒绝。
3. 手工输入管理员 Token 解锁；检查浏览器 storage 均没有 Token。
4. 创建明确标记为 `SYNTHETIC_PRODUCTION_ACCEPTANCE` 的 synthetic JD，不得使用真人简历或未授权招聘数据。
5. 页面刷新，重新 GET 后确认 JD 仍存在。
6. 人工 edit，刷新后确认修改存在。
7. submit → approve；在 publish 前记录 matching 和 graph，确认都没有切换。
8. publish；确认岗位分析、matching、graph 同时使用相同的最新 published profile version / fingerprint。
9. 刷新页面，确认发布版本仍存在。
10. 由负责人执行 Render restart / redeploy；确认 readiness 恢复后，验证 JD、审核事件、published version、matching、graph 均仍存在且一致。
11. 新建 pending 版本，确认正式结果仍用上一 published；approve 但不 publish，仍不切换；reject 后仍不切换。
12. 清除本页管理员权限，确认后续写请求被拒绝且公共读正常。

## E. 失败处理与上线阻断条件

出现任一情况立即停止上线或关写：Persistent Disk 未挂载；readiness 非 200；数据库不可写/损坏；生产 origin CORS 失败；匿名写入成功；Token 出现在 bundle/日志/响应；重启后数据丢失；pending、approved-unpublished 或 rejected 影响 matching/graph；多实例/多 worker 被误开启。

本清单只准备 repository-side deployment readiness。Codex 未创建平台资源、未设置生产环境变量、未部署、未写生产数据库。
