import os
import pathlib
import time

import pytest

from src.json_repair import repair_json

path = pathlib.Path(__file__).parent.resolve()
CI = os.getenv("CI") is not None

correct_json = (path / "valid.json").read_text()

incorrect_json = (path / "invalid.json").read_text()


def _unclosed_object_string_payload(target_bytes, fragment_factory):
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
def test_true_true_correct(benchmark):
    benchmark(repair_json, correct_json, return_objects=True, skip_json_loads=True)

    # Retrieve the median execution time
    mean_time = benchmark.stats.get("median")

    # Define your time threshold in seconds
    max_time = 3 / 10**3  # 3 millisecond

    # Assert that the average time is below the threshold
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_true_true_incorrect(benchmark):
    benchmark(repair_json, incorrect_json, return_objects=True, skip_json_loads=True)

    # Retrieve the median execution time
    mean_time = benchmark.stats.get("median")

    # Define your time threshold in seconds
    max_time = 3 / 10**3  # 3 millisecond

    # Assert that the average time is below the threshold
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_true_false_correct(benchmark):
    benchmark(repair_json, correct_json, return_objects=True, skip_json_loads=False)
    # Retrieve the median execution time
    mean_time = benchmark.stats.get("median")

    # Define your time threshold in seconds
    max_time = 30 * (1 / 10**6)  # 30 microsecond

    # Assert that the average time is below the threshold
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_true_false_incorrect(benchmark):
    benchmark(repair_json, incorrect_json, return_objects=True, skip_json_loads=False)
    # Retrieve the median execution time
    mean_time = benchmark.stats.get("median")

    # Define your time threshold in seconds
    max_time = 3 / 10**3  # 3 millisecond

    # Assert that the average time is below the threshold
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_false_true_correct(benchmark):
    benchmark(repair_json, correct_json, return_objects=False, skip_json_loads=True)
    # Retrieve the median execution time
    mean_time = benchmark.stats.get("median")

    # Define your time threshold in seconds
    max_time = 3 / 10**3  # 3 millisecond

    # Assert that the average time is below the threshold
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_false_true_incorrect(benchmark):
    benchmark(repair_json, incorrect_json, return_objects=False, skip_json_loads=True)
    # Retrieve the median execution time
    mean_time = benchmark.stats.get("median")

    # Define your time threshold in seconds
    max_time = 3 / 10**3  # 3 millisecond

    # Assert that the average time is below the threshold
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_false_false_correct(benchmark):
    benchmark(repair_json, correct_json, return_objects=False, skip_json_loads=False)
    # Retrieve the median execution time
    mean_time = benchmark.stats.get("median")

    # Define your time threshold in seconds
    max_time = 60 / 10**6  # 60 microsecond

    # Assert that the average time is below the threshold
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_false_false_incorrect(benchmark):
    benchmark(repair_json, incorrect_json, return_objects=False, skip_json_loads=False)
    # Retrieve the median execution time
    mean_time = benchmark.stats.get("median")

    # Define your time threshold in seconds
    max_time = 3 / 10**3  # 3 millisecond

    # Assert that the average time is below the threshold
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_unclosed_object_string_with_many_comma_fragments(benchmark):
    benchmark(
        repair_json,
        unclosed_object_string_fragments,
        return_objects=True,
        skip_json_loads=True,
    )

    mean_time = benchmark.stats.get("median")
    max_time = 75 / 10**3  # 75 millisecond
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_unclosed_object_string_with_mixed_quote_fragments(benchmark):
    benchmark(
        repair_json,
        mixed_quote_object_string_fragments,
        return_objects=True,
        skip_json_loads=True,
    )

    mean_time = benchmark.stats.get("median")
    max_time = 125 / 10**3  # 125 millisecond
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_far_quote_object_string_with_many_comma_fragments():
    start = time.perf_counter()
    repair_json(far_quote_comma_object_string_fragments, return_objects=True, skip_json_loads=True)
    elapsed = time.perf_counter() - start

    max_time = 250 / 10**3  # 250 millisecond
    assert elapsed < max_time, f"Performance regression: {elapsed:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_far_quote_object_string_with_many_brace_fragments():
    start = time.perf_counter()
    repair_json(far_quote_brace_object_string_fragments, return_objects=True, skip_json_loads=True)
    elapsed = time.perf_counter() - start

    max_time = 250 / 10**3  # 250 millisecond
    assert elapsed < max_time, f"Performance regression: {elapsed:.3f}s > {max_time:.3f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_schema_true_false_correct(benchmark):
    pytest.importorskip("jsonschema")
    benchmark(
        repair_json,
        correct_json,
        schema=schema_perf,
        return_objects=True,
        skip_json_loads=False,
    )

    mean_time = benchmark.stats.get("median")
    max_time = 6 / 10**4  # 600 microsecond
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.6f}s > {max_time:.6f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_schema_false_false_correct(benchmark):
    pytest.importorskip("jsonschema")
    benchmark(
        repair_json,
        correct_json,
        schema=schema_perf,
        return_objects=False,
        skip_json_loads=False,
    )

    mean_time = benchmark.stats.get("median")
    max_time = 8 / 10**4  # 800 microsecond
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.6f}s > {max_time:.6f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_schema_true_true_incorrect(benchmark):
    pytest.importorskip("jsonschema")
    benchmark(
        repair_json,
        incorrect_json,
        schema=schema_perf,
        return_objects=True,
        skip_json_loads=True,
    )

    mean_time = benchmark.stats.get("median")
    max_time = 45 / 10**4  # 4.5 millisecond
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.6f}s > {max_time:.6f}s"


@pytest.mark.skipif(CI, reason="Performance tests are skipped in CI")
def test_schema_false_true_incorrect(benchmark):
    pytest.importorskip("jsonschema")
    benchmark(
        repair_json,
        incorrect_json,
        schema=schema_perf,
        return_objects=False,
        skip_json_loads=True,
    )

    mean_time = benchmark.stats.get("median")
    max_time = 45 / 10**4  # 4.5 millisecond
    assert mean_time < max_time, f"Benchmark exceeded threshold: {mean_time:.6f}s > {max_time:.6f}s"
