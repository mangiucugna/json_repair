# Repo Notes for Codex

## Environment
- Use the uv-managed environment at `.venv`; install dev dependencies with `uv sync --group dev`.
- Prefer `uv run ...` for Python tooling.
- Dependency groups live in `pyproject.toml`; update `uv.lock` when dependencies change.

## Validation
- Run the full test suite with `uv run pytest`.
- Run the full hook stack with `pre-commit run --all-files`.
- `tests/test_performance.py` is timing-sensitive and can fail on slower machines.
- Keep schema performance coverage in `tests/test_performance.py` for both fast-path (`skip_json_loads=False`) and parser-path (`skip_json_loads=True`) scenarios.
- The `uv-lock-upgrade` hook can rewrite `uv.lock`, including the local `json-repair` package version, so restage it before committing after version bumps or dependency changes.
- Keep schema-only dependencies in their own `schema` group; CI jobs that only exercise core parser paths should use `--no-default-groups` and omit `schema` so Python prerelease jobs are not blocked on upstream PyO3 wheels.

## Release / Packaging
- Project version lives in `pyproject.toml` under `[project].version`; use semantic versioning, with patch bumps for bug fixes.
- Keep `MANIFEST.in` pruning `tests` so test modules are not shipped in the sdist.
- In `[tool.setuptools.package-data]`, use the real package key `json_repair` so `py.typed` stays included reliably.
- Run `uvx twine check dist/*` after building and before publishing.
- Gate optional schema dependencies with `python_full_version` markers during new Python prerelease cycles so core installs and non-schema tests can still run before upstream PyO3 wheels are available.

## Docs
- Keep `README.zh.md` aligned with `README.md` when contributor guidance or usage behavior changes.
- For local docs demo validation, follow `.agents/skills/docs-demo-local-test/SKILL.md`.

## Code Areas
- API and CLI entry points: `src/json_repair/json_repair.py`, `src/json_repair/__init__.py`, `src/json_repair/__main__.py`.
- Parser orchestration: `src/json_repair/json_parser.py`.
- Repair primitives: `src/json_repair/parse_*.py`, `src/json_repair/parse_string_helpers/*`.
- Schema logic: `src/json_repair/schema_repair.py`.
- Demo API/UI: `docs/app.py`, `docs/index.js`, `docs/index*.html`, `docs/styles.css`.

## Repo-Specific Implementation Notes
- Avoid extracting short, non-shared helpers in parser code when the inline logic is still readable.
- `JSONParser.parse` should return only JSON; use `parser.logger` for logs instead of tuple returns.
- Parser fast paths must work for both plain strings and `StringFileWrapper`; do not rely on `str`-only helpers inside parse helpers.
- When adding repair heuristics, emit a `self.log` entry and keep `strict=True` conservative unless the relaxed behavior is explicitly intended.
- In `parse_string` object-value context, comma heuristics should stop only for plausible next members; commas followed by prose or inline raw containers like `{"blank_1": ...}` belong to the string.
- In `parse_string` object-value context, brace heuristics for `}` before triple backticks must not truncate quoted multiline strings that contain literal fenced snippets like ````{}````.
- In `parse_string` object-value context, brace heuristics for `}` before triple backticks must also preserve fenced snippets followed by literal quoted prose such as ````}```"a``; otherwise the parser truncates the current member and drops later keys.
- In `parse_string` object-value context, the `}` before triple-backticks heuristic must not scan through quotes inside a following raw container that is outside the string, but literal container content such as ```` [1,2],\n"`` can still belong to the current string; treat `container + comma` as outside the string only when that comma actually starts the next object member.
- When `parse_string` decides that a post-fence raw container still belongs to the current object-value string, carry that decision into the actual scan and consume the balanced container as string content; lookahead-only fixes still let inner quotes inside `[... "x" ...]` or `{"k":"v"}` terminate the string early.
- Inside a post-fence raw container that is being preserved as literal string content, do not reinterpret `#`, `//`, or `/* */` sequences as actual comments; slash-heavy literals like `[http://x]` and `[/a//b/]` must stay intact.
- Inside a post-fence raw container that is being preserved as literal string content, only treat inner `[`/`{`/`(` as nested structure when the preceding significant character makes a nested value plausible; unmatched inner delimiters like `[foo[bar]` can be plain prose.
- After `,` or `:` inside a preserved post-fence raw container, inner `[`/`{`/`(` still need a plausible structured next token; prose such as `[foo, [bar]` must stay literal even though the delimiter could also start a real nested value.
- For preserved post-fence raw containers, digit-starting nested arrays or parenthesized values after `,` or `:` are still structured; otherwise `_skip_inline_container(...)` can stop at the first inner `]` or `)` and let later bare-key-like prose steal the next member.
- If text after a post-fence `[`/`{`/`(` cannot be balanced as a raw container, fall back to the generic quote scan instead of forcing the string closed; unbalanced bracket-like prose such as ```` [{`` can still belong to the current string.
- In `parse_string` object-value context, do not let `quote + whitespace + quote` short-circuit before misplaced-quote recovery when a next member follows; malformed multiline strings can place a stray quote on its own line before the real terminator, and that next key may be quoted, comment-prefixed, or bare, but `,}` and trailing commas at EOF must still terminate the value instead of being treated as another member, and generic comma classification must stay conservative about multiline curly-quoted prose inside strings.
- When a schema is provided, apply schema repair and validation for both valid and invalid JSON inputs.
- Keep schema-guided dispatch centralized in `JSONParser.parse_json(schema, path)`; avoid duplicating parser switch logic.
- `patternProperties` matching is intentionally limited to a safe literal-plus-anchor subset; do not execute user-supplied regexes.
- `SchemaRepairer.repair_value` repairs only a subset of JSON Schema; `SchemaRepairer.validate(...)` must remain the enforcement path for unsupported keywords.
- `schema_repair_mode` supports only `standard` and opt-in `salvage`; `salvage` should stay limited to best-effort structural recovery.
- `schema_repair_mode="salvage"` without a schema must raise `ValueError`.
- Treat `skip_json_loads=True` as an explicit opt-out of JSON loader fast paths.

## Known Pitfalls
- In `SchemaRepairer._repair_type_union`, validate each candidate branch before returning so mixed unions can fall back to a later valid branch.
- In salvage mode, keep list-to-object/root-array salvage heuristics scoped to object-only schemas; skip them when array is also allowed at that level.
- In `repair_json`, keep a single shared output-finalization path for logging, `return_objects`, empty-string handling, and `json.dumps`.
- In `schema_repair_mode="salvage"`, only drop array items for data-repair failures; propagate schema-definition errors.
- In `parse_object`, keep the empty-object-to-array fallback gated by object-shape detection; escaped object keys or object-style `:` separators must stay on the object-repair path instead of being reclassified as set literals.
- Parser refactors are sensitive to context lifetimes and heuristic branch ordering; preserve malformed-input behavior when restructuring `parse_string` and `parse_object`.
- Normalize `RecursionError` from the top-level repair parser entry point into `ValueError`; downstream callers commonly handle parse failures but not raw recursion exceptions.
- Parenthesized Python syntax must distinguish explicit tuples like `()` and `(1,)` from grouped scalars like `(1)`, and array repair must preserve the expected closing delimiter so `[` inputs still log a missing `]` when they end with `)`.
- Top-level `(` scanning must stay more conservative than nested tuple parsing; inline prose or numbered headings can contain parentheses before the real JSON block, so only standalone parenthesized values should start a top-level parse.
- Top-level comment skipping currently bounces between `parse_json` and `parse_comment`; prefer iterative re-entry when touching that flow because comment-heavy inputs can hit `RecursionError` after a few hundred comments.
