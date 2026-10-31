"""AetherGit Core Engine - Problem 06: Open Source Decision Intelligence & Knowledge Recovery.

Architecture:
- Signal-Weighted Discussion Filtering (140+ reply mining)
- Git Diff & AST Symbol Anchoring (single-line and multi-line hunks, renames)
- Rename-Resilient Fuzzy Relinking (50% sig + 50% SequenceMatcher)
- Cross-Platform Contributor Identity Graph
- Contiguous Substring Verifiable Traceability
- Local Gemma (gemma4:e4b via Ollama) Inference
"""

import difflib
import hashlib
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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


def relink_symbol_across_repo(
    sig: str,
    old_body: str,
    candidates: List[Dict[str, Any]],
    threshold: float = 0.60,
) -> Optional[Dict[str, Any]]:
    """Relinks an architectural decision to code when files are renamed AND edited.

    Solves Problem 06 Consideration #3:
    - Combines 50% function signature match + 50% normalized SequenceMatcher ratio
    - Threshold >= 0.60 allows link survival through refactoring and renaming
    """
    if not candidates:
        return None

    normalized_old = normalize_code_snippet(old_body)
    best_candidate: Optional[Dict[str, Any]] = None
    best_score = 0.0

    for cand in candidates:
        cand_symbol = cand.get("function_symbol") or ""
        cand_body = cand.get("code") or ""
        normalized_cand = normalize_code_snippet(cand_body)

        # 1. Signature similarity (0.0 to 1.0)
        sig_score = 0.0
        if sig and cand_symbol:
            if sig.lower() == cand_symbol.lower():
                sig_score = 1.0
            elif sig.lower() in cand_symbol.lower() or cand_symbol.lower() in sig.lower():
                sig_score = 0.75

        # 2. Body similarity using difflib SequenceMatcher (0.0 to 1.0)
        if normalized_old and normalized_cand:
            matcher = difflib.SequenceMatcher(None, normalized_old, normalized_cand)
            body_ratio = matcher.ratio()
        else:
            body_ratio = 1.0 if not normalized_old and not normalized_cand else 0.0

        # Hybrid confidence score: 50% signature + 50% body
        confidence = (0.5 * sig_score) + (0.5 * body_ratio)

        if confidence > best_score:
            best_score = confidence
            best_candidate = {
                "file": cand.get("file"),
                "function_symbol": cand_symbol,
                "lines": cand.get("lines", (1, 1)),
                "confidence": round(confidence, 4),
                "sig_score": round(sig_score, 4),
                "body_ratio": round(body_ratio, 4),
                "relinked": True,
            }

    if best_candidate and best_score >= threshold:
        return best_candidate

    return None


def resolve_contributor_identities(
    participants: List[Union[Dict[str, Any], str]],
) -> Dict[str, Any]:
    """Unifies contributor identities across GitHub handles, Git commit emails, and discuss.python.org.

    Solves Problem 06 Consideration #4:
    - Unifies @gvanrossum, guido@python.org, and Guido van Rossum into a canonical maintainer profile.
    - Handles handles, emails, and forum display names.
    """
    profiles: List[Dict[str, Any]] = []

    def normalize_token(s: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]", "", s).lower()

    for p in participants:
        if isinstance(p, str):
            # Parse string e.g. "Guido van Rossum <guido@python.org> (@gvanrossum)"
            emails = re.findall(r"[\w\.-]+@[\w\.-]+", p)
            handles = re.findall(r"@([a-zA-Z0-9_-]+)", p)
            clean_name = re.sub(r"<[^>]+>|@[a-zA-Z0-9_-]+", "", p).strip()
            item = {
                "name": clean_name or (handles[0] if handles else (emails[0] if emails else p)),
                "github": handles[0] if handles else None,
                "email": emails[0] if emails else None,
                "forum_name": clean_name or None,
            }
        else:
            item = dict(p)

        name = item.get("name") or item.get("forum_name") or ""
        github = (item.get("github") or "").lstrip("@")
        email = item.get("email") or ""
        forum_name = item.get("forum_name") or name

        # Collect keys to cluster
        keys = set()
        if github:
            keys.add(normalize_token(github))
        if email:
            keys.add(normalize_token(email.split("@")[0]))
            keys.add(email.lower())
        if name:
            keys.add(normalize_token(name))

        # Check if matches existing profile
        matched_profile = None
        for prof in profiles:
            if keys.intersection(prof["_cluster_keys"]):
                matched_profile = prof
                break

        if matched_profile is None:
            canonical_handle = github or (email.split("@")[0] if email else normalize_token(name))
            matched_profile = {
                "canonical_id": canonical_handle,
                "name": name or github or email,
                "github": github,
                "emails": [email] if email else [],
                "forum_names": [forum_name] if forum_name else [],
                "aliases": set(),
                "_cluster_keys": set(keys),
            }
            profiles.append(matched_profile)
        else:
            # Merge
            if github and not matched_profile["github"]:
                matched_profile["github"] = github
            if email and email not in matched_profile["emails"]:
                matched_profile["emails"].append(email)
            if forum_name and forum_name not in matched_profile["forum_names"]:
                matched_profile["forum_names"].append(forum_name)
            if name and not matched_profile["name"]:
                matched_profile["name"] = name
            matched_profile["_cluster_keys"].update(keys)

        if github:
            matched_profile["aliases"].add(f"@{github}")
            matched_profile["aliases"].add(github)
        if email:
            matched_profile["aliases"].add(email)
        if forum_name:
            matched_profile["aliases"].add(forum_name)

    # Clean internal keys and convert aliases to sorted list
    result: Dict[str, Any] = {"canonical_profiles": {}, "lookup_map": {}}
    for prof in profiles:
        prof.pop("_cluster_keys", None)
        prof["aliases"] = sorted(list(prof["aliases"]))
        cid = prof["canonical_id"]
        result["canonical_profiles"][cid] = prof
        for alias in prof["aliases"]:
            result["lookup_map"][alias.lower()] = cid

    return result


def verify_source_traceability(
    decision_record: Dict[str, Any],
    raw_corpus: str,
) -> Dict[str, Any]:
    """Verifies that extracted decisions and verbatim evidence genuinely exist in original discussions.

    Solves Problem 06 Consideration #5:
    - Verifies >=60% content-word overlap
    - Verifies a contiguous phrase match (>=4 consecutive words) from verbatim_evidence inside raw_corpus
    - Rejects hallucinated AI summaries
    """
    evidence = decision_record.get("verbatim_evidence") or decision_record.get("quote") or ""
    why_text = decision_record.get("why") or ""
    corpus_lower = raw_corpus.lower()

    # 1. Contiguous multi-word quote verification (>=4 consecutive words)
    contiguous_match = False
    matched_phrase = ""
    evidence_words = re.findall(r"\b\w+\b", evidence.lower())

    if len(evidence_words) >= 4:
        # Check window sizes of 4 to min(8, len(evidence_words))
        window_size = 4
        for i in range(len(evidence_words) - window_size + 1):
            phrase = " ".join(evidence_words[i : i + window_size])
            # Check regex with flexible whitespace
            pattern = r"\b" + r"\s+".join(re.escape(w) for w in evidence_words[i : i + window_size]) + r"\b"
            if re.search(pattern, corpus_lower):
                contiguous_match = True
                matched_phrase = phrase
                break
    elif len(evidence_words) > 0:
        # For short evidence (<4 words), match entire phrase
        phrase = " ".join(evidence_words)
        if phrase in corpus_lower:
            contiguous_match = True
            matched_phrase = phrase

    # 2. Content word overlap (>= 60%)
    stop_words = {"the", "a", "an", "is", "and", "or", "to", "in", "it", "of", "for", "on", "we", "this"}
    test_words = [
        w for w in re.findall(r"\b[a-zA-Z0-9_-]+\b", f"{why_text} {evidence}".lower())
        if w not in stop_words and len(w) > 2
    ]

    if test_words:
        matched_words = [w for w in test_words if w in corpus_lower]
        word_overlap = len(matched_words) / len(test_words)
    else:
        word_overlap = 1.0

    is_verified = (word_overlap >= 0.60) and contiguous_match

    return {
        "verified": is_verified,
        "word_overlap": round(word_overlap, 4),
        "contiguous_match": contiguous_match,
        "matched_phrase": matched_phrase,
        "reason": (
            "Traceability verified: >=60% word overlap and contiguous verbatim quote found in source corpus."
            if is_verified
            else "Traceability failed: verbatim quote not found contiguously in source discussion."
        ),
    }

