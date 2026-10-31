"""Unit test suite for AetherGit decision engine."""

import unittest
from src.engine import (
    score_and_rank_discussion,
    parse_diff_and_symbol_anchor,
    compute_code_fingerprint,
    relink_symbol_across_repo,
    resolve_contributor_identities,
    verify_source_traceability,
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


class TestRenameRelinkerAndIdentity(unittest.TestCase):
    def test_relink_symbol_across_rename_and_edits(self):
        """Tests that a function in parser/core.c moved to src/lexer/fast_core.c and edited relinks >= 0.60."""
        sig = "parse_token_stream"
        old_body = """
        int parse_token_stream(TokenStream* ts) {
            Token t;
            while (next_token(ts, &t)) {
                process_token(&t);
            }
            return 0;
        }
        """
        # Refactored candidate with slight edits in body
        candidates = [
            {
                "file": "src/lexer/fast_core.c",
                "function_symbol": "parse_token_stream",
                "code": """
                int parse_token_stream(TokenStream* ts) {
                    Token t;
                    // optimized buffer iteration
                    while (fast_next_token(ts, &t)) {
                        process_token_fast(&t);
                    }
                    return 0;
                }
                """,
                "lines": (45, 125),
            },
            {
                "file": "src/utils/unrelated.c",
                "function_symbol": "unrelated_util",
                "code": "void unrelated_util() {}",
                "lines": (1, 10),
            },
        ]
        match = relink_symbol_across_repo(sig, old_body, candidates, threshold=0.60)
        self.assertIsNotNone(match)
        self.assertEqual(match["file"], "src/lexer/fast_core.c")
        self.assertEqual(match["function_symbol"], "parse_token_stream")
        self.assertGreaterEqual(match["confidence"], 0.70)
        self.assertTrue(match["relinked"])

    def test_resolve_contributor_identities(self):
        """Tests unifying GitHub handle, Git email, and discuss forum name into single canonical profile."""
        participants = [
            {"github": "gvanrossum", "email": "guido@python.org"},
            {"forum_name": "Guido van Rossum", "email": "guido@python.org"},
            "Guido van Rossum <guido@python.org> (@gvanrossum)",
            {"github": "kushagar", "email": "kushagar@example.com", "name": "Kushagar"},
        ]
        res = resolve_contributor_identities(participants)
        canonical = res["canonical_profiles"]
        lookup = res["lookup_map"]

        self.assertIn("gvanrossum", canonical)
        prof = canonical["gvanrossum"]
        self.assertEqual(prof["github"], "gvanrossum")
        self.assertIn("guido@python.org", prof["emails"])
        self.assertIn("guido van rossum", lookup)
        self.assertIn("guido@python.org", lookup)
        self.assertIn("@gvanrossum", lookup)

    def test_verify_source_traceability_success(self):
        """Tests contiguous phrase matching and word overlap for genuine evidence."""
        raw_corpus = """
        Issue #1832: Benchmark results are in.
        The Rust rewrite branch was 2x slower on big files compared to the C parser.
        We must revert #1901 and keep the C parser for production stability.
        """
        record = {
            "decided": "Keep the C parser",
            "rejected": "Rewrite in Rust",
            "why": "2x slower on big files compared to the C parser",
            "verbatim_evidence": "2x slower on big files compared to the C parser",
        }
        res = verify_source_traceability(record, raw_corpus)
        self.assertTrue(res["verified"])
        self.assertTrue(res["contiguous_match"])
        self.assertGreaterEqual(res["word_overlap"], 0.80)

    def test_verify_source_traceability_rejects_hallucination(self):
        """Tests that hallucinated quotes are rejected by contiguous validator."""
        raw_corpus = "The C parser is currently used in our engine."
        hallucinated_record = {
            "decided": "Keep C parser",
            "why": "Rust causes too many memory leaks and concurrency locks",
            "verbatim_evidence": "Rust causes too many memory leaks and concurrency locks",
        }
        res = verify_source_traceability(hallucinated_record, raw_corpus)
        self.assertFalse(res["verified"])
        self.assertFalse(res["contiguous_match"])


# Pytest top-level test discovery compatibility
def test_pytest_diff_anchor_multiline():
    suite = TestSignalFilterAndDiffAnchor()
    suite.test_parse_diff_multiline_hunk_and_c_symbol()


def test_pytest_diff_anchor_singleline():
    suite = TestSignalFilterAndDiffAnchor()
    suite.test_parse_diff_single_line_hunk_and_python_symbol()


def test_pytest_relink_symbol():
    suite = TestRenameRelinkerAndIdentity()
    suite.test_relink_symbol_across_rename_and_edits()


def test_pytest_resolve_identities():
    suite = TestRenameRelinkerAndIdentity()
    suite.test_resolve_contributor_identities()


def test_pytest_verify_traceability():
    suite = TestRenameRelinkerAndIdentity()
    suite.test_verify_source_traceability_success()
    suite.test_verify_source_traceability_rejects_hallucination()


if __name__ == "__main__":
    unittest.main()
