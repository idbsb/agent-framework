"""Exercise actual ASGI routing and Pydantic validation without adding httpx."""
import asyncio
import json
import os
import unittest
from unittest.mock import patch

from src.api.app import app
from src.api.closure import get_closure
import test_p1_closure as fixtures


async def request(method, path, body=None, client="127.0.0.1"):
    output = []
    async def receive():
        return dict(type="http.request", body=json.dumps(body or {}).encode(), more_body=False)
    async def send(message):
        output.append(message)
    route, _, query = path.partition("?")
    await app(dict(type="http", asgi={"version": "3.0"}, http_version="1.1", method=method, scheme="http",
                   path=route, raw_path=route.encode(), query_string=query.encode(), root_path="",
                   headers=[(b"content-type", b"application/json")], client=(client, 1000), server=("127.0.0.1", 8000)), receive, send)
    status = next(m["status"] for m in output if m["type"] == "http.response.start")
    data = json.loads(b"".join(m.get("body", b"") for m in output if m["type"] == "http.response.body"))
    return status, data


class ApiTest(unittest.TestCase):
    setUpClass = fixtures.ClosureTest.__dict__["setUpClass"]
    setUp = fixtures.ClosureTest.setUp
    def tearDown(self):
        app.dependency_overrides.clear()
        fixtures.ClosureTest.tearDown(self)

    def call(self, method, path, body=None, client="127.0.0.1"):
        app.dependency_overrides[get_closure] = lambda: self.service
        with patch.dict(os.environ, P1_CLOSURE_WRITES="1"):
            return asyncio.run(request(method, "/api/closure"+path, body, client))

    def test_http_validation_and_not_found(self):
        self.assertEqual(self.call("POST", "/evidence", {"job_id": "empty"})[0], 422)
        self.assertEqual(self.call("GET", "/candidate/missing")[0], 404)
        self.assertEqual(self.call("POST", "/profiles/run", {"job_title": "missing"})[0], 404)
        self.assertEqual(self.call("GET", "/nonsense/missing")[0], 400)

    def test_local_write_guard(self):
        self.assertEqual(self.call("POST", "/evidence", fixtures.jd("local"), client="203.0.113.1")[0], 403)

    def test_real_api_discover_review_and_conflict(self):
        for i in range(3):
            self.assertEqual(self.call("POST", "/evidence", fixtures.jd(f"c{i}", title=""))[0], 200)
        status, candidates = self.call("POST", "/discovery/run")
        self.assertEqual(status, 200)
        item = candidates[0]
        path = f'/candidate/{item["id"]}/actions'
        payload = dict(expected_version=item["version"], expected_revision=0, action="nope")
        self.assertEqual(self.call("POST", path, payload)[0], 400)
        payload["action"] = "submit"
        self.assertEqual(self.call("POST", path, payload)[0], 200)
        self.assertEqual(self.call("POST", path, payload)[0], 409)
        self.assertEqual(self.call("GET", f'/candidate/{item["id"]}/diff?before=1&after=999')[0], 404)
        self.assertEqual(self.call("POST", f'/candidate/{item["id"]}/manual', dict(expected_version=1, expected_revision=1, definition={}))[0], 422)

    def test_malformed_skill_id_returns_422_not_500(self):
        for i in range(3):
            self.service.add_evidence(fixtures.jd(f"c{i}", title=""))
        item = self.service.discover()[0]
        manual = item["auto_definition"]
        manual["required_skills"][0]["skill_id"] = ["invalid"]
        status, _ = self.call("POST", f'/candidate/{item["id"]}/manual', dict(expected_version=1, expected_revision=0, definition=manual))
        self.assertEqual(status, 422)
