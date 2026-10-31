"""EXPERIMENTAL: Cloud API Fallback (PROPOSED).

WARNING: This module attempts to call cloud models (Gemini / OpenAI).
Per Hackathon 2026 rules (Slide 12 & Page 17), closed cloud APIs are strictly PROHIBITED
and will disqualify the team or score 0 on Open-Source AI Use.

This PR is submitted for architectural discussion and must be REJECTED in favor of local gemma4:e4b.
"""

import os


def call_cloud_gemini_api(prompt: str) -> str:
    """Attempts to call cloud Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable required for cloud execution.")
    return "Cloud response"
