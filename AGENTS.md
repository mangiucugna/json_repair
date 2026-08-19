# Repo Notes for Codex

## Environment
- Use the uv-managed environment at `.venv`; install dev dependencies with `uv sync --group dev`.
- Prefer `uv run ...` for Python tooling.
- Dependency groups live in `pyproject.toml`; update `uv.lock` when dependencies change.

## Validation
- Run the full test suite with `uv run pytest`.
- Run the full hook stack with `pre-commit run --all-files`.
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
- Keep docs demo share state in the URL hash, not query params.

## Durable Implementation Notes
- Keep valid-JSON fast paths on the standard library path; `strict=True` must not second-guess inputs that `json.loads` already accepts.
- Treat `skip_json_loads=True` as an explicit opt-out for inputs already known to be invalid; do not assume behavior must match the stdlib-preserving path for valid JSON.
- `load(fd)` should behave like `json.load(fd)` and repair from the descriptor's current position.
- When adding repair heuristics, keep `strict=True` conservative and emit parser logs for automatic corrections.
- When a schema is provided, apply schema repair and validation for both valid and invalid JSON inputs.
- Keep schema-guided dispatch centralized in `JSONParser.parse_json(schema, path)`.
- `patternProperties` matching is intentionally limited to a safe subset; do not execute user-supplied regexes.
- Preserve schema dict identity in `SchemaRepairer.resolve_schema` whenever possible so validator caching remains effective.
- When validating a detached `anyOf` or `oneOf` branch, retain the original root schema's resolver scope so root-relative `$ref` values can resolve `$defs`.
- `schema_repair_mode` supports only `standard` and opt-in `salvage`; salvage may recover strongly evidenced structural mismatches, but must not silently coerce or infer semantic property renames (for example, `results` to `patterns`).
- For sequential top-level fragments, salvage may skip candidates that fail schema repair or validation and return the first schema-valid fragment; never select an item from an actual top-level JSON array.
- Treat user-supplied schemas as an attacker-controlled input surface: deep nesting in schema normalization, validation, and repair paths needs an explicit depth limit or controlled `ValueError`, not an uncaught `RecursionError`.

## Refactor Pitfalls
- In `repair_json`, keep a single shared output-finalization path for logging, `return_objects`, empty-string handling, and `json.dumps`.
- Parser refactors are sensitive to context lifetimes and heuristic branch ordering; preserve malformed-input behavior when restructuring `parse_string` or `parse_object`.
- Recognize unquoted literals only as complete tokens followed by a JSON separator or end-of-input; support case-insensitive `none` as null, but keep quoted values and other barewords as strings.
- Treat comma-separated parenthesized sequences as Python-style tuples that normalize to arrays, while preserving a single parenthesized value as a scalar; Python-style literals are supported only within arrays, objects, and tuples, not as bare top-level values.
- Preserve bare quotes inside compact regex character classes such as `['"]` and `[^'"]`; do not let them split the enclosing JSON value into separate top-level elements.
- When an object property contains an unclosed array of scalar values followed by a quoted `key: value` member, close the array and resume the enclosing object; preserve direct-array and pre-scalar missing-object recovery (`["key": "value"] -> [{"key": "value"}]`).
- Top-level raw decoding may discard a valid prefix only when non-comma garbage follows; preserve complete-input heuristics and defer comma-prefixed continuations to structural object repair.
- Performance regressions often hide in repeated `parse_string` lookahead scans on long malformed object values; include cases with many commas or `}` characters before a far quote, and retain only inputs with a meaningful baseline slowdown (roughly one second or more).
- Normalize top-level `RecursionError` into `ValueError`.
