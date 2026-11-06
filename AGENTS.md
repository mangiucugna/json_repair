# Repository guidance

## Workflow
- Use `.venv` via `uv run`; install development dependencies with `uv sync --group dev` and update `uv.lock` when dependencies change.
- For code changes, run `uv run pytest` and `pre-commit run --all-files`. Skip pre-commit for Markdown-only changes unless requested. If hooks update files, retain and restage those updates in commit flows.
- Keep Ruff `ANN401` disabled; use mypy and ty. Keep CI's `ruff format` aligned with the Python-only pre-commit hook.
- When consolidating tests, preserve coverage across stdlib fast paths, forced repair, schema modes, and file buffering. CI's Python-version matrix runs only `tests/test_json_repair.py`; moving its cases elsewhere changes matrix coverage.
- The docs API tests require Flask and Flask-CORS, and the overload-inference tests require mypy. Full-suite CI needs the `test`, `schema`, and `typecheck` groups; missing test dependencies should fail collection rather than silently skip these modules.
- Keep Python 3.10 support best effort without expanding CI or adding compatibility work for it. Retain performance tests and dependency-update hooks in normal pre-commit runs.
- Keep `README.zh.md` aligned with `README.md` when behavior or contributor guidance changes. `README.md` is the PyPI description; avoid relative links. Store demo share state in the URL hash.
- For releases, align `pyproject.toml` and `CITATION.cff`, use semantic versioning, and run `uvx twine check dist/*` after building. Preserve sdist test exclusion and the `json_repair` package-data key for `py.typed`.

## Parser and schema contracts
- Preserve standard-library behavior for valid JSON, including in strict mode; `skip_json_loads=True` explicitly opts out. `load(fd)` starts at the descriptor's current position.
- Keep repair heuristics conservative in strict mode and log automatic corrections. Preserve malformed-input behavior and context lifetimes when refactoring; use existing regression tests to cover specific cases.
- Treat comments as whitespace at structural value boundaries; consuming trivia must not continue top-level parsing. Keep one shared output-finalization path in `repair_json`.
- Apply schema repair and validation to valid and invalid inputs, with dispatch centralized in `JSONParser.parse_json(schema, path)`. Preserve accepted Pydantic field names and explicit-alias precedence.
- Share tuple schema mapping between parsing and repair: `prefixItems` is positional and `items` constrains the tail; preserve legacy `items`/`additionalItems` behavior. Retain root resolver scope for detached schema branches and schema identity for validator caching.
- Normalize only schema-bearing locations; preserve literal values in keywords such as `const`, `enum`, `default`, and `examples`. Validate schema definitions before repair and keep repeated validation efficient.
- Treat schemas as untrusted: limit recursion or raise controlled `ValueError`; never execute user-supplied `patternProperties` regexes. Normalize top-level `RecursionError` to `ValueError`.
- Schema repair modes are `standard` and opt-in `salvage`. Salvage requires strong structural evidence, never infers semantic property renames, and may select the first schema-valid sequential fragment but not an item from an actual top-level array.
- Guard against repeated string lookahead scans on long malformed inputs; test meaningful performance regressions when changing that code.
