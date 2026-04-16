# Examples

These examples show how to use `json_repair` in common integration points without changing the library itself.

## Quick start

Run the standard-library-only examples with:

```bash
uv run python examples/repair_llm_output.py
uv run python examples/chinese_llm_output.py
uv run python examples/pydantic_schema.py
uv run python examples/stream_stable.py
```

The FastAPI example needs extra dependencies:

```bash
uv add --group dev fastapi uvicorn
uv run uvicorn examples.fastapi_app:app --reload
```

## Included examples

- [repair_llm_output.py](repair_llm_output.py): Repair JSON wrapped in markdown fences, comments, or extra prose from an LLM response.
- [chinese_llm_output.py](chinese_llm_output.py): Repair Chinese-language JSON while preserving non-Latin characters in the final output.
- [pydantic_schema.py](pydantic_schema.py): Use a Pydantic v2 model as schema guidance, then validate the repaired object.
- [stream_stable.py](stream_stable.py): Keep a stable best-effort JSON snapshot while a streamed response is still incomplete.
- [fastapi_app.py](fastapi_app.py): Repair and validate model output inside a FastAPI endpoint before returning a typed response.
