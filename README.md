# ⚡ AetherGit: Open Source Decision Intelligence & Knowledge Recovery

> **Hacktoberfest 2026 · Hack Day Sonipat (NST Rishihood University)**  
> **Problem 06: Recover the Decisions Nobody Wrote Down**  
> *Powered strictly by local open-weight Google Gemma (`gemma4:e4b` via Ollama)*

[![CI Pipeline](https://img.shields.io/badge/CI-Passing%20(Python%203.11)-success?logo=github-actions)](.github/workflows/ci.yml)
[![AI Model](https://img.shields.io/badge/AI%20Model-gemma4%3Ae4b%20(Local%20Ollama)-blueviolet?logo=ollama)](#-open-weight-ai-model-execution)
[![Deployment](https://img.shields.io/badge/Deployed-Vercel-black?logo=vercel)](https://aethergit.vercel.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Strictly Open Source](https://img.shields.io/badge/Cloud%20APIs-Zero%20(100%25%20Offline)-brightgreen)](#-zero-cloud-api-policy)

---

## 1. The Real-World Maintainer Problem

Open-source projects accumulate years of heated architectural debates across 140+ reply GitHub issues, reverted pull requests, and forum threads (such as `discuss.python.org`).

Often, a team tests an idea—for example, rewriting a C parser in Rust—discovers it is **2× slower on big files**, and reverts the Pull Request (`#1901`) without writing a formal Architectural Decision Record (ADR). Two years later, a well-meaning new contributor wastes weeks writing the exact same Rust rewrite because the technical reason it failed was buried in closed discussions.

### Why Standard `git blame` Fails:
```text
┌────────────────────────────────────────────────────────────────────────┐
│ Standard git blame (0% Architectural Context)                         │
├────────────────────────────────────────────────────────────────────────┤
│ commit 1902: Revert "PR #1901: rewrite in rust"                        │
│ -> Tells you WHAT happened, but 0% context on WHY it was reverted.     │
└────────────────────────────────────────────────────────────────────────┘
                                 vs
┌────────────────────────────────────────────────────────────────────────┐
│ AetherGit Architectural Memory Firewall (100% Recovered Context)       │
├────────────────────────────────────────────────────────────────────────┤
│ Anchor: parser/core.c (lines 40–120), function parse_token_stream()   │
│ Decided:  Keep the C parser                                            │
│ Rejected: Rewrite in Rust (PR #1901)                                   │
│ Why:      2x slower on big files compared to the C parser              │
│ Active Bot Guard: "Tried in 2022 and reverted: 2x slower. See #1901." │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The 3-Stage Pipeline Architecture

```mermaid
flowchart TD
    subgraph S1["Stage 1: Signal-Weighted Thread Mining"]
        A["Raw GitHub Issues (140+ replies)"] --> D["Score & Rank Discussion"]
        B["Reverted PRs & Git Diffs"] --> D
        C["discuss.python.org Threads"] --> D
        D -->|"Position Boost + Rejection Keywords"| E["Top-K Signal Context Chunks"]
    end

    subgraph S2["Stage 2: Verifiable MADR Extraction"]
        E --> F["Local Gemma 4 Engine (gemma4:e4b via Ollama)"]
        F --> G["MADR JSON Decision Record"]
        G --> H["Contiguous Substring Quote Validator (>=4 words)"]
        H -->|"Verified Evidence"| I["Deterministic Code Anchor"]
    end

    subgraph S3["Stage 3: Rename-Resilient Code Link & PR Firewall"]
        I --> J["Hybrid AST Relinker (50% Sig + 50% SequenceMatcher)"]
        J --> K["Unified Contributor Identity Graph"]
        K --> L["Decisions Bot Firewall"]
        L -->|"New PR touches lines 40-120 with matching title"| M["🚨 Block Mistake: Tried in 2022 and reverted: 2x slower. See #1901."]
    end
```

---

## 3. How to Run Live (Local Gemma 4 via Ollama)

The hosted live site at [https://aethergit.vercel.app/](https://aethergit.vercel.app/) transparently displays verified, cached demo outputs (`cached-demo (not live)`) by default. To make the hosted site execute **genuinely live AI inference** against your local machine's Gemma 4:

1. **Quit the Ollama Desktop application** if it is running in the system menu bar.
2. **Launch Ollama from your terminal with CORS origin permissions** for the Vercel site:
   ```bash
   OLLAMA_ORIGINS="https://aethergit.vercel.app" ollama serve
   ```
3. In a second terminal window, verify that `gemma4:e4b` is installed and running:
   ```bash
   ollama run gemma4:e4b
   ```
4. Open [https://aethergit.vercel.app/](https://aethergit.vercel.app/) in your browser.
   - The status pill in the top header detects the local model and turns green: `Model: gemma4:e4b (Local Ollama)` with badge `live-gemma4`.
   - Any discussion extracted in the browser executes directly against `http://localhost:11434/api/generate` with live MADR parsing and quote verification.

> **Transparent Labeling Guarantee:** Unless Gemma 4 runs locally with `OLLAMA_ORIGINS` enabled as shown above, the hosted site clearly labels responses as `cached-demo (not live)` in amber. If local Ollama is offline and custom text is entered, the site refuses to show canned text and displays: `"Gemma is not running on this computer. Showing nothing."`

---

## 4. Open-Weight AI Model Execution

- **AI Model:** `gemma4:e4b`
- **Execution Environment:** Local Ollama (`http://localhost:11434/api/generate` and `/api/tags`)
- **Zero Cloud API Policy:** Zero OpenAI, Anthropic, or Gemini Cloud API keys. Complies 100% with Problem 06 and Hacktoberfest open-weight rules.
- **Deterministic CI Gate:** When running in GitHub Actions (`CI=true`) or when local Ollama is offline, `src/engine.py` activates an instantaneous verified deterministic gate so test suites pass 100% green in under 1 second.

---

## 5. How We Solve All 5 Official Judging Rubric Challenges (Page 12)

| # | Official Judge Question (Page 12) | Technical Solution in `src/engine.py` | Implementation Details |
|---|---|---|---|
| **1** | **Extracting from very long discussions?** | `score_and_rank_discussion(messages, top_k=8)` | Prioritizes rejection/benchmark terms (`rejected`, `revert`, `slower`, `benchmark`, `veto`), boosts maintainer authority, adds position weights to the final 3 closing consensus replies, and never drops context. |
| **2** | **Distinguishing accepted vs. rejected ideas?** | Contrastive MADR Schema + Git Revert State in `extract_decision_record_with_gemma` | Combines Git merge/revert metadata with Gemma's structured JSON schema to separate `decided` from `rejected`, extracting individual technical failure causes. |
| **3** | **What if files are renamed AND edited?** | `relink_symbol_across_repo(sig, old_body, candidates)` | Combines **50% function signature matching** (`parse_token_stream`) + **50% normalized `difflib.SequenceMatcher` body similarity** so that even if `parser/core.c` moves to `src/lexer/fast_core.c` and lines are edited, the architectural link survives with >=85% confidence. |
| **4** | **Recognizing contributors across platforms?** | `resolve_contributor_identities(participants)` | Cross-Platform Identity Graph unifying GitHub handles, Git commit emails, and forum display names into a canonical profile. |
| **5** | **Verifying every decision against its source?** | `verify_source_traceability(record, raw_corpus)` | Contiguous Substring Quote Validator requiring **>=60% content-word overlap** AND an exact **contiguous multi-word match (>=4 consecutive words)** from `verbatim_evidence` inside the source corpus, rejecting hallucinated AI summaries. |

---

## 6. Repository Structure

```text
aethergit/
├── .github/
│   ├── pull_request_template.md    # Mandatory 4-header PR template
│   └── workflows/
│       └── ci.yml                  # Automated Python 3.11 build, test, and CLI workflow
├── examples/                       # Section 4.5 artifacts
│   ├── sample_input.json           # Slide 6 C Parser & Page 12 Python PEP Scenarios
│   └── actual_output.json          # Real verified output generated by AetherGit
├── src/
│   ├── __init__.py
│   ├── engine.py                   # Core Decision Intelligence & Ollama Gemma engine
│   └── cli.py                      # Command-line interface and git blame comparison tool
├── tests/
│   ├── __init__.py
│   ├── test_smoke.py               # CI environment bootstrap smoke test
│   ├── test_engine.py              # 16 unit tests covering all 5 rubric challenges
│   └── test_api_endpoints.py       # Unit tests for API endpoints
├── app.py                          # Flask REST API backend & static file server
├── index.html                      # Standalone dark-mode Tailwind CSS web application
├── HACKATHON.md                    # Official Team & Problem registration
├── LICENSE                         # MIT License (Team Aadi Yogi)
├── requirements.txt                # Production dependencies (flask, streamlit, requests, pytest)
└── README.md                       # Comprehensive architecture guide
```

---

## 7. Quickstart & Installation

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/sudhanshukhetan/aethergit.git
cd aethergit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Optional: Run Local Gemma via Ollama
```bash
# Pull the open-weight Gemma model
ollama pull gemma4:e4b
```

### 3. Run Automated Unit Tests
```bash
CI=true PYTHONPATH=. python3 -m unittest discover tests -v
```

### 4. Run AetherGit CLI Scanner & Example Validator
```bash
# Validate Section 4.5 mandatory examples
python3 -m src.cli --verify-examples

# Scan repository commit history for reverts
python3 -m src.cli --scan-git-log
```

### 5. Launch Web Application
```bash
# Run Flask Server
python3 app.py
```
Open `http://localhost:5000` or launch `index.html` directly in your browser.

---

## 8. Team Details

- **Team Name:** Aadi Yogi
- **Members:**
  - Sudhanshu Khetan (Team Lead)
  - Krishna Gupta
  - Hemant Kumar
  - Mauli Arora
- **Event:** Hacktoberfest 2026 – Hack Day Sonipat (NST Rishihood University)
- **Problem Statement:** Problem 06: Open Source Decision Intelligence and Knowledge Recovery
- **AI Models Used:** `gemma4:e4b (via Ollama local execution)`
