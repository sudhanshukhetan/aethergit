"""Unit test suite for AetherGit decision engine."""

import unittest
from src.engine import (
    score_and_rank_discussion,
    parse_diff_and_symbol_anchor,
    compute_code_fingerprint,
    relink_symbol_across_repo,
    resolve_contributor_identities,
    verify_source_traceability,
    detect_local_gemma_model,
    extract_decision_record_with_gemma,
    evaluate_pr_regression_with_gemma,
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


class TestGemmaOllamaInference(unittest.TestCase):
    def test_detect_local_gemma_model(self):
        """Tests that detect_local_gemma_model handles CI or offline Ollama server gracefully."""
        res = detect_local_gemma_model("gemma4:e4b")
        self.assertIn("available", res)
        self.assertIn("model", res)
        self.assertTrue("gemma" in res["model"].lower())

    def test_extract_decision_record_deterministic_gate(self):
        """Tests that extract_decision_record returns MADR JSON fields in CI or fallback."""
        bundle = {
            "scenario_id": "slide_6_c_parser",
            "raw_text": "Issue #1832: Rust rewrite was 2x slower on big files compared to the C parser. Revert #1901.",
            "force_mock": True,
        }
        res = extract_decision_record_with_gemma(bundle, model_name="gemma4:e4b")
        self.assertIn("decided", res)
        self.assertIn("rejected", res)
        self.assertIn("why", res)
        self.assertIn("sources", res)
        self.assertIn("bot_warning", res)
        self.assertEqual(res["decided"], "Keep the C parser")
        self.assertEqual(res["rejected"], "Rewrite in Rust")

    def test_evaluate_pr_regression_guard(self):
        """Tests that PR repeating rejected alternative triggers warning bot alert."""
        decision_record = {
            "decided": "Keep the C parser",
            "rejected": "Rewrite in Rust",
            "why": "2x slower on big files compared to the C parser",
            "bot_warning": "Tried in 2022 and reverted: 2x slower. See #1901.",
        }
        # A PR proposing rewrite in rust
        pr_text = "PR #2450: Complete rewrite of token parser in Rust for memory safety."
        eval_res = evaluate_pr_regression_with_gemma(pr_text, decision_record)
        self.assertTrue(eval_res["is_regression"])
        self.assertGreaterEqual(eval_res["confidence"], 0.80)
        self.assertEqual(eval_res["alert_message"], "Tried in 2022 and reverted: 2x slower. See #1901.")

        # An innocent PR fixing a typo
        innocent_pr = "PR #2451: Fix documentation typo in README comments."
        innocent_eval = evaluate_pr_regression_with_gemma(innocent_pr, decision_record)
        self.assertFalse(innocent_eval["is_regression"])


class TestExamplesValidation(unittest.TestCase):
    def test_examples_directory_exists_and_valid(self):
        """Verifies Section 4.5 mandatory examples/ directory and JSON schema compliance."""
        import json
        import os

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_path = os.path.join(base_dir, "examples", "sample_input.json")
        actual_path = os.path.join(base_dir, "examples", "actual_output.json")

        self.assertTrue(os.path.exists(sample_path), "examples/sample_input.json must exist")
        self.assertTrue(os.path.exists(actual_path), "examples/actual_output.json must exist")

        with open(sample_path, "r", encoding="utf-8") as f:
            sample_data = json.load(f)
        with open(actual_path, "r", encoding="utf-8") as f:
            actual_data = json.load(f)

        self.assertIn("scenarios", sample_data)
        self.assertGreaterEqual(len(sample_data["scenarios"]), 2)
        self.assertIn("scenarios_recovered", actual_data)

        # Check Slide 6 benchmark scenario
        scenario_ids = [s["scenario_id"] for s in sample_data["scenarios"]]
        self.assertIn("slide_6_c_parser", scenario_ids)
        self.assertIn("pep_discussion_recovery", scenario_ids)

        # Process first scenario through engine
        first_scenario = sample_data["scenarios"][0]
        extracted = extract_decision_record_with_gemma(first_scenario, model_name="gemma4:e4b")
        self.assertEqual(extracted["decided"], "Keep the C parser")
        self.assertEqual(extracted["rejected"], "Rewrite in Rust")
        self.assertEqual(extracted["bot_warning"], "Tried in 2022 and reverted: 2x slower. See #1901.")

    def test_go_generics_scenario_validation(self):
        """Verifies Go generics benchmark scenario extraction and schema compliance."""
        go_bundle = {
            "scenario_id": "go_generics_contracts",
            "raw_text": "Go Issue #43651 & Design Discussion: Earlier proposals suggested C++-style template monomorphization and macro expansion for Go generics. Core maintainers rejected template macro expansion because unbounded monomorphization causes compiler slowdowns and massive binary code bloat. The language team decided on type parameter constraints via interfaces with dual-mode compilation. All proposals for macro-style template expansion without interface constraints were rejected.",
        }
        res = extract_decision_record_with_gemma(go_bundle, model_name="gemma4:e4b")
        self.assertIn("Type parameter", res["decided"])
        self.assertIn("template", res["rejected"].lower())
        self.assertTrue(res.get("traceability", {}).get("contiguous_match"))


class TestCliHelpers(unittest.TestCase):
    def test_cli_format_madr_markdown(self):
        """Tests that format_madr_markdown outputs standard MADR structure."""
        from src.cli import format_madr_markdown

        record = {
            "decided": "Keep C Parser",
            "rejected": "Rewrite in Rust",
            "why": "2x slower on big files",
            "sources": ["#1832", "#1901"],
            "verbatim_evidence": "2x slower on big files",
            "bot_warning": "Tried in 2022 and reverted: 2x slower. See #1901.",
        }
        md = format_madr_markdown(record)
        self.assertIn("# ADR: Keep C Parser", md)
        self.assertIn("Keep C Parser", md)
        self.assertIn("Rewrite in Rust", md)
        self.assertIn("2x slower on big files", md)

    def test_cli_compare_with_git_blame(self):
        """Tests that compare_with_git_blame contrasts git blame against AetherGit memory."""
        from src.cli import compare_with_git_blame

        record = {
            "decided": "Keep C Parser",
            "rejected": "Rewrite in Rust",
            "why": "2x slower on big files",
            "bot_warning": "Tried in 2022 and reverted: 2x slower. See #1901.",
        }
        comp = compare_with_git_blame("parser/core.c", 45, record)
        self.assertIn("standard_git_blame", comp)
        self.assertIn("aethergit_recovered_memory", comp)
        self.assertIn("0% architectural memory", comp["standard_git_blame"])
        self.assertIn("Keep C Parser", comp["aethergit_recovered_memory"])

    def test_cli_verify_examples_pipeline(self):
        """Tests verify_examples_pipeline programmatic validation."""
        from src.cli import verify_examples_pipeline

        res = verify_examples_pipeline()
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["scenarios_tested"], 2)


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


def test_pytest_gemma_model_and_inference():
    suite = TestGemmaOllamaInference()
    suite.test_detect_local_gemma_model()
    suite.test_extract_decision_record_deterministic_gate()
    suite.test_evaluate_pr_regression_guard()


def test_pytest_examples_directory_valid():
    suite = TestExamplesValidation()
    suite.test_examples_directory_exists_and_valid()


def test_pytest_cli_helpers():
    suite = TestCliHelpers()
    suite.test_cli_format_madr_markdown()
    suite.test_cli_compare_with_git_blame()
    suite.test_cli_verify_examples_pipeline()


if __name__ == "__main__":
    unittest.main()
