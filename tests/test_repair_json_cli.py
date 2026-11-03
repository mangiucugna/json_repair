import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.json_repair.json_repair import cli


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    raw = "{key:value"
    expected = '{\n"key": "value"\n}'
    input_path.write_text(raw)

    cli(inline_args=[str(input_path), "--indent", "0", "--ensure_ascii"])
    assert capsys.readouterr().out == expected + "\n"

    cli(inline_args=[str(input_path), "--indent", "0", "-o", str(output_path)])
    assert output_path.read_text() == expected

    cli(inline_args=[str(input_path), "--indent", "0", "-i"])
    assert input_path.read_text() == expected

    with patch("sys.stdin", new=io.StringIO(raw)):
        cli(inline_args=["--indent", "0"])
    assert capsys.readouterr().out == expected + "\n"


def test_cli_inline_requires_filename(capsys: pytest.CaptureFixture[str]) -> None:
    """cli() should exit with an error when --inline is passed without a filename."""
    with pytest.raises(SystemExit) as exc:
        cli(inline_args=["--inline"])
    captured = capsys.readouterr()
    assert captured.err.strip() == "Error: Inline mode requires a filename"
    assert exc.value.code != 0


def test_cli_inline_and_output_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """cli() should exit with an error when --inline and --output are used together."""
    outfile = tmp_path / "out.json"
    with pytest.raises(SystemExit) as exc:
        cli(inline_args=["dummy.json", "--inline", "--output", str(outfile)])
    captured = capsys.readouterr()
    assert captured.err.strip() == "Error: You cannot pass both --inline and --output"
    assert exc.value.code != 0


def test_cli_schema_file_guides_repair(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pytest.importorskip("jsonschema")
    schema_path = tmp_path / "schema.json"
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    schema_path.write_text(json.dumps(schema))
    input_path = tmp_path / "input.json"
    input_path.write_text('{"value": }')

    cli(inline_args=[str(input_path), "--indent", "0", "--schema", str(schema_path)])
    captured = capsys.readouterr()
    assert captured.out == '{\n"value": 0\n}\n'


def test_cli_schema_applies_to_valid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pytest.importorskip("jsonschema")
    schema_path = tmp_path / "schema.json"
    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    schema_path.write_text(json.dumps(schema))
    input_path = tmp_path / "input.json"
    input_path.write_text('{"value": "1"}')

    cli(inline_args=[str(input_path), "--indent", "0", "--schema", str(schema_path)])
    captured = capsys.readouterr()
    assert captured.out == '{\n"value": 1\n}\n'

    cli(
        inline_args=[
            str(input_path),
            "--indent",
            "0",
            "--schema",
            str(schema_path),
            "--skip-json-loads",
        ]
    )
    captured = capsys.readouterr()
    assert captured.out == '{\n"value": 1\n}\n'


def test_cli_schema_model_guides_repair(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("jsonschema")
    pytest.importorskip("pydantic", minversion="2")

    module_path = tmp_path / "schema_model.py"
    module_path.write_text("from pydantic import BaseModel\n\n\nclass SchemaModel(BaseModel):\n    value: int\n")
    monkeypatch.syspath_prepend(tmp_path)

    input_path = tmp_path / "input.json"
    input_path.write_text('{"value": "1"}')

    cli(
        inline_args=[
            str(input_path),
            "--indent",
            "0",
            "--schema-model",
            "schema_model:SchemaModel",
            "--skip-json-loads",
        ]
    )
    captured = capsys.readouterr()
    assert captured.out == '{\n"value": 1\n}\n'


def test_cli_schema_and_strict_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"type": "integer"}))
    input_path = tmp_path / "input.json"
    input_path.write_text('{"value": }')

    with pytest.raises(SystemExit) as exc:
        cli(inline_args=[str(input_path), "--schema", str(schema_path), "--strict"])
    captured = capsys.readouterr()
    assert "schema" in captured.err.lower()
    assert exc.value.code != 0


def test_cli_schema_and_schema_model_are_mutually_exclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"type": "integer"}))

    with pytest.raises(SystemExit) as exc:
        cli(
            inline_args=[
                "dummy.json",
                "--schema",
                str(schema_path),
                "--schema-model",
                "schema_model:SchemaModel",
            ]
        )
    captured = capsys.readouterr()
    assert "schema" in captured.err.lower()
    assert exc.value.code != 0


def test_cli_schema_repair_mode_salvage_requires_schema(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli(inline_args=["--schema-repair-mode", "salvage"])
    captured = capsys.readouterr()
    assert "schema-repair-mode" in captured.err.lower()
    assert exc.value.code != 0


def test_cli_schema_repair_mode_salvage_drops_invalid_items(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pytest.importorskip("jsonschema")
    schema_path = tmp_path / "schema.json"
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "score": {"type": "number"},
                    },
                    "required": ["id", "score"],
                },
            }
        },
        "required": ["items"],
    }
    schema_path.write_text(json.dumps(schema))
    input_path = tmp_path / "input.json"
    input_path.write_text('{"items":[{"id":1,"score":85.6},{"id":2,"score":"N/A"}]}')

    cli(
        inline_args=[
            str(input_path),
            "--indent",
            "0",
            "--schema",
            str(schema_path),
            "--schema-repair-mode",
            "salvage",
        ]
    )
    captured = capsys.readouterr()
    assert captured.out == '{\n"items": [\n{\n"id": 1,\n"score": 85.6\n}\n]\n}\n'
