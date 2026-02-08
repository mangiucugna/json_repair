---
name: docs-demo-local-test
description: Test the docs JSON repair demo against local backend changes before publishing. Use this when modifying docs/app.py or docs UI files and you need local end-to-end verification.
---

# Docs Demo Local Test

## Overview

Use this workflow to validate docs demo behavior with local code only, without relying on the deployed PythonAnywhere API. This is the default verification path for `docs/app.py`, `docs/index.js`, `docs/index.html`, `docs/index.zh.html`, and `docs/styles.css` changes.

## Workflow

1. Start the local demo API server:
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --with flask --with flask-cors python docs/app.py
```
2. Start the local static site server:
```bash
python3 -m http.server 4173 --directory docs
```
3. Open `http://127.0.0.1:4173/index.html`.
4. In browser devtools, patch `fetch` so the page hits local API instead of PythonAnywhere:
```javascript
() => {
  const target = "https://mangiucugna.pythonanywhere.com/api/repair-json";
  const local = "http://127.0.0.1:5000/api/repair-json";
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    let nextInput = input;
    if (typeof input === "string" && input === target) {
      nextInput = local;
    } else if (input instanceof Request && input.url === target) {
      nextInput = new Request(local, input);
    }
    return originalFetch(nextInput, init);
  };
  return "fetch patched";
}
```
5. Run a schema coercion check:
- Input JSON: `{"value":"1",}`
- Schema: `{"type":"object","properties":{"value":{"type":"integer"}},"required":["value"]}`
- Expected output JSON: `{"value": 1}`
- Expected log contains: `Coerced string to integer`
6. Confirm network request target is local:
- `POST http://127.0.0.1:5000/api/repair-json`
7. Capture screenshot if needed.
8. Stop both local servers with `Ctrl+C`.

## Troubleshooting

- If `uv run` fails with cache permission errors, rerun with `UV_CACHE_DIR=/tmp/uv-cache`.
- If Flask modules are missing, keep using `uv run --with flask --with flask-cors ...`.
- If output still matches production behavior, the fetch patch did not apply; reload and patch again before typing input.
