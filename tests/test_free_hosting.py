"""Free single-service hosting contract."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import FileResponse

from src.api.app import serve_frontend
from src.closure.settings import free_readonly, production


class FreeHostingTest(unittest.TestCase):
    def test_render_without_disk_fails_safe_to_read_only(self):
        with patch.dict(os.environ, {"RENDER": "true", "P1_CLOSURE_WRITES": "0",
                                    "P1_STORAGE_DIR": ""}, clear=False):
            self.assertTrue(free_readonly())
            self.assertFalse(production())

    def test_render_write_switch_cannot_use_ephemeral_local_auth(self):
        with patch.dict(os.environ, {"RENDER": "true", "P1_CLOSURE_WRITES": "1",
                                    "P1_STORAGE_DIR": ""}, clear=False):
            self.assertFalse(free_readonly())
            self.assertTrue(production())

    def test_frontend_and_spa_routes_are_served(self):
        root = serve_frontend("")
        nested = serve_frontend("match")
        asset = next((Path(__file__).parents[1] / "frontend/dist/assets").glob("*.js"))
        static = serve_frontend(f"assets/{asset.name}")
        data = serve_frontend("data/job_analysis_v1.json")
        self.assertIsInstance(root, FileResponse)
        self.assertEqual(root.path, nested.path)
        self.assertEqual(Path(static.path), asset)
        self.assertEqual(data.headers["cache-control"], "no-cache")

    def test_unknown_api_is_not_rewritten_to_html(self):
        with self.assertRaises(HTTPException) as raised:
            serve_frontend("api/not-real")
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
