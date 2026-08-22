import http.client
import json
import threading
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook
from agent_framework.ui_server import Handler, ThreadingHTTPServer


class UiServerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch("agent_framework.ui_server.DB_PATH", Path(self.temp_dir.name) / "web.db")
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_server_uses_a_free_local_port(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        try:
            self.assertGreater(server.server_address[1], 0)
        finally:
            server.server_close()

    def test_excel_import_route_is_not_reported_as_unknown(self):
        def workbook_bytes(headers, row):
            wb = Workbook(); ws = wb.active; ws.append(headers); ws.append(row)
            out = BytesIO(); wb.save(out); return out.getvalue()
        jd = workbook_bytes(["JD编号", "原始岗位名称", "工作职责", "必备技能"], ["T-JD-1", "AI Agent开发工程师", "开发Agent", "Python；RAG"])
        standard = workbook_bytes(["原始岗位名称", "标准岗位名称", "岗位族", "技术领域"], ["AI Agent开发工程师", "AI Agent开发工程师", "大模型与智能体开发", "Agent,LLM"])
        boundary = "----agent-test-boundary"
        def part(name, filename, data):
            return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n".encode() + data + b"\r\n")
        body = part("jd_file", "jd.xlsx", jd) + part("standard_file", "standard.xlsx", standard) + f"--{boundary}--\r\n".encode()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
            conn.request("POST", "/import-excel", body, {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))})
            response = conn.getresponse()
            self.assertEqual(response.status, 303)
            response.read()
            conn.request("GET", "/")
            refreshed = conn.getresponse().read().decode("utf-8")
            self.assertIn("最近一次导入", refreshed)
            self.assertIn("T-JD-1", refreshed)
            self.assertNotIn("未知操作", refreshed)
        finally:
            server.shutdown(); server.server_close()

    def test_json_update_api_and_status_survive_refresh(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            payload = json.dumps({"jobs": [{"id": "API-JD-1", "原始岗位名": "Agent工程师", "岗位簇": "智能体", "技能摘要": "Python"}]}, ensure_ascii=False).encode("utf-8")
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1])
            conn.request("POST", "/api/v1/jobs/import", payload, {"Content-Type": "application/json", "Content-Length": str(len(payload))})
            response = conn.getresponse()
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertEqual(data["added"], 1)
            conn.request("GET", "/api/v1/status")
            status = json.loads(conn.getresponse().read().decode("utf-8"))
            self.assertEqual(status["job_count"], 1)
            self.assertEqual(status["last_import"]["added"], 1)
        finally:
            server.shutdown(); server.server_close()


if __name__ == "__main__":
    unittest.main()
