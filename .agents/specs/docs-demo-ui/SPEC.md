# Demo UI Test Spec

Status: Active

## Overview

- This spec defines when the docs demo needs browser-level validation and what a comprehensive run must prove.
- It applies only to the demo site:
  - `docs/app.py`
  - `docs/index.js`
  - `docs/index.html`
  - `docs/index.zh.html`
  - `docs/styles.css`
- It complements, but does not replace, repo-wide validation such as `uv run pytest` and `pre-commit run --all-files`.
- The intended style is spec-first and agent-executable: the decision to test, the required workflow, and the acceptance criteria must be explicit enough that an agent can follow them without improvising policy.
- The repo already has a dedicated skill for local demo verification:
  - `.agents/skills/docs-demo-local-test/SKILL.md`
- When this spec calls for a demo UI test, that skill is the required entrypoint for local setup and baseline verification.

## Requirements

- The agent MUST choose one of three demo validation levels for every task that touches the demo site:
  - `Level 0`: no demo UI test
  - `Level 1`: local smoke test
  - `Level 2`: comprehensive local UI test
- The agent MUST use `Level 0` when the task does not affect the demo site.
- The agent MUST use `Level 1` for narrow, low-risk demo changes such as copy-only or small CSS-only edits.
- The agent MUST use `Level 2` when any of the following is true:
  - `docs/index.js` changed
  - URL, history, hash/query parsing, local storage, clipboard, reload, or share-link behavior changed
  - schema input, schema mode, or client-side validation behavior changed
  - locale switching or localized UI behavior changed
  - `docs/app.py` changed in a way that affects demo requests or responses
  - the user explicitly asks for UI testing
  - a demo-site bug is being fixed or investigated
  - a docs demo change is being prepared for release and confidence matters
- The agent MUST use Chrome MCP for `Level 1` and `Level 2` browser verification.
- The agent MUST use `.agents/skills/docs-demo-local-test/SKILL.md` as the setup guide for `Level 1` and `Level 2`.
- The agent MUST run demo UI tests against the local demo API and local static site, not the deployed site, unless the user explicitly asks otherwise.
- The agent MUST run `Level 2` in a fresh isolated browser context so prior local storage, stale requests, and previous test state do not contaminate results.
- The agent MUST patch browser `fetch` to target `http://127.0.0.1:5000/api/repair-json` before testing request-driven behavior.
- The agent MUST verify, during `Level 1` and `Level 2`, that at least one request actually hits the local API target.
- The agent MUST leave the local docs page on a clean short URL after any share-state hydration flow; tests for URL behavior are incomplete if they only inspect rendered content.
- The agent MUST treat large-example share behavior as a first-class contract when URL or sharing code changes.
- The agent MUST explicitly report any skipped required scenario in the final response.

## Design

### Test Levels

- `Level 0`
  - No browser work.
  - Typical cases:
    - parser-only or library-only changes under `src/` or `tests/`
    - packaging or release-only changes
    - Markdown-only changes outside the demo UI

- `Level 1`
  - Run the repo-local demo flow from `.agents/skills/docs-demo-local-test/SKILL.md`.
  - Minimum smoke coverage:
    1. Start the local docs API:
       - `UV_CACHE_DIR=/tmp/uv-cache uv run --with flask --with flask-cors python docs/app.py`
    2. Start the local static site:
       - `python3 -m http.server 4173 --directory docs`
    3. Open `http://127.0.0.1:4173/index.html` in Chrome MCP.
    4. Patch `fetch` to target the local API.
    5. Run the baseline schema coercion case:
       - Input JSON: `{"value":"1",}`
       - Schema: `{"type":"object","properties":{"value":{"type":"integer"}},"required":["value"]}`
       - Expected output contains `"value": 1`
       - Expected log contains `Coerced string to integer`
    6. Confirm the request target is `POST http://127.0.0.1:5000/api/repair-json`

- `Level 2`
  - Use the same local-server setup as `Level 1`.
  - Run in a fresh isolated Chrome MCP context.
  - The following matrix is required.

### Comprehensive Matrix

1. Baseline schema-guided repair
   - Run the same coercion case as the smoke test.
   - Confirm the local API request body contains both `malformedJSON` and `schema`.
   - Confirm the response body matches the repaired object and logs.

2. Client-side validation
   - Invalid schema text:
     - enter malformed schema JSON
     - confirm the UI shows the client-side schema error
     - confirm no demo API request is sent
   - Invalid schema mode:
     - if the mode is manipulated to an unsupported value, confirm the UI reports the mode error and does not send the request
   - Salvage without schema:
     - set `schemaRepairMode` to `salvage` with no schema
     - confirm the UI reports the missing-schema error
     - confirm no request is sent

3. Draft persistence
   - Enter non-empty input and optional schema.
   - Confirm draft state is written to local storage.
   - Reload the page.
   - Confirm the input and schema rehydrate from local storage.
   - Confirm the visible page URL remains the short local page path.

4. Small share-link flow
   - Use a small reproducible example.
   - Click the share-link button.
   - Confirm the clipboard write succeeds or the UI reports success.
   - Read the copied URL when possible.
   - Open the copied URL in a fresh isolated context.
   - Confirm input and schema hydrate correctly.
   - Confirm the visible URL is cleaned after hydration.

5. Large share-state flow
   - Use a realistically large payload and a matching schema.
   - The example MUST not be a toy payload. It SHOULD resemble actual demo usage:
     - nested objects and arrays
     - long string fields such as explanations or model output
     - enough size to exceed the readable plain-URL path
     - schema present, not omitted
   - Confirm the page remains usable and the visible URL stays short during editing.
   - Use the share-link button.
   - Confirm the large example follows the intended large-share behavior:
     - if large share links are supported, the copied link is produced in the documented large-share format and can be reopened
     - if large share links are intentionally unsupported, the UI clearly says so and does not poison the visible URL
   - If a large link is copied, open it in a fresh isolated context and confirm:
     - state hydrates correctly
     - the local API receives the request with schema included
     - the visible URL is cleaned after hydration
   - This scenario is mandatory whenever URL, share, history, compression, storage, or clipboard behavior changed.

6. Legacy-link compatibility
   - If older share-link formats are still supported, open at least one legacy link.
   - Confirm state hydrates correctly.
   - Confirm the page cleans the visible URL after hydration.

7. Chinese-page smoke
   - Open `http://127.0.0.1:4173/index.zh.html`.
   - Confirm:
     - the page loads
     - inputs are present
     - share/status copy is rendered in Chinese
     - there is no obvious broken layout or missing control
   - This remains a smoke check unless the bug specifically targets localization.

### Evidence

- A comprehensive run MUST capture enough evidence to audit the result.
- Capture at least:
  - one screenshot of a repaired state
  - one screenshot or network capture showing the large-share case
  - the exact local API request URL
  - the local API request body for at least one schema-guided call
  - any copied share-URL length or share-format details when share behavior is under test
- Save screenshots to a local temporary path and report those paths in the final response.

### Cleanup

- Stop both local servers after the run.

### Reporting

- The final response for a demo UI run should include:
  - whether the run was `Level 1` or `Level 2`
  - whether Chrome MCP was used
  - whether the API target was local
  - which required scenarios passed
  - which required scenarios failed or were left unverified
  - screenshot paths, if captured

### Maintenance

- Update this spec whenever any of the following changes:
  - the demo share-state format
  - the required local-server commands
  - the expected behavior for large examples
  - the minimum comprehensive test matrix
  - the browser tool or local validation workflow
