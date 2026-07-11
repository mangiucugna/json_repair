# Repo Notes for Codex

## Environment
- Use the uv-managed environment at `.venv`; install dev dependencies with `uv sync --group dev`.
- Prefer `uv run ...` for Python tooling.
- Dependency groups live in `pyproject.toml`; update `uv.lock` when dependencies change.

## Validation
- Run the full test suite with `uv run pytest`.
- Run the full hook stack with `pre-commit run --all-files`.
- `tests/test_performance.py` is timing-sensitive and can fail on slower machines.
- `tests/test_type_inference.py` exercises import resolution from a temp directory; keep it independent of editable installs.
- The hook stack may rewrite `uv.lock` or `.pre-commit-config.yaml`; if hook-managed files change during commit flows, restage the resulting updates instead of repeatedly restoring them.

## Release And Packaging
- Project version lives in `pyproject.toml` under `[project].version`; use semantic versioning, with patch bumps for bug fixes.
- Keep `CITATION.cff` aligned with the released version metadata in `pyproject.toml`.
- Keep `MANIFEST.in` pruning `tests` so test modules are not shipped in the sdist.
- In `[tool.setuptools.package-data]`, use the real package key `json_repair` so `py.typed` remains included.
- Run `uvx twine check dist/*` after building and before publishing.

## Docs
- Keep `README.zh.md` aligned with `README.md` when behavior or contributor guidance changes.
- `README.md` is the PyPI long description via `pyproject.toml`; avoid relative file or image links there.
- For local docs demo validation, follow `.agents/skills/docs-demo-local-test/SKILL.md`.
- Keep docs demo share state in the URL hash, not query params.

## Code Areas
- API and CLI entry points: `src/json_repair/json_repair.py`, `src/json_repair/__init__.py`, `src/json_repair/__main__.py`.
- Parser orchestration: `src/json_repair/json_parser.py`.
- Repair primitives: `src/json_repair/parse_*.py`, `src/json_repair/parse_string_helpers/*`.
- Schema logic: `src/json_repair/schema_repair.py`.
- Demo API/UI: `docs/app.py`, `docs/index.js`, `docs/index*.html`, `docs/styles.css`.

## Durable Implementation Notes
- Keep valid-JSON fast paths on the standard library path; `strict=True` must not second-guess inputs that `json.loads` already accepts.
- Treat `skip_json_loads=True` as an explicit opt-out for inputs already known to be invalid; do not assume behavior must match the stdlib-preserving path for valid JSON.
- `load(fd)` should behave like `json.load(fd)` and repair from the descriptor's current position.
- When adding repair heuristics, keep `strict=True` conservative and emit parser logs for automatic corrections.
- When a schema is provided, apply schema repair and validation for both valid and invalid JSON inputs.
- Keep schema-guided dispatch centralized in `JSONParser.parse_json(schema, path)`.
- `patternProperties` matching is intentionally limited to a safe subset; do not execute user-supplied regexes.
- Preserve schema dict identity in `SchemaRepairer.resolve_schema` whenever possible so validator caching remains effective.
- `schema_repair_mode` supports only `standard` and opt-in `salvage`; `salvage` should remain best-effort structural recovery, not broad silent coercion.
- Treat user-supplied schemas as an attacker-controlled input surface: deep nesting in schema normalization, validation, and repair paths needs an explicit depth limit or controlled `ValueError`, not an uncaught `RecursionError`.

## Refactor Pitfalls
- In `repair_json`, keep a single shared output-finalization path for logging, `return_objects`, empty-string handling, and `json.dumps`.
- Parser refactors are sensitive to context lifetimes and heuristic branch ordering; preserve malformed-input behavior when restructuring `parse_string` or `parse_object`.
- Performance regressions often hide in repeated `parse_string` lookahead scans on long malformed object values; include cases with many commas or `}` characters before a far quote when changing comma/right-brace heuristics.
- Normalize top-level `RecursionError` into `ValueError`.
