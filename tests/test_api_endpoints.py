"""Unit tests for Flask REST API endpoints in app.py."""

import unittest
from app import app


class TestApiEndpoints(unittest.TestCase):
    """Verifies all backend REST endpoints return HTTP 200 with correct schemas."""

    def setUp(self):
        self.client = app.test_client()

    def test_get_root_serves_html(self):
        """GET / must return HTTP 200 with HTML content."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"AetherGit", res.data)

    def test_get_api_status(self):
        """GET /api/status must return HTTP 200 and online status."""
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "online")
        self.assertEqual(data.get("mode"), "cached-demo")
        self.assertEqual(data.get("engine"), "cached demo data (no AI on the hosted server)")

    def test_post_api_extract(self):
        """POST /api/extract must extract MADR records and symbol anchors."""
        payload = {
            "issue_text": "Issue #1832: Benchmark showed Rust was 2x slower on big files. Revert #1901 and keep C parser.",
            "diff_header": "diff --git a/parser/core.c b/parser/core.c\n@@ -40,80 +40,80 @@ int parse_token_stream(TokenStream* ts)",
        }
        res = self.client.post("/api/extract", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("decided", data)
        self.assertIn("rejected", data)
        self.assertIn("why", data)
        self.assertIn("anchor", data)

    def test_post_api_evaluate_pep(self):
        """POST /api/evaluate-pep must evaluate custom discussion threads."""
        payload = {
            "corpus": "Discussion Thread: Variable leaking was rejected because it shadows outer variables unpredictably. Consensus decided localized scope in Python 3."
        }
        res = self.client.post("/api/evaluate-pep", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("decided", data)
        self.assertIn("rejected", data)
        self.assertIn("ranked_messages", data)

    def test_post_api_relink(self):
        """POST /api/relink must calculate similarity ratio and resolve identities."""
        payload = {"symbol": "parse_token_stream"}
        res = self.client.post("/api/relink", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("relink_match", data)
        self.assertIn("confidence", data["relink_match"])
        self.assertIn("resolved_identities", data)

    def test_post_api_check_pr(self):
        """POST /api/check-pr must detect architectural regression on critical anchors."""
        # Regression PR inside anchor range
        res = self.client.post("/api/check-pr", json={"pr_title": "rewrite in rust", "slider_val": 45})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("is_regression"))
        self.assertTrue(data.get("touches_anchor"))

        # Innocent PR inside anchor range (should NOT be marked regression)
        res_innocent = self.client.post("/api/check-pr", json={"pr_title": "Fix typo in README", "slider_val": 45})
        self.assertEqual(res_innocent.status_code, 200)
        data_innocent = res_innocent.get_json()
        self.assertFalse(data_innocent.get("is_regression"))
        self.assertTrue(data_innocent.get("touches_anchor"))

        # PR outside anchor range (e.g. line 130)
        res_outside = self.client.post("/api/check-pr", json={"pr_title": "rewrite in rust", "slider_val": 130})
        self.assertEqual(res_outside.status_code, 200)
        data_outside = res_outside.get_json()
        self.assertFalse(data_outside.get("is_regression"))
        self.assertFalse(data_outside.get("touches_anchor"))


if __name__ == "__main__":
    unittest.main()
