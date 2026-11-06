import json
import pathlib
from io import StringIO

import pytest

from src.json_repair.json_repair import from_file, load


@pytest.mark.parametrize("skip_json_loads", [False, True])
def test_load_repairs_missing_opening_brace_from_current_position(skip_json_loads: bool) -> None:
    prefix = '{"stale": true}\n'
    fd = StringIO(prefix + '\n"a": {"b": "你好"}}\n')
    fd.seek(len(prefix))
    result = load(fd, logging=True, skip_json_loads=skip_json_loads, chunk_length=2)
    assert isinstance(result, tuple)
    value, logs = result
    assert value == {"a": {"b": "你好"}}
    assert any("opening object brace" in entry["text"] for entry in logs)


def test_load_declines_missing_opening_brace_with_trailing_content() -> None:
    assert load(StringIO('"a": 1} {"b": 2}'), chunk_length=2) == {"b": 2}


def test_load_strict_rejects_missing_opening_brace() -> None:
    with pytest.raises(ValueError, match="Missing opening object brace"):
        load(StringIO('"a": 1}'), strict=True, chunk_length=2)


def test_load_repairs_from_current_file_position() -> None:
    prefix = '{"stale": true}\n'
    raw = prefix + '{"key": }'

    for skip_json_loads in [False, True]:
        fd = StringIO(raw)
        fd.seek(len(prefix))

        assert load(fd, skip_json_loads=skip_json_loads, chunk_length=2) == {"key": ""}


@pytest.mark.parametrize("chunk_length", [0, 2], ids=["default-buffer", "small-buffer"])
def test_repair_json_from_file(chunk_length: int) -> None:
    path = pathlib.Path(__file__).parent
    expected = json.loads((path / "valid.json").read_text())

    assert from_file(filename=path / "invalid.json", chunk_length=chunk_length) == expected


@pytest.mark.parametrize("chunk_length", [0, 2], ids=["default-buffer", "small-buffer"])
def test_repair_json_from_file_logging(tmp_path: pathlib.Path, chunk_length: int) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text("{key:value}")

    assert from_file(filename=input_path, logging=True, chunk_length=chunk_length) == (
        {"key": "value"},
        [
            {
                "text": "While parsing a string, we found a literal instead of a quote",
                "context": "{key:value}",
            },
            {
                "context": "{key:value}",
                "text": "While parsing a string missing the left delimiter in object key context, we found a :, stopping here",
            },
            {
                "text": "While parsing a string, we missed the closing quote, ignoring",
                "context": "{key:value}",
            },
            {
                "text": "While parsing a string, we found a literal instead of a quote",
                "context": "{key:value}",
            },
            {
                "context": "{key:value}",
                "text": "While parsing a string missing the left delimiter in object value context, we found a , or } and we couldn't determine that a right delimiter was present. Stopping here",
            },
            {
                "text": "While parsing a string, we missed the closing quote, ignoring",
                "context": "{key:value}",
            },
        ],
    )


def test_repair_json_from_large_file(tmp_path: pathlib.Path) -> None:
    input_path = tmp_path / "large.json"
    input_path.write_text("x" * 5 * 1024 * 1024)

    assert from_file(filename=input_path, logging=True) == ("", [])


@pytest.mark.parametrize("raw", ['{"key": 1}', '{"key": }'])
@pytest.mark.parametrize("skip_json_loads", [False, True])
def test_load_non_seekable_stream(raw: str, skip_json_loads: bool) -> None:
    class NonSeekableStream(StringIO):
        def seekable(self) -> bool:
            return False

        def tell(self) -> int:
            raise OSError("not seekable")

    fd = NonSeekableStream("ignored" + raw)
    fd.read(len("ignored"))
    assert load(fd, skip_json_loads=skip_json_loads, logging=True) == load(
        StringIO(raw), skip_json_loads=skip_json_loads, logging=True
    )
