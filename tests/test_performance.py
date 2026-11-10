import os
import pathlib
import time
from collections.abc import Callable

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from src.json_repair import repair_json

path = pathlib.Path(__file__).parent.resolve()
CI = os.getenv("CI") is not None

correct_json = (path / "valid.json").read_text()

incorrect_json = (path / "invalid.json").read_text()


def _unclosed_object_string_payload(target_bytes: int, fragment_factory: Callable[[int], str]) -> str:
    base = '{"a": "'
    pieces = []
    index = 0
    while len(base) + len(",".join(pieces)) < target_bytes:
        pieces.append(fragment_factory(index))
        index += 1
    return base + ",".join(pieces)


unclosed_object_string_fragments = '{"a": "' + ",".join("fragment" for _ in range(3000))
mixed_quote_object_string_fragments = _unclosed_object_string_payload(
    35000,
    lambda index: 'frag"ment' if index % 3 == 0 else ("'fragment'" if index % 3 == 1 else "fragment"),
)
far_quote_comma_object_string_fragments = '{"a": "' + ("x," * 10_000) + '" tail'
far_quote_brace_object_string_fragments = '{"a": "' + ("x}" * 5_000) + '" tail'
unclosed_object_string_escaped_newlines = '{"a": "' + ("x\\n" * 5_000)
unclosed_object_string_long_content = '{"a": "' + ("value = compute(item)\\n" * 10_000)
unquoted_object_value_long_content = '{"a": ' + ("The quick brown fox jumps over the lazy dog " * 5_000) + "}"
array_strings_with_inner_quotes = "[" + ", ".join(f'"he said "hi {index}" to me"' for index in range(2_000)) + "]"
array_object_string_with_many_brackets = (
    '[{"answer": "' + ("Paris is the capital of France [1] and Lyon is big [2].\\n" * 800) + '"},]'
)
unclosed_object_string_with_many_braces = '{"a": "' + ("text } more " * 3_000)
table_rows_after_missing_row_bracket = (
    '{"headers": ["name", "status"], "rows": [["item 0", "ok"], "item 1", "ok"], '
    + ", ".join(f'["item {i}", "ok"]' for i in range(2, 4_000))
    + "]}"
)
long_prose_before_json = (
    "Let me think about this carefully. The user wants a list of cities, so I will check each one. " * 2_000
    + '```json\n{"cities": ["Paris", "Lyon"]}\n```'
)
parenthesized_prose_lines_before_json = (
    "".join(f"({i}) Step {i}: check the input and compute the value.\n" for i in range(6_000))
    + '```json\n{"answer": 42}\n```'
)

schema_perf = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "_id": {"type": "string"},
            "index": {"type": "integer"},
            "guid": {"type": "string"},
            "isActive": {"type": "boolean"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "friends": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                    "required": ["id", "name"],
                },
            },
        },
        "required": ["_id", "index", "guid", "isActive", "tags", "friends"],
        "additionalProperties": True,
    },
}


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
@pytest.mark.parametrize(
    ("raw", "return_objects", "skip_json_loads", "max_time"),
    [
        pytest.param(correct_json, True, True, 3 / 10**3, id="true_true_correct"),
        pytest.param(incorrect_json, True, True, 3 / 10**3, id="true_true_incorrect"),
        pytest.param(correct_json, True, False, 30 * (1 / 10**6), id="true_false_correct"),
        pytest.param(incorrect_json, True, False, 3 / 10**3, id="true_false_incorrect"),
        pytest.param(correct_json, False, True, 3 / 10**3, id="false_true_correct"),
        pytest.param(incorrect_json, False, True, 3 / 10**3, id="false_true_incorrect"),
        pytest.param(correct_json, False, False, 60 / 10**6, id="false_false_correct"),
        pytest.param(incorrect_json, False, False, 3 / 10**3, id="false_false_incorrect"),
    ],
)
def test_repair_performance(
    benchmark: BenchmarkFixture, raw: str, return_objects: bool, skip_json_loads: bool, max_time: float
) -> None:
    benchmark(
        repair_json,
        raw,
        return_objects=return_objects,
        skip_json_loads=skip_json_loads,
    )

    assert benchmark.stats is not None
    median_time = benchmark.stats.get("median")
    assert median_time < max_time, f"Benchmark exceeded threshold: {median_time:.6f}s > {max_time:.6f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_unclosed_object_string_with_many_comma_fragments(benchmark: BenchmarkFixture) -> None:
    benchmark(
        repair_json,
        unclosed_object_string_fragments,
        return_objects=True,
        skip_json_loads=True,
    )

    assert benchmark.stats is not None
    mean_time = benchmark.stats.get("median")
    max_time = 75 / 10**3  # 75 millisecond
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_unclosed_object_string_with_mixed_quote_fragments(benchmark: BenchmarkFixture) -> None:
    benchmark(
        repair_json,
        mixed_quote_object_string_fragments,
        return_objects=True,
        skip_json_loads=True,
    )

    assert benchmark.stats is not None
    mean_time = benchmark.stats.get("median")
    max_time = 125 / 10**3  # 125 millisecond
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_far_quote_object_string_with_many_comma_fragments() -> None:
    start = time.perf_counter()
    repair_json(far_quote_comma_object_string_fragments, return_objects=True, skip_json_loads=True)
    elapsed = time.perf_counter() - start

    max_time = 250 / 10**3  # 250 millisecond
    assert elapsed < max_time, f"Performance regression: {elapsed:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_far_quote_object_string_with_many_brace_fragments() -> None:
    start = time.perf_counter()
    repair_json(far_quote_brace_object_string_fragments, return_objects=True, skip_json_loads=True)
    elapsed = time.perf_counter() - start

    max_time = 250 / 10**3  # 250 millisecond
    assert elapsed < max_time, f"Performance regression: {elapsed:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_unclosed_object_string_with_many_escaped_newlines() -> None:
    start = time.perf_counter()
    repair_json(unclosed_object_string_escaped_newlines, return_objects=True, skip_json_loads=True)
    elapsed = time.perf_counter() - start

    max_time = 250 / 10**3  # 250 millisecond
    assert elapsed < max_time, f"Performance regression: {elapsed:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
@pytest.mark.parametrize(
    ("raw", "return_objects", "skip_json_loads", "max_time"),
    [
        pytest.param(correct_json, True, False, 6 / 10**4, id="schema_true_false_correct"),
        pytest.param(correct_json, False, False, 8 / 10**4, id="schema_false_false_correct"),
        pytest.param(incorrect_json, True, True, 45 / 10**4, id="schema_true_true_incorrect"),
        pytest.param(incorrect_json, False, True, 45 / 10**4, id="schema_false_true_incorrect"),
    ],
)
def test_schema_repair_performance(
    benchmark: BenchmarkFixture, raw: str, return_objects: bool, skip_json_loads: bool, max_time: float
) -> None:
    pytest.importorskip("jsonschema")
    benchmark(
        repair_json,
        raw,
        return_objects=return_objects,
        skip_json_loads=skip_json_loads,
        schema=schema_perf,
    )

    assert benchmark.stats is not None
    median_time = benchmark.stats.get("median")
    assert median_time < max_time, f"Benchmark exceeded threshold: {median_time:.6f}s > {max_time:.6f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
@pytest.mark.parametrize(
    ("raw", "skip_json_loads", "max_time"),
    [
        pytest.param(unclosed_object_string_long_content, True, 1, id="long-unclosed-string"),
        pytest.param(unquoted_object_value_long_content, True, 0.25, id="long-unquoted-value"),
        pytest.param(array_strings_with_inner_quotes, True, 1, id="array-inner-quotes"),
        pytest.param(array_object_string_with_many_brackets, False, 0.25, id="brackets-in-string"),
        pytest.param(unclosed_object_string_with_many_braces, True, 1, id="braces-in-string"),
        pytest.param(table_rows_after_missing_row_bracket, True, 0.25, id="table-row-continuations"),
        pytest.param(long_prose_before_json, False, 0.01, id="prose-before-json"),
        pytest.param(parenthesized_prose_lines_before_json, False, 0.25, id="parenthesized-prose"),
    ],
)
def test_long_input_repair_performance(raw: str, skip_json_loads: bool, max_time: float) -> None:
    start = time.perf_counter()
    repair_json(raw, return_objects=True, skip_json_loads=skip_json_loads)
    elapsed = time.perf_counter() - start

    assert elapsed < max_time, f"Performance regression: {elapsed:.3f}s > {max_time:.3f}s"
