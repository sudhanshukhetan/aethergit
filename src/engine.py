"""AetherGit Core Engine - Problem 06: Open Source Decision Intelligence & Knowledge Recovery.

Architecture:
- Signal-Weighted Discussion Filtering (140+ reply mining)
- Git Diff & AST Symbol Anchoring (single-line and multi-line hunks, renames)
- Rename-Resilient Fuzzy Relinking (50% sig + 50% SequenceMatcher)
- Cross-Platform Contributor Identity Graph
- Contiguous Substring Verifiable Traceability
- Local Gemma (gemma4:e4b via Ollama) Inference
"""

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# Key decision/rejection vocabulary recognized by maintainers
DECISION_KEYWORDS = [
    "rejected",
    "revert",
    "slower",
    "benchmark",
    "instead",
    "veto",
    "keep",
    "abandon",
    "perf regression",
    "decision",
    "superseded",
]

# Diff hunk regex supporting both single-line (@@ -40 +40 @@) and multi-line (@@ -40,80 +40,80 @@)
HUNK_REGEX = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:\s*(.*))?")

# AST / Function signature regexes for C, Python, and Rust
FUNC_REGEXES = [
    re.compile(r"(?:def|async\s+def)\s+([a-zA-Z_]\w*)\s*\("),  # Python
    re.compile(r"(?:fn|pub\s+fn)\s+([a-zA-Z_]\w*)\s*(?:<[^>]+>)?\s*\("),  # Rust
    re.compile(r"(?:[\w\*]+)\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{?"),  # C / C++
]


def score_and_rank_discussion(
    messages: List[Union[Dict[str, Any], str]],
    top_k: int = 8,
) -> List[Dict[str, Any]]:
    """Scores and ranks long discussion threads (140+ replies) to prioritize decision signal.

    Solves Problem 06 Consideration #1:
    - Weights engineering rejection/decision terms (rejected, revert, slower, benchmark, etc.)
    - Adds position boost to the final 3 closing comments (where consensus settles)
    - Boosts core maintainer comments
    - Returns top-k messages in original chronological order
    - Never returns 0 messages if input is non-empty
    """
    if not messages:
        return []

    total = len(messages)
    scored: List[Tuple[float, int, Dict[str, Any]]] = []

    for idx, item in enumerate(messages):
        if isinstance(item, str):
            msg = {"id": idx + 1, "author": f"user_{idx+1}", "body": item, "is_maintainer": False}
        else:
            msg = dict(item)
            if "id" not in msg:
                msg["id"] = idx + 1

        body = (msg.get("body") or msg.get("text") or "").lower()
        score = 1.0  # Base visibility

        # Keyword matching
        for kw in DECISION_KEYWORDS:
            if kw in body:
                score += 2.5

        # Maintainer boost
        role = str(msg.get("role", "")).lower()
        author = str(msg.get("author", "")).lower()
        if (
            msg.get("is_maintainer")
            or "maintainer" in role
            or "owner" in role
            or "author" in role
            or author in ["gvanrossum", "torvalds", "maintainer", "core-team"]
        ):
            score += 3.0

        # Position weighting for closing consensus (last 3 comments)
        if idx >= max(0, total - 3):
            closing_rank = idx - (total - 3) + 1  # 1, 2, or 3
            score += 2.0 * closing_rank

        scored.append((score, idx, msg))

    # Sort descending by score, take top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = scored[: min(top_k, total)]

    # Re-sort chronologically by original index
    selected.sort(key=lambda x: x[1])

    # Ensure never returning 0 if input non-empty
    if not selected and messages:
        return [messages[-1] if isinstance(messages[-1], dict) else {"id": total, "body": str(messages[-1])}]

    return [item[2] for item in selected]


def normalize_code_snippet(code: str) -> str:
    """Strips comments and whitespace for canonical hashing."""
    lines = []
    for line in code.splitlines():
        cleaned = re.sub(r"//.*$|#.*$|/\*.*?\*/", "", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def compute_code_fingerprint(code: str) -> str:
    """Computes SHA-256 hash of normalized code."""
    normalized = normalize_code_snippet(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_function_symbol(header_tail: str, code_snippet: str) -> Optional[str]:
    """Extracts function/symbol name from diff hunk header tail or code snippet."""
    # First check diff hunk tail (e.g., '@@ -40,80 +40,80 @@ int parse_token_stream(...)')
    if header_tail:
        for reg in FUNC_REGEXES:
            m = reg.search(header_tail)
            if m:
                return m.group(1)
        # Fallback word token in header tail
        tokens = re.findall(r"\b([a-zA-Z_]\w*)\s*\(", header_tail)
        if tokens:
            return tokens[-1]

    # Check code snippet lines
    if code_snippet:
        for reg in FUNC_REGEXES:
            for line in code_snippet.splitlines():
                m = reg.search(line)
                if m:
                    return m.group(1)

    return None


def parse_diff_and_symbol_anchor(
    diff_header: str,
    code_snippet: str = "",
) -> Dict[str, Any]:
    """Parses Git diff headers, hunks, renames, and extracts AST symbol anchor.

    Handles:
    - Multi-line hunks: @@ -40,80 +40,80 @@
    - Single-line hunks: @@ -40 +40 @@
    - Rename headers: rename from / rename to
    - Function symbol extraction: parse_token_stream, compile_comprehension_scope
    - SHA-256 fingerprint of normalized code
    """
    res: Dict[str, Any] = {
        "old_file": None,
        "new_file": None,
        "is_rename": False,
        "old_start": 0,
        "old_lines": 1,
        "new_start": 0,
        "new_lines": 1,
        "function_symbol": None,
        "code_hash": compute_code_fingerprint(code_snippet) if code_snippet else "",
        "raw_hunk": None,
    }

    # Detect git rename headers
    rename_from = re.search(r"^rename from (.*)$", diff_header, re.MULTILINE)
    rename_to = re.search(r"^rename to (.*)$", diff_header, re.MULTILINE)
    if rename_from and rename_to:
        res["old_file"] = rename_from.group(1).strip()
        res["new_file"] = rename_to.group(1).strip()
        res["is_rename"] = True

    # Detect file paths in diff --git
    git_files = re.search(r"^diff --git a/(.*?) b/(.*?)$", diff_header, re.MULTILINE)
    if git_files:
        if not res["old_file"]:
            res["old_file"] = git_files.group(1).strip()
        if not res["new_file"]:
            res["new_file"] = git_files.group(2).strip()

    # Parse hunk header
    hunk_match = HUNK_REGEX.search(diff_header)
    header_tail = ""
    if hunk_match:
        res["raw_hunk"] = hunk_match.group(0)
        res["old_start"] = int(hunk_match.group(1))
        res["old_lines"] = int(hunk_match.group(2)) if hunk_match.group(2) else 1
        res["new_start"] = int(hunk_match.group(3))
        res["new_lines"] = int(hunk_match.group(4)) if hunk_match.group(4) else 1
        header_tail = hunk_match.group(5) or ""

    # Extract function symbol
    res["function_symbol"] = extract_function_symbol(header_tail, code_snippet)

    return res
