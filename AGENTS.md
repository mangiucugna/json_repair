# Repo Notes for Codex

## Environment
- Use the uv-managed environment at `.venv`; install dev dependencies with `uv sync --group dev`.
- Prefer `uv run ...` for Python tooling (use `uv run python -m ...` if `python` is not on PATH).
- Dependency groups live in `pyproject.toml`; update `uv.lock` when dependencies change.

## Tests
- Run the full test suite with:
  - `uv run pytest`
- Performance benchmarks in `tests/test_performance.py` are timing-sensitive and may fail on slower machines.
- Keep schema-based performance coverage in `tests/test_performance.py` for both fast-path (`skip_json_loads=False`) and parser-path (`skip_json_loads=True`) scenarios.

## Pre-commit
- Run all hooks without activating a venv:
  - `pre-commit run --all-files`
- The `pre-commit autoupdate` hook can modify `.pre-commit-config.yaml` (e.g., bumping hook revs). Re-run pre-commit after updates.
- Hooks like `ruff-pre-commit` and `semgrep` require network access to fetch resources.
- Always run pre-commit fully; do not leave it partially completed.
- For new/untracked files, manually run ruff (`pre-commit run ruff-check --files ...` and `pre-commit run ruff-format --files ...`) because hooks with `pass_filenames: true` won't see them.

## Packaging
- For slimmer source distributions, keep a `MANIFEST.in` rule `prune tests` so test modules are not shipped in the sdist.
- In `[tool.setuptools.package-data]`, use the real package key (`json_repair`) rather than placeholders, otherwise typed marker inclusion (`py.typed`) can be brittle.
- In release publishing, run a metadata sanity check (`uvx twine check dist/*`) after building and before the PyPI publish step.
- In CI, prefer `uv run --group ... --frozen` for project-aware checks (tests/type-check) and reserve `uvx` for standalone tool invocations.

## Releases
- Project version lives in `pyproject.toml` under `[project].version`.
- Use semantic versioning; patch bumps are appropriate for bug fixes.

## Docs
- Keep `README.zh.md` aligned with `README.md` when updating contributor guidance or usage notes.
- For local docs demo validation (API + UI + network target checks), follow `.agents/skills/docs-demo-local-test/SKILL.md`.

## Commits
- Prefer descriptive commit messages with a short summary line and a brief bullet list of key changes.
- When closing issues, start the summary with `Fix #<issue-number>:` so GitHub auto-closes.

## Code Areas
- API and CLI entry points: `src/json_repair/json_repair.py`, `src/json_repair/__init__.py`, `src/json_repair/__main__.py`.
- Parser orchestration: `src/json_repair/json_parser.py`.
- Repair primitives: `src/json_repair/parse_*.py`, `src/json_repair/parse_string_helpers/*`.
- Schema logic: `src/json_repair/schema_repair.py`.
- Demo API/UI: `docs/app.py`, `docs/index.js`, `docs/index*.html`, `docs/styles.css`.
- Tests: parser tests (`tests/test_parse_*.py`), schema tests (`tests/test_schema_*.py`), CLI/API wrappers, strict-mode tests, performance benchmarks.

## Contributing
- PRs follow `.github/PULL_REQUEST_TEMPLATE.md` (review `CONTRIBUTING.md`, add tests, and run pre-commit + unit tests).

## Style preferences
- Avoid extracting small, non-shared helper functions if the original block is short; keep logic inline for readability.
- For JSONParser logging, prefer the inline no-op lambda over a module-level `_noop` helper.
- JSONParser.parse should return only JSON; use `parser.logger` for logs instead of tuple returns.
- Add brief docstrings/comments for non-obvious control flow; explain intent, not mechanics.
- Parser fast paths must work for both plain strings and `StringFileWrapper`; do not assume `str`-only helpers such as `.find()` inside parse helpers.
- When adding new repair heuristics, emit a `self.log` entry and skip the repair in `strict=True` unless explicitly intended.
- Do not wrap `importlib.import_module(...)` in an extra `@cache` helper here; Python already caches imported modules, and the extra wrapper adds complexity without measurable benefit in this project.
- For Ruff config changes, trial candidate rule families with `ruff check --statistics` first, then enable only the specific high-signal codes that fit the repo instead of broad noisy families.
- For exception-style Ruff rules, prefer targeted control-flow rules like `TRY300` over rules like `TRY004` that would change public exception types unless an API behavior change is explicitly intended.

## Schema-guided parsing
- When a schema is provided, apply schema repair+validation for both valid and invalid JSON inputs.
- On the `json.loads/json.load` fast path, validate the loaded value against the schema first.
- On speculative schema checks in the `json.loads/json.load` fast path, prefer a boolean validity probe (`is_valid`) over full error materialization; reserve `validate(...)` for the final error-reporting path.
- If fast-path loading or schema validation fails, fall back to `parser.parse_with_schema(...)`, then validate the parsed result before returning.
- Keep schema-guided dispatch centralized in `JSONParser.parse_json(schema, path)`; avoid duplicating parser switch logic.
- `patternProperties` matching uses a safe literal+anchor subset (`token`, `^token`, `token$`, `^token$`) and must not execute user-supplied regex patterns.
- `SchemaRepairer.repair_value` enforces a subset of JSON Schema; keep `SchemaRepairer.validate(...)` to enforce unsupported keywords (e.g., `pattern`, `minLength`, `maximum`, formats/combinators not repaired directly).
- `schema_repair_mode` supports `standard` (default) and `salvage`; `salvage` is opt-in and should only add best-effort repairs (currently array-item dropping + conservative list-to-object mapping).
- Boolean schema coercion is mode-independent: apply expanded safe tokens (`true/false`, `yes/no`, `y/n`, `on/off`, `1/0`, and numeric `1`/`0`) in both `standard` and `salvage`.
- `schema_repair_mode="salvage"` without a schema must raise a `ValueError` instead of silently downgrading behavior.
- Treat `skip_json_loads=True` as an explicit opt-out of JSON loader fast paths; do not add schema-aware scalar fast-repair behavior in that mode.

## Known review pitfalls
- In `SchemaRepairer._repair_type_union`, validate each candidate branch before returning so mixed `type` unions (for example `["object", "array"]`) can fall back to a later valid branch instead of failing on the first repaired branch.
- In salvage mode, keep list-to-object/root-array object salvage heuristics scoped to object-only schemas; when array is also allowed at the same schema level, skip those heuristics to avoid accidental shape changes.
- In `repair_json`, keep a single shared output-finalization block (`logging` / `return_objects` / empty-string / `json.dumps`) and avoid duplicating it across fast-path/parser branches; duplicated return trees drift and cause behavior mismatches.
- In `schema_repair_mode="salvage"`, only drop array items for data-repair failures; propagate schema-definition errors (e.g., unsupported schema types) instead of silently returning partial output.
