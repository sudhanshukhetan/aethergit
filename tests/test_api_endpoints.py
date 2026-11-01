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

    def test_post_api_check_pr_invalid_slider(self):
        """POST /api/check-pr with invalid slider_val returns HTTP 400."""
        for invalid_val in ["abc", None, 0, 301]:
            res = self.client.post("/api/check-pr", json={"slider_val": invalid_val})
            self.assertEqual(res.status_code, 400, f"Expected 400 for slider_val={invalid_val}")
            data = res.get_json()
            self.assertIn("error", data)
            self.assertIn("slider_val must be a whole number from 1 to 300", data["error"])

    def test_post_endpoints_list_body_no_500(self):
        """All POST endpoints with JSON list body [1, 2, 3] return 200/400, never HTTP 500."""
        endpoints = ["/api/extract", "/api/evaluate-pep", "/api/relink", "/api/check-pr"]
        for ep in endpoints:
            res = self.client.post(ep, json=[1, 2, 3])
            self.assertIn(res.status_code, [200, 400], f"Endpoint {ep} returned {res.status_code}")
            self.assertNotEqual(res.status_code, 500)

    def test_post_api_evaluate_pep_custom_discussion(self):
        """POST /api/evaluate-pep with discussion_text does not return comprehension sample record."""
        custom_text = "We decided to keep Python 3.11 in CI because 3.12 broke numpy builds."
        res = self.client.post("/api/evaluate-pep", json={"discussion_text": custom_text})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertNotEqual(data.get("decided"), "Comprehension iteration variables have localized inner scope in Python 3")
        self.assertEqual(data.get("source"), "rule-based-fallback (not AI)")

    def test_post_api_extract_custom_issue(self):
        """POST /api/extract with custom issue_text does not return C parser record."""
        custom_issue = "users trust the login flow"
        res = self.client.post("/api/extract", json={"issue_text": custom_issue})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertNotEqual(data.get("decided"), "Keep the C parser")
        self.assertEqual(data.get("source"), "rule-based-fallback (not AI)")


if __name__ == "__main__":
    unittest.main()
