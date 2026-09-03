# 部署说明

## 1. 部署形态

本系统采用 React + FastAPI 的 Web 架构。开发环境可分别启动前后端；正式免费演示环境使用一个 Render Web Service，由 FastAPI 同域提供 API 与 `frontend/dist/` 中的前端生产构建。

- 在线演示：https://agent-framework-g8ij.onrender.com/
- API 文档：https://agent-framework-g8ij.onrender.com/docs
- 健康检查：https://agent-framework-g8ij.onrender.com/api/jobs
- 正式分支：`main`
- 参赛标签：`competition-final-v1.0`

Render 免费实例可能在闲置后休眠，首次访问通常需要等待唤醒。前端会对瞬时网络失败进行有限重试，图谱和动态演化读取失败时可展示随版本打包的最近正式静态结果；这提高了演示可用性，但不等于对第三方免费云服务作“永不断线”承诺。

## 2. 环境要求

| 软件 | 要求 | 本次验证版本 |
|---|---|---|
| 操作系统 | Windows 10/11 或常见 Linux | Windows |
| Python | 3.11–3.12 | 3.12.13 |
| Node.js | 20 及以上 | 24.18.0 |
| npm | 10 及以上 | 11.16.0 |
| Git | 2.x | 以本机可用版本为准 |

## 3. 获取固定版本

```bash
git clone https://github.com/idbsb/agent-framework.git
cd agent-framework
git checkout competition-final-v1.0
```

## 4. 后端安装与启动

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Linux/macOS：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

启动后访问 `http://127.0.0.1:8000/docs`。Windows 也可使用根目录 `start_system.bat` 启动本地系统。

## 5. 前端安装与启动

```powershell
cd frontend
npm ci
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。Vite 开发服务器将 API 请求转发到本地后端。生产构建命令：

```powershell
cd frontend
npm run build
```

构建结果位于 `frontend/dist/`。正式 Render Python 运行时不安装 Node，因此修改前端后必须在提交前重新生成并提交该目录。

## 6. 环境变量与数据库

本地默认值示例保存在根目录 `.env.example`，程序不会自动读取该文件，需由启动环境显式设置。

| 变量 | 免费公开演示值 | 说明 |
|---|---|---|
| `P1_ENV` | `local` | 免费只读模式，避免假装具备持久盘 |
| `P1_FREE_READONLY` | `1` | 强制公开实例只读 |
| `P1_CLOSURE_WRITES` | `0` | 关闭管理员在线写入 |
| `P1_CLOSURE_DB` | `data/p1_closure.sqlite3` | 本地 SQLite 路径；数据库不提交 Git |
| `CORS_ORIGINS` | 空 | 单一 Render 同源部署无需跨域 |
| `PYTHON_VERSION` | `3.12.13` | Render Python 版本 |

付费持久化模式还需要 `P1_STORAGE_DIR`、`P1_INITIALIZE_DB`、`P1_ADMIN_TOKEN` 和 `P1_ADMIN_NAME`。管理员令牌必须至少 32 个高熵 ASCII 字符，只存放在 Render Secret 中，禁止写入 Git、日志、URL 或任何 `VITE_*` 前端变量。

## 7. Render 正式部署

仓库根目录 `render.yaml` 已声明服务：

- Build Command：`pip install -r requirements.txt`
- Start Command：`uvicorn src.api.app:app --host 0.0.0.0 --port $PORT --workers 1`
- Health Check：`/api/jobs`
- Branch：`main`

部署步骤：

1. 在 Render 选择 **New > Blueprint**，连接公开仓库 `https://github.com/idbsb/agent-framework`。
2. 读取仓库根目录 `render.yaml` 创建或更新服务。
3. 核对环境变量为免费只读模式，不配置管理员令牌。
4. 部署完成后访问根地址，依次检查首页、岗位分析、图谱、动态演化、JD 解析、简历分析与人岗匹配。
5. 请求 `/api/jobs`、`/api/system/overview` 和 `/api/graph/job/AI%20Agent%E5%BC%80%E5%8F%91%E5%B7%A5%E7%A8%8B%E5%B8%88`，均应返回 HTTP 200。

`main` 更新会触发已有 Render 服务自动部署。比赛冻结后以 `competition-final-v1.0` 作为评审版本，不以赛后 `main` 的继续提交作为参赛内容。

## 8. 部署后验收与故障定位

- 页面无法打开：先访问 `/api/jobs`，免费实例冷启动时等待约一分钟后刷新。
- 页面出现“展示最近可用数据”：实时请求重试耗尽，当前是随版本打包的静态正式结果；服务恢复后重新加载页面。
- 解析或匹配失败：这些功能必须调用实时 FastAPI，确认后端已唤醒且没有 5xx。
- `ModuleNotFoundError`：确认使用同一 `.venv` 并重新安装 `requirements.txt`。
- 前端依赖错误：在 `frontend/` 执行 `npm ci`，不要删除或手改 `package-lock.json`。
- 端口占用：关闭占用 8000/5173 的旧进程，或为 Uvicorn/Vite 指定其他端口。
- 在线写入被拒绝：免费部署固定只读，这是数据安全设计，不是服务故障。

如需启用可持久写入的付费环境，必须挂载持久盘、保持单实例/单 worker，并按 `docs/p1_production_deployment_checklist.md` 完成认证、备份与重启恢复验收。
