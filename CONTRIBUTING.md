# Contributing to AetherGit

Thank you for your interest in contributing to **AetherGit**! We welcome bug fixes, documentation improvements, new architectural benchmark scenarios, and code enhancements.

AetherGit is an open-source Architectural Memory Firewall designed for Hacktoberfest 2026 (Problem 06: Open Source Decision Intelligence and Knowledge Recovery).

---

## 1. Quickstart Development Setup

### Prerequisites
- **Python 3.10 or higher**
- **Git**
- *(Optional for full AI mode)* **[Ollama](https://ollama.ai)** with `gemma4:e4b` model pulled:
  ```bash
  ollama pull gemma4:e4b
  ollama serve
  ```

### Installation
1. Fork and clone the repository:
   ```bash
   git clone https://github.com/sudhanshukhetan/aethergit.git
   cd aethergit
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install project dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 2. Running the Test Suite

All contributions must pass the automated test suite before merging:
```bash
# Run unit tests
PYTHONPATH=. pytest tests/ -v

# Or using Python's standard library test runner:
PYTHONPATH=. python3 -m unittest discover tests -v
```

Validate the mandatory Section 4.5 example benchmark dataset:
```bash
python3 -m src.cli --Verify-examples
```

---

## 3. Running the Interactive Dashboard

Launch the Streamlit interactive dashboard locally:
```bash
streamlit run app.py
```
Or open `index.html` directly in any modern browser for the standalone dark-mode Tailwind interface.

---

## 4. Pull Request Guidelines

1. **Create a descriptive feature branch**:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. **Follow PEP 8 naming conventions** for Python code.
3. **Deterministic Fallback**: If you add any functionality touching local AI models, ensure it gracefully falls back when `CI=true` or when Ollama is offline.
4. **No Closed Cloud APIs**: Hackathon rules strictly prohibit closed cloud APIs (OpenAI / Claude / Cloud Gemini). All AI inference must run via local `gemma4:e4b`.
5. **Open a Pull Request**:
   - Provide a clear summary in `.github/pull_request_template.md`.
   - Ensure all CI tests pass.
