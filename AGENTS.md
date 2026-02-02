# Repo Notes for Codex

## Environment
- Use the uv-managed environment at `.venv`; install dev dependencies with `uv sync --group dev`.
- Prefer `uv run ...` for Python tooling (use `uv run python -m ...` if `python` is not on PATH).
- Dependency groups live in `pyproject.toml`; update `uv.lock` when dependencies change.
- You may see `/Users/s.baccianella/.rvm/scripts/rvm:29: operation not permitted: ps` in shell output; safe to ignore.

## Tests
- Run the full test suite with:
  - `uv run pytest`
- Performance benchmarks in `tests/test_performance.py` are timing-sensitive and may fail on slower machines.

## Pre-commit
- Run all hooks without activating a venv:
  - `pre-commit run --all-files`
- The `pre-commit autoupdate` hook can modify `.pre-commit-config.yaml` (e.g., bumping hook revs). Re-run pre-commit after updates.
- Hooks like `ruff-pre-commit` and `semgrep` require network access to fetch resources.
- Always run pre-commit fully; do not leave it partially completed.

## Releases
- Project version lives in `pyproject.toml` under `[project].version`.
- Use semantic versioning; patch bumps are appropriate for bug fixes.

## Docs
- Keep `README.zh.md` aligned with `README.md` when updating contributor guidance or usage notes.

## Commits
- Prefer descriptive commit messages with a short summary line and a brief bullet list of key changes.
- When closing issues, start the summary with `Fix #<issue-number>:` so GitHub auto-closes.

## Code Areas
- Public API and CLI entry points:
  - `src/json_repair/json_repair.py` (repair_json plus loads/load/from_file wrappers; strict/logging/stream_stable options)
  - `src/json_repair/__init__.py` (exports wrapper functions)
  - `src/json_repair/__main__.py` (CLI; files/stdin, in-place output, formatting flags like `--indent`/`--ensure_ascii`)
- Parser entrypoint and orchestration:
  - `src/json_repair/json_parser.py` (JSONParser; parse/parse_json dispatch, stream handling)
- Core parsers:
  - `src/json_repair/parse_object.py`, `src/json_repair/parse_array.py`, `src/json_repair/parse_string.py`, `src/json_repair/parse_number.py`, `src/json_repair/parse_comment.py`
- String helpers:
  - `src/json_repair/parse_string_helpers/parse_boolean_or_null.py`, `src/json_repair/parse_string_helpers/parse_json_llm_block.py`
- Utilities:
  - `src/json_repair/utils/json_context.py`, `src/json_repair/utils/string_file_wrapper.py`, `src/json_repair/utils/constants.py`, `src/json_repair/utils/object_comparer.py`
- Web demo and API:
  - `docs/app.py` (Flask API `/api/repair-json`, uses CORS, returns repaired JSON + log)
  - `docs/index.js` (client UI; debounced `processInput`, AbortController, URL param handling)
  - `docs/index.html`, `docs/index.zh.html` (localized pages + SEO metadata)
  - `docs/styles.css` (layout and responsive styles)
- Tests:
  - Parser tests: `tests/test_parse_*.py`
  - API/CLI tests: `tests/test_json_repair.py`, `tests/test_repair_json_cli.py`, `tests/test_repair_json_from_file.py`
  - Strict mode: `tests/test_strict_mode.py`
  - Performance/benchmarks: `tests/test_performance.py`, `.benchmarks/`

## Contributing
- PRs follow `.github/PULL_REQUEST_TEMPLATE.md` (review `CONTRIBUTING.md`, add tests, and run pre-commit + unit tests).

## Style preferences
- Avoid extracting small, non-shared helper functions if the original block is short; keep logic inline for readability.
- For JSONParser logging, prefer the inline no-op lambda over a module-level `_noop` helper.
- When adding new repair heuristics, emit a `self.log` entry and skip the repair in `strict=True` unless explicitly intended.
