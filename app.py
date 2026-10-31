"""AetherGit Interactive Dashboard & Serverless API Backend.

Problem 06: Open Source Decision Intelligence and Knowledge Recovery
Hacktoberfest 2026 - Hack Day Sonipat
Model: Gemma 4 (gemma-4-26b-a4b-it via Google Gemini API)
"""

import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, request

HTML_PATH = Path(__file__).resolve().parent / "index.html"

# Initialize Flask Application Backend
app = Flask(__name__)
application = app
handler = app

# In-memory IP rate limiter: max 10 requests per minute per IP
_ip_request_timestamps = defaultdict(list)


def is_rate_limited(ip: str, limit: int = 10, window_seconds: int = 60) -> bool:
    """Best-effort in-memory sliding window rate limiter."""
    now = time.time()
    timestamps = _ip_request_timestamps[ip]
    _ip_request_timestamps[ip] = [t for t in timestamps if now - t < window_seconds]
    if len(_ip_request_timestamps[ip]) >= limit:
        return True
    _ip_request_timestamps[ip].append(now)
    return False


def normalize_text(text: str) -> str:
    """Normalizes text by lowercasing, stripping punctuation, and collapsing whitespace."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def server_quote_check(quote: str, discussion: str) -> dict:
    """Performs verifiable quote check on the server against exact discussion text."""
    norm_quote = normalize_text(quote)
    norm_disc = normalize_text(discussion)

    quote_words = norm_quote.split()
    disc_words = norm_disc.split()
    disc_word_set = set(disc_words)

    has_min_words = len(quote_words) >= 4
    contiguous = has_min_words and (norm_quote in norm_disc)

    if quote_words:
        matched = [w for w in quote_words if w in disc_word_set]
        overlap = round(len(matched) / len(quote_words), 4)
    else:
        overlap = 0.0

    return {
        "contiguous": contiguous,
        "word_overlap": overlap,
    }


def extract_first_json_block(text: str) -> dict:
    """Extracts the first balanced {...} JSON block from response text."""
    start_idx = text.find("{")
    if start_idx == -1:
        raise ValueError("No JSON object found")

    brace_count = 0
    in_string = False
    escape = False
    end_idx = -1

    for i in range(start_idx, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if not in_string:
            if c == "{":
                brace_count += 1
            elif c == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

    if end_idx != -1:
        return json.loads(text[start_idx:end_idx])

    match = re.search(r"\{[\s\S]*?\}", text)
    if match:
        return json.loads(match.group(0))

    raise ValueError("Invalid JSON block")


def call_gemma_api(discussion_text: str):
    """Executes server-side Gemma 4 inference with 1 retry on malformed JSON."""
    provider = os.environ.get("AI_PROVIDER", "gemini").lower()
    model = os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it")

    prompt = (
        "You read a software team discussion and find the final decision.\n"
        "Use ONLY information written in the discussion. Never guess.\n"
        "If something is missing, write \"unknown\".\n"
        "Reply with JSON only, no other text, exactly:\n"
        "{\"decided\":\"...\",\"rejected\":\"...\",\"reason\":\"...\",\"quote\":\"words copied exactly from the discussion that show the reason\",\"file\":\"...\"}\n\n"
        f"Discussion:\n{discussion_text}"
    )

    if provider == "ollama":
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        payload = {
            "model": "gemma4:e4b",
            "prompt": prompt,
            "stream": False,
        }
        for attempt in range(2):
            try:
                resp = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=45)
                if resp.status_code == 429:
                    return None, ("Rate limit reached. Try again in a minute.", 429)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                raw_answer = data.get("response", "")
                parsed = extract_first_json_block(raw_answer)
                record = {
                    "decided": str(parsed.get("decided", "unknown")),
                    "rejected": str(parsed.get("rejected", "unknown")),
                    "reason": str(parsed.get("reason", "unknown")),
                    "quote": str(parsed.get("quote", "unknown")),
                    "file": str(parsed.get("file", "unknown")),
                }
                return record, None
            except Exception:
                if attempt == 1:
                    return None, ("The AI service did not answer.", 502)
        return None, ("The AI service did not answer.", 502)

    # Default: Google Gemini API Provider
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None, ("Live AI is not configured on the server.", 503)

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
        },
    }

    for attempt in range(2):
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=45)
            if resp.status_code == 429:
                return None, ("Rate limit reached. Try again in a minute.", 429)
            if resp.status_code != 200:
                continue
            res_json = resp.json()
            candidates = res_json.get("candidates", [])
            if not candidates:
                continue
            parts = candidates[0].get("content", {}).get("parts", [])
            # Read answer by joining text, skipping any part marked "thought": true
            text_parts = [p.get("text", "") for p in parts if not p.get("thought")]
            full_text = "".join(text_parts)
            parsed = extract_first_json_block(full_text)
            record = {
                "decided": str(parsed.get("decided", "unknown")),
                "rejected": str(parsed.get("rejected", "unknown")),
                "reason": str(parsed.get("reason", "unknown")),
                "quote": str(parsed.get("quote", "unknown")),
                "file": str(parsed.get("file", "unknown")),
            }
            return record, None
        except Exception:
            if attempt == 1:
                return None, ("The AI service did not answer.", 502)
    return None, ("The AI service did not answer.", 502)


def check_pr_regression(pr_title: str, line_number: int, rejected_text: str, reason_text: str = ""):
    """Evaluates PR regression against historical anchor line range and whole-word matching."""
    if not rejected_text or rejected_text.strip().lower() == "unknown":
        return {
            "status": "NO_DECISION",
            "message": "No decision saved yet. Extract one first.",
            "is_regression": False,
            "touches_anchor": 40 <= line_number <= 120,
        }

    touches_anchor = 40 <= line_number <= 120
    if not touches_anchor:
        return {
            "status": "SAFE",
            "message": "Safe Line Range - No Architectural Regression",
            "is_regression": False,
            "touches_anchor": False,
        }

    # Find whole words longer than 3 letters
    rejected_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", rejected_text.lower()))
    title_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", pr_title.lower()))

    shared_words = rejected_words.intersection(title_words)
    if shared_words:
        msg = f"Decision alert: Proposed changes repeat rejected alternative: '{rejected_text}'"
        if reason_text and reason_text.lower() != "unknown":
            msg += f" (Reason: {reason_text})"
        return {
            "status": "BLOCK",
            "message": msg,
            "is_regression": True,
            "touches_anchor": True,
            "shared_words": list(shared_words),
        }

    return {
        "status": "SAFE",
        "message": "Safe Line Range - No Architectural Regression",
        "is_regression": False,
        "touches_anchor": True,
    }


@app.after_request
def add_cors_headers(response):
    """Permit cross-origin requests from any frontend."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


# =========================================================================
# WEB FRONTEND ROUTES
# =========================================================================
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path=""):
    """Serves the standalone dark-mode Tailwind web dashboard."""
    if path.startswith("api/"):
        return jsonify({"error": "Endpoint not found"}), 404
    if HTML_PATH.exists():
        return Response(HTML_PATH.read_text(encoding="utf-8"), mimetype="text/html")
    return Response("<h1>AetherGit Decision Intelligence Online</h1>", mimetype="text/html")


# =========================================================================
# REST API ENDPOINTS
# =========================================================================
@app.route("/api/status", methods=["GET"])
def api_status():
    """Returns engine availability status via Gemini API or local Ollama."""
    provider = os.environ.get("AI_PROVIDER", "gemini").lower()
    model = os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it")

    if provider == "ollama":
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        try:
            r = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if r.status_code == 200:
                return jsonify({"live": True, "model": "gemma4:e4b"})
            return jsonify({"live": False, "reason": "model unreachable"})
        except Exception:
            return jsonify({"live": False, "reason": "model unreachable"})

    # Gemini provider
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return jsonify({"live": False, "reason": "not configured"})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
    headers = {"x-goog-api-key": api_key}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return jsonify({"live": True, "model": model})
        return jsonify({"live": False, "reason": "model unreachable"})
    except Exception:
        return jsonify({"live": False, "reason": "model unreachable"})


@app.route("/api/extract", methods=["POST", "OPTIONS"])
def api_extract():
    """Extracts formal decision record using live Gemma 4 model."""
    if request.method == "OPTIONS":
        return jsonify({"ok": True}), 200

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.remote_addr or "unknown"
    if is_rate_limited(ip, limit=10, window_seconds=60):
        return jsonify({"error": "Rate limit reached. Try again in a minute."}), 429

    data = request.get_json(silent=True) or {}
    discussion_text = data.get("discussion_text") or data.get("issue_text") or data.get("corpus") or ""
    if not isinstance(discussion_text, str) or not discussion_text.strip():
        return jsonify({"error": "Paste a discussion first."}), 400
    if len(discussion_text) > 12000:
        return jsonify({"error": "Discussion too long (max 12,000 characters)."}), 413

    record, err = call_gemma_api(discussion_text)
    if err:
        msg, code = err
        return jsonify({"error": msg}), code

    model = os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it")
    if os.environ.get("AI_PROVIDER", "gemini").lower() == "ollama":
        model = "gemma4:e4b"

    quote_check = server_quote_check(record.get("quote", ""), discussion_text)
    return jsonify({
        "source": "live",
        "model": model,
        "record": record,
        "quote_check": quote_check,
    }), 200


@app.route("/api/evaluate-pep", methods=["POST", "OPTIONS"])
def api_evaluate_pep():
    """Alias for POST /api/extract."""
    return api_extract()


@app.route("/api/check-pr", methods=["POST", "OPTIONS"])
def api_check_pr():
    """Evaluates pull request regression against extracted decision memory."""
    if request.method == "OPTIONS":
        return jsonify({"ok": True}), 200

    data = request.get_json(silent=True) or {}
    pr_title = str(data.get("pr_title") or "")
    slider_val = int(data.get("slider_val", 45))
    rejected_text = str(data.get("rejected", ""))
    reason_text = str(data.get("reason", ""))

    res = check_pr_regression(pr_title, slider_val, rejected_text, reason_text)
    return jsonify(res), 200


# =========================================================================
# STREAMLIT COMPATIBILITY RUNNER
# =========================================================================
try:
    import streamlit as st
except ImportError:
    st = None


def main():
    """Interactive Streamlit application runner when launched via streamlit run app.py."""
    if st is None:
        return

    st.set_page_config(
        page_title="AetherGit · Open Source Decision Intelligence",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("<div style='font-size: 2.2rem; font-weight: 800; color: #f8fafc;'>⚡ AetherGit: Decision Intelligence</div>", unsafe_allow_html=True)
    st.info("Interactive Streamlit dashboard active. Launch http://localhost:8000 for the full web app.")


run_streamlit_dashboard = main

if __name__ == "__main__" or (st is not None and hasattr(st, "runtime") and st.runtime.exists()):
    if not os.environ.get("VERCEL"):
        main()
