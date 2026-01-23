# Repo Notes for Codex

## Environment
- Use the existing venv at `.venv`; activate before running any Python tooling.
- If `python` is not on PATH, use the venv's interpreter: `. .venv/bin/activate` then `python -m ...`.
- `requirements.txt` includes `pytest`, `pre-commit`, etc. Install into `.venv` if needed.
- You may see `/Users/s.baccianella/.rvm/scripts/rvm:29: operation not permitted: ps` in shell output; safe to ignore.

## Tests
- Run the full test suite with:
  - `. .venv/bin/activate && python -m pytest`

## Pre-commit
- Run all hooks with:
  - `. .venv/bin/activate && pre-commit run --all-files`
- The `pre-commit autoupdate` hook can modify `.pre-commit-config.yaml` (e.g., bumping hook revs). Re-run pre-commit after updates.
- Hooks like `ruff-pre-commit` and `semgrep` require network access to fetch resources.

## Releases
- Project version lives in `pyproject.toml` under `[project].version`.
- Use semantic versioning; patch bumps are appropriate for bug fixes.

## Commits
- Prefer descriptive commit messages with a short summary line and a brief bullet list of key changes.
- When closing issues, start the summary with `Fix #<issue-number>:` so GitHub auto-closes.

## Code Areas
- Public API and CLI entry points:
  - `src/json_repair/json_repair.py` (repair_json/load helpers)
  - `src/json_repair/__main__.py` (CLI)
- Parser entrypoint and orchestration:
  - `src/json_repair/json_parser.py` (dispatches to parse_* modules)
- Core parsers:
  - `src/json_repair/parse_object.py`, `src/json_repair/parse_array.py`, `src/json_repair/parse_string.py`, `src/json_repair/parse_number.py`, `src/json_repair/parse_comment.py`
- String helpers:
  - `src/json_repair/parse_string_helpers/parse_boolean_or_null.py`, `src/json_repair/parse_string_helpers/parse_json_llm_block.py`
- Utilities:
  - `src/json_repair/utils/json_context.py`, `src/json_repair/utils/string_file_wrapper.py`, `src/json_repair/utils/constants.py`, `src/json_repair/utils/object_comparer.py`
- Tests:
  - Parser tests: `tests/test_parse_*.py`
  - API/CLI tests: `tests/test_json_repair.py`, `tests/test_repair_json_cli.py`, `tests/test_repair_json_from_file.py`
  - Strict mode: `tests/test_strict_mode.py`
  - Performance/benchmarks: `tests/test_performance.py`, `.benchmarks/`
