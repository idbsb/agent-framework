"""Zero-dependency browser interface for the job-skill agent framework."""
from __future__ import annotations

import html
import json
import cgi
import sys
import threading
import webbrowser
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .core import AgentPipeline, Database

ROOT = Path(__file__).resolve().parents[1]
# When packaged, keep team data beside the .exe instead of in PyInstaller's
# temporary extraction folder, so it persists across launches.
APP_DATA_DIR = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT) / "data"
DB_PATH = APP_DATA_DIR / "challenge_cup.db"

PAGE = """<!doctype html><html lang='zh-CN'><meta charset='utf-8'>
<title>挑战杯｜岗位技能 Agent｜持续更新版</title><style>
body{max-width:920px;margin:30px auto;font:16px 'Microsoft YaHei',sans-serif;color:#18263b;background:#f6f8fc}h1{color:#1359a6}section{background:#fff;border-radius:12px;padding:20px 24px;margin:16px 0;box-shadow:0 2px 12px #dbe3ef}label{display:block;margin:10px 0 5px;font-weight:bold}input,textarea,select,button{font:inherit;padding:9px;border:1px solid #b8c7dc;border-radius:7px;box-sizing:border-box}input,textarea,select{width:100%}textarea{height:110px}button{background:#1769c2;color:white;border:0;margin-top:12px;cursor:pointer}pre{white-space:pre-wrap;background:#f2f6fb;padding:14px;border-radius:7px}.tip{color:#52677f;font-size:14px}</style>
<body><h1>挑战杯：岗位技能 Agent <small style='font-size:16px;color:#1769c2'>持续更新版 V4</small></h1><p>真实 JD 可反复增量导入；刷新页面后数据概览和最近操作结果仍会保留。</p>
{dashboard}
<section><h2>① 导入或更新第一组 Excel（推荐）</h2><p class='tip'>新 JD 自动新增；相同 JD 编号自动更新且不重复。人工复核记录会保留，旧的自动技能会重新计算。</p><form method='post' action='/import-excel' enctype='multipart/form-data'><label>重点岗位真实JD库.xlsx</label><input name='jd_file' type='file' accept='.xlsx' required><label>岗位名称标准化表V1.1.xlsx</label><input name='standard_file' type='file' accept='.xlsx' required><button>导入 / 更新并提取技能</button></form></section>
<section><h2>兼容：导入 JSON</h2><form method='post' action='/import' enctype='multipart/form-data'><input name='json_file' type='file' accept='.json' required><button>导入 JSON 数据</button></form></section>
<section><h2>② 生成岗位画像</h2><form method='post' action='/profile'><label>岗位簇</label><input name='cluster' value='大模型与智能体开发' required><button>生成或更新画像</button></form></section>
<section><h2>③ 简历匹配</h2><form method='post' action='/match'><label>目标岗位簇</label><input name='cluster' value='大模型与智能体开发' required><label>粘贴简历文本（技能、项目、经历均可）</label><textarea name='resume' placeholder='例如：Python；LangGraph；RAG；向量数据库；Docker；FastAPI' required></textarea><button>开始匹配</button></form></section>
<section><h2>④ 人工复核</h2><p class='tip'>第一组可在这里确认、驳回或新增一条 JD 的技能，下一轮画像会使用修正结果。</p><form method='post' action='/review'><label>JD 编号</label><input name='job_id' placeholder='例如 AGENT001' required><label>技能名称</label><input name='skill' placeholder='例如 Kubernetes' required><label>处理结果</label><select name='decision'><option value='confirm'>确认抽取正确</option><option value='reject'>驳回抽取结果</option><option value='add'>人工补充技能</option></select><label>审核人 / 原因（可选）</label><input name='reviewer' placeholder='例如 第一组；JD明确要求'><button>保存复核结果</button></form></section>{result}</body></html>"""

def pipeline():
    db = Database(DB_PATH); db.init(); return db, AgentPipeline(db)

def render(result=None):
    db, agent = pipeline()
    try:
        status = agent.status()
        saved = status.get("last_result") or {}
    finally:
        db.close()
    last = status.get("last_import") or {}
    dashboard = """<section><h2>数据概览</h2>
      <p><b>JD 总数：</b>{jobs}　<b>岗位簇：</b>{clusters}　<b>技术领域：</b>{domains}　<b>有效技能：</b>{skills}</p>
      <p class='tip'>最近一次导入：处理 {processed} 条，新增 {added} 条，更新 {updated} 条，未变化 {unchanged} 条；时间：{updated_at}</p>
      <p class='tip'>数据更新接口：POST /api/v1/jobs/import　状态接口：GET /api/v1/status</p></section>""".format(
        jobs=status["job_count"], clusters=status["cluster_count"], domains=status["domain_count"], skills=status["skill_count"],
        processed=last.get("processed", 0), added=last.get("added", 0), updated=last.get("updated", 0),
        unchanged=last.get("unchanged", 0), updated_at=html.escape(str(last.get("imported_at", "尚未导入"))))
    result_data = result if result is not None else saved
    result_html = "<p class='tip'>等待操作。</p>" if not result_data else "<h2>最近一次操作结果</h2><pre>" + html.escape(json.dumps(result_data, ensure_ascii=False, indent=2)) + "</pre>"
    return PAGE.replace("{dashboard}", dashboard).replace("{result}", result_html).encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def send_page(self, result=None):
        body = render(result); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/v1/status":
            db, agent = pipeline()
            try: self.send_json(agent.status())
            finally: db.close()
        elif path == "/": self.send_page()
        else: self.send_json({"error": "not_found", "path": path}, 404)
    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/v1/jobs/import":
            length = int(self.headers.get("Content-Length", 0))
            db, agent = pipeline()
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                records = payload.get("jobs", []) if isinstance(payload, dict) else payload
                if not isinstance(records, list): raise ValueError("jobs 必须是 JSON 数组")
                self.send_json(agent.import_jobs(records, source="api"))
            except Exception as exc: self.send_json({"error": str(exc)}, 400)
            finally: db.close()
            return
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            fields = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type})
            get = lambda k: fields.getvalue(k, "")
        else:
            length = int(self.headers.get("Content-Length", 0)); fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            get = lambda k: fields.get(k, [""])[0]
        db, agent = pipeline()
        try:
            if path == "/import":
                upload = fields["json_file"]
                result = agent.import_jobs(json.loads(upload.file.read().decode("utf-8-sig")), source="json")
            elif path == "/import-excel":
                result = agent.import_excel(fields["jd_file"].file.read(), fields["standard_file"].file.read())
            elif path == "/profile": result = agent.build_profile(get("cluster"))
            elif path == "/match": result = agent.match(get("cluster"), get("resume"))
            elif path == "/review": agent.review(get("job_id"), get("skill"), get("decision"), get("reviewer")); result = {"状态": "已保存；请重新生成岗位画像。"}
            else: result = {"错误": "未知操作", "path": path}
        except Exception as exc: result = {"错误": str(exc), "path": path}
        db.set_state("last_ui_result", result)
        db.close()
        self.send_response(303); self.send_header("Location", "/"); self.end_headers()

def main():
    # Port 0 asks Windows for an available local port, so a previous launch
    # or another app cannot make the double-click launcher fail silently.
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Timer(.5, lambda: webbrowser.open(url)).start()
    print("网页已打开。关闭此窗口即可停止服务。")
    server.serve_forever()

def self_test() -> int:
    """Packaged-app smoke test: starts the actual HTTP server and fetches its page."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        conn.request("GET", "/")
        response = conn.getresponse()
        return 0 if response.status == 200 and b"Agent" in response.read() else 1
    finally:
        server.shutdown(); server.server_close()

if __name__ == "__main__": main()
