# Render 免费部署说明（不使用 Vercel）

本项目的免费公开部署只使用一个 Render Web Service：

- `challenge-cup-agent-framework-api`：FastAPI 同时提供 React 前端和 API。

服务由仓库根目录的 `render.yaml` 声明。前端生产构建保存在 `frontend/dist` 并由 FastAPI 同域提供，Vercel 不再是运行依赖，也不需要跨域配置。

## 免费模式的边界

Render Free Web Service 没有 Persistent Disk，文件系统会在休眠、重启或重新部署后清空。因此免费模式固定设置：

- `P1_FREE_READONLY=1`
- `P1_CLOSURE_WRITES=0`
- 不配置管理员 Token
- 不声称在线 SQLite 修改可以永久保存

公开查询、JD 解析、简历解析、人岗匹配、岗位分析、图谱展示和冻结数据读取仍可使用。管理员新增、审核和发布数据的线上写入按钮会被后端明确拒绝。需要修改正式数据时，通过 GitHub 分支和 PR 更新版本化文件、重新构建 `frontend/dist` 并部署。

免费 Web Service 闲置后会休眠，首次访问 API 可能需要约一分钟唤醒。静态前端本身不休眠。

## 部署步骤

1. 将本分支合并到 GitHub `main`；已连接仓库的现有 Render 服务会自动部署。
2. 若需要重新创建，在 Render Dashboard 选择 **New > Blueprint**，连接公开仓库 `https://github.com/idbsb/agent-framework` 并使用根目录的 `render.yaml`。
3. 部署成功后直接访问 Web Service 的 `onrender.com` 根地址，而不是 `/docs`。
4. 检查岗位、技能、JD 解析、简历解析和匹配页面；写入接口应返回 403。

修改前端源码后，在提交前执行 `cd frontend && npm ci && npm run build`，并一并提交更新后的 `frontend/dist`。

## 升级为可持久写入

只有需要在线新增、审核、发布并在重启后保留数据时，才升级后端并挂载 Persistent Disk，然后按 `docs/p1_production_deployment_checklist.md` 切换到付费生产配置。不要在免费实例上开启 `P1_CLOSURE_WRITES=1`。
