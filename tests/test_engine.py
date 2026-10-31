"""Unit test suite for AetherGit decision engine."""

import unittest
from src.engine import (
    score_and_rank_discussion,
    parse_diff_and_symbol_anchor,
    compute_code_fingerprint,
)


class TestSignalFilterAndDiffAnchor(unittest.TestCase):
    def test_score_and_rank_discussion_position_weighted(self):
        """Tests that 140+ reply discussions are prioritized by keywords and closing comments."""
        messages = [
            {"id": i, "author": f"user_{i}", "body": f"Random comment number {i}"}
            for i in range(1, 145)
        ]
        # Insert critical decision signals
        messages[10] = {
            "id": 11,
            "author": "perf_bot",
            "body": "Benchmark shows the Rust rewrite is 2x slower on big files, rejected.",
            "is_maintainer": False,
        }
        messages[143] = {
            "id": 144,
            "author": "maintainer_lead",
            "body": "Agreed, we will revert #1901 and keep the C parser.",
            "is_maintainer": True,
        }

        ranked = score_and_rank_discussion(messages, top_k=5)
        self.assertLessEqual(len(ranked), 5)
        self.assertGreater(len(ranked), 0)

        # Confirm the critical signal comments were selected
        ids = [m["id"] for m in ranked]
        self.assertIn(11, ids)
        self.assertIn(144, ids)

        # Confirm chronological order preservation
        self.assertEqual(ids, sorted(ids))

    def test_score_and_rank_never_returns_empty(self):
        """Tests that ranking never returns empty for non-empty input."""
        msgs = [{"id": 1, "body": "Hello world"}]
        ranked = score_and_rank_discussion(msgs, top_k=3)
        self.assertEqual(len(ranked), 1)

    def test_parse_diff_multiline_hunk_and_c_symbol(self):
        """Tests multi-line hunk (@@ -40,80 +40,80 @@) and C function symbol extraction."""
        diff_header = """diff --git a/parser/core.c b/parser/core.c
--- a/parser/core.c
+++ b/parser/core.c
@@ -40,80 +40,80 @@ int parse_token_stream(TokenStream* stream) {
"""
        code = """int parse_token_stream(TokenStream* stream) {
    // Process tokens in C
    return 0;
}"""
        res = parse_diff_and_symbol_anchor(diff_header, code)
        self.assertEqual(res["old_file"], "parser/core.c")
        self.assertEqual(res["new_file"], "parser/core.c")
        self.assertEqual(res["old_start"], 40)
        self.assertEqual(res["old_lines"], 80)
        self.assertEqual(res["new_start"], 40)
        self.assertEqual(res["new_lines"], 80)
        self.assertEqual(res["function_symbol"], "parse_token_stream")
        self.assertTrue(len(res["code_hash"]) > 0)

    def test_parse_diff_single_line_hunk_and_python_symbol(self):
        """Tests single-line hunk (@@ -40 +40 @@) and Python function symbol extraction."""
        diff_header = """diff --git a/compiler/scope.py b/compiler/scope.py
rename from compiler/scope.py
rename to compiler/ast_scope.py
@@ -40 +40 @@
"""
        code = """def compile_comprehension_scope(node, context):
    pass
"""
        res = parse_diff_and_symbol_anchor(diff_header, code)
        self.assertTrue(res["is_rename"])
        self.assertEqual(res["old_file"], "compiler/scope.py")
        self.assertEqual(res["new_file"], "compiler/ast_scope.py")
        self.assertEqual(res["old_start"], 40)
        self.assertEqual(res["old_lines"], 1)  # Default for single-line hunk
        self.assertEqual(res["new_start"], 40)
        self.assertEqual(res["new_lines"], 1)
        self.assertEqual(res["function_symbol"], "compile_comprehension_scope")


# Pytest top-level test discovery compatibility
def test_pytest_diff_anchor_multiline():
    suite = TestSignalFilterAndDiffAnchor()
    suite.test_parse_diff_multiline_hunk_and_c_symbol()


def test_pytest_diff_anchor_singleline():
    suite = TestSignalFilterAndDiffAnchor()
    suite.test_parse_diff_single_line_hunk_and_python_symbol()


if __name__ == "__main__":
    unittest.main()
