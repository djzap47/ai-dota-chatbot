# Contributing

Thanks for helping improve AI Dota 2 Tracker. Useful contributions include reproducible bug fixes, clearer documentation, UI improvements, and well-sourced corrections to game data.

## Local development

1. Fork and clone the repository, then create a branch for your change.
2. Follow the [README setup](README.md#quick-start) to create a virtual environment and install `requirements.txt`.
3. Use your own development database and API keys if you need to exercise live services. Offline checks do not require `.env` or credentials.
4. Run the relevant checks from the repository root:

```bash
python -m unittest discover -s tests -v
python -m compileall -q api app scripts bot.py
git diff --check
```

Tests use Python's standard-library `unittest`, FastAPI's test client, local datasets, and mocked external calls. CI runs on Python 3.12 and 3.14. It does not call Gemini, STRATZ, or a live database.

## Making changes

- Follow the surrounding code style and `.editorconfig`.
- Add focused regression tests for behavior changes. Documentation-only updates do not need artificial tests.
- Update the README or relevant guide when changing setup, configuration, endpoints, or script behavior.
- For UI changes, include a screenshot and check both desktop and mobile widths.
- Keep credentials and local runtime files out of commits. Share sanitized logs only.

For build or mechanics corrections, include the hero, role, relevant patch, and a source supporting the change. Distinguish curated advice from API-derived data. Read [data maintenance](docs/data-maintenance.md) before regenerating datasets: some scripts overwrite files or replace database contents.

## Pull requests and issues

Describe the problem, the resulting behavior, and how you checked it. Keep unrelated refactors separate so the change is easy to review. Use the issue templates for reproducible bugs and feature proposals.

When reporting an incorrect answer, include the exact question and response, whether it happened in the demo or locally, and any relevant data-refresh details. Omit credentials and personal data.
