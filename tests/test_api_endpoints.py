"""Unit tests for Flask REST API endpoints and live Gemma/Gemini integration."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app import (
    app,
    check_pr_regression,
    extract_first_json_block,
    normalize_text,
    server_quote_check,
)


class TestApiEndpoints(unittest.TestCase):
    """Verifies all backend REST endpoints and edge cases."""

    def setUp(self):
        self.client = app.test_client()

    def test_get_root_serves_html(self):
        """GET / must return HTTP 200 with HTML content."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"AetherGit", res.data)

    def test_status_missing_key_returns_not_configured(self):
        """GET /api/status without GEMINI_API_KEY returns live: false, not configured."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "AI_PROVIDER": "gemini"}):
            res = self.client.get("/api/status")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertFalse(data.get("live"))
            self.assertEqual(data.get("reason"), "not configured")

    @patch("requests.get")
    def test_status_live_model_check(self, mock_get):
        """GET /api/status with valid key returns live: true when model endpoint answers 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-mock", "AI_PROVIDER": "gemini"}):
            res = self.client.get("/api/status")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("live"))
            self.assertEqual(data.get("model"), "gemma-4-26b-a4b-it")

    def test_extract_empty_input_rejected_400(self):
        """POST /api/extract with empty or whitespace-only input returns 400."""
        res = self.client.post("/api/extract", json={"discussion_text": "   "})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertEqual(data.get("error"), "Paste a discussion first.")

    def test_extract_too_long_input_rejected_413(self):
        """POST /api/extract with text > 12,000 characters returns 413."""
        huge_text = "A" * 12001
        res = self.client.post("/api/extract", json={"discussion_text": huge_text})
        self.assertEqual(res.status_code, 413)
        data = res.get_json()
        self.assertEqual(data.get("error"), "Discussion too long (max 12,000 characters).")

    def test_extract_missing_gemini_key_returns_503(self):
        """POST /api/extract without GEMINI_API_KEY returns 503."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "AI_PROVIDER": "gemini"}):
            res = self.client.post("/api/extract", json={"discussion_text": "Alice: test thread"})
            self.assertEqual(res.status_code, 503)
            data = res.get_json()
            self.assertEqual(data.get("error"), "Live AI is not configured on the server.")

    @patch("requests.post")
    def test_extract_google_429_rate_limit(self, mock_post):
        """POST /api/extract propagates Google 429 rate limit cleanly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "AI_PROVIDER": "gemini"}):
            res = self.client.post("/api/extract", json={"discussion_text": "Alice: test thread"})
            self.assertEqual(res.status_code, 429)
            data = res.get_json()
            self.assertEqual(data.get("error"), "Rate limit reached. Try again in a minute.")

    @patch("requests.post")
    def test_extract_live_success_with_json_fences(self, mock_post):
        """POST /api/extract parses JSON wrapped in ```json ``` markdown code fences."""
        ai_response_text = """Here is the result:
```json
{
  "decided": "Keep the C parser",
  "rejected": "Rewrite in Rust",
  "reason": "Rust was 2x slower on big files.",
  "quote": "Rust was 2x slower on big files",
  "file": "parser/core.c"
}
```
"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "internal thought", "thought": True},
                            {"text": ai_response_text},
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        sample_disc = "Asha: Proposal to rewrite in Rust. Ravi: Rust was 2x slower on big files. Asha: Keep the C parser."
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "AI_PROVIDER": "gemini"}):
            res = self.client.post("/api/extract", json={"discussion_text": sample_disc})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data.get("source"), "live")
            self.assertEqual(data.get("model"), "gemma-4-26b-a4b-it")
            record = data.get("record", {})
            self.assertEqual(record.get("decided"), "Keep the C parser")
            self.assertEqual(record.get("rejected"), "Rewrite in Rust")
            self.assertEqual(record.get("file"), "parser/core.c")

            # Check quote check verification
            qc = data.get("quote_check", {})
            self.assertTrue(qc.get("contiguous"))
            self.assertEqual(qc.get("word_overlap"), 1.0)

    @patch("requests.post")
    def test_extract_retries_on_bad_json(self, mock_post):
        """POST /api/extract retries once when model returns malformed JSON on first attempt."""
        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Not valid json at all!"}]}}]
        }

        good_resp = MagicMock()
        good_resp.status_code = 200
        good_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"decided":"Use JSON","rejected":"XML","reason":"Simpler","quote":"JSON is simpler","file":"config.py"}'
                            }
                        ]
                    }
                }
            ]
        }

        mock_post.side_effect = [bad_resp, good_resp]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "AI_PROVIDER": "gemini"}):
            res = self.client.post("/api/extract", json={"discussion_text": "Bob: JSON is simpler than XML."})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data["record"]["decided"], "Use JSON")
            self.assertEqual(mock_post.call_count, 2)

    def test_server_quote_check_contiguous_and_word_overlap(self):
        """Verifies server-side quote check contiguous requirement and overlap ratio."""
        discussion = "PR #1901 was reverted because the Rust rewrite was 2x slower on big files compared to the C parser."

        # Case 1: Exact contiguous quote >= 4 words
        qc1 = server_quote_check("2x slower on big files compared to the C parser", discussion)
        self.assertTrue(qc1["contiguous"])
        self.assertEqual(qc1["word_overlap"], 1.0)

        # Case 2: Substring with punctuation stripped
        qc2 = server_quote_check('"2x slower on big files"', discussion)
        self.assertTrue(qc2["contiguous"])
        self.assertEqual(qc2["word_overlap"], 1.0)

        # Case 3: Fewer than 4 words fails contiguous check
        qc3 = server_quote_check("2x slower files", discussion)
        self.assertFalse(qc3["contiguous"])
        self.assertEqual(qc3["word_overlap"], 1.0)

        # Case 4: Non-contiguous / hallucinated words
        qc4 = server_quote_check("2x slower on massive distributed servers", discussion)
        self.assertFalse(qc4["contiguous"])
        self.assertLess(qc4["word_overlap"], 1.0)

    def test_json_block_extraction_utility(self):
        """extract_first_json_block finds and parses balanced JSON."""
        raw = 'Here is the JSON:\n```json\n{"decided": "A", "nested": {"key": "val"}}\n```\nExtra notes.'
        parsed = extract_first_json_block(raw)
        self.assertEqual(parsed["decided"], "A")
        self.assertEqual(parsed["nested"]["key"], "val")

    def test_pr_firewall_whole_word_matching(self):
        """Tests PR firewall line range and whole-word matching logic (Trust vs Rust)."""
        rejected = "Rewrite in Rust"
        reason = "2x slower on big files"

        # Case 1: "Trust the parser" at line 45 must NOT match "Rust"
        res1 = check_pr_regression("Trust the parser", 45, rejected, reason)
        self.assertEqual(res1["status"], "SAFE")
        self.assertFalse(res1["is_regression"])

        # Case 2: "Fix typo in README" at line 45 is SAFE
        res2 = check_pr_regression("Fix typo in README", 45, rejected, reason)
        self.assertEqual(res2["status"], "SAFE")
        self.assertFalse(res2["is_regression"])

        # Case 3: "Rewrite parser in Rust" at line 45 is BLOCKED
        res3 = check_pr_regression("Rewrite parser in Rust", 45, rejected, reason)
        self.assertEqual(res3["status"], "BLOCK")
        self.assertTrue(res3["is_regression"])
        self.assertIn("Rewrite in Rust", res3["message"])

        # Case 4: Line outside 40..120 is SAFE
        res4 = check_pr_regression("Rewrite parser in Rust", 150, rejected, reason)
        self.assertEqual(res4["status"], "SAFE")
        self.assertFalse(res4["is_regression"])

        # Case 5: Exact boundary checks: 39 -> SAFE, 40 -> BLOCK, 120 -> BLOCK, 121 -> SAFE
        self.assertEqual(check_pr_regression("Rewrite parser in Rust", 39, rejected, reason)["status"], "SAFE")
        self.assertEqual(check_pr_regression("Rewrite parser in Rust", 40, rejected, reason)["status"], "BLOCK")
        self.assertEqual(check_pr_regression("Rewrite parser in Rust", 120, rejected, reason)["status"], "BLOCK")
        self.assertEqual(check_pr_regression("Rewrite parser in Rust", 121, rejected, reason)["status"], "SAFE")

        # Case 6: No decision extracted yet
        res_no_dec = check_pr_regression("Rewrite in Rust", 45, "")
        self.assertEqual(res_no_dec["status"], "NO_DECISION")
        self.assertIn("No decision saved yet", res_no_dec["message"])


if __name__ == "__main__":
    unittest.main()
