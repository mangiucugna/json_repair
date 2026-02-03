import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.json_repair.json_repair import cli


def test_cli(capsys):
    # Create a temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
    _, tempout_path = tempfile.mkstemp(suffix=".json")
    temp_path = Path(temp_path)
    tempout_path = Path(tempout_path)
    try:
        # Write content to the temporary file
        with os.fdopen(temp_fd, "w") as tmp:
            tmp.write("{key:value")
        cli(inline_args=[str(temp_path), "--indent", "0", "--ensure_ascii"])
        captured = capsys.readouterr()
        assert captured.out == '{\n"key": "value"\n}\n'

        # Test the output option
        cli(inline_args=[str(temp_path), "--indent", "0", "-o", str(tempout_path)])
        with tempout_path.open() as tmp:
            out = tmp.read()
        assert out == '{\n"key": "value"\n}'

        # Test the inline option
        cli(inline_args=[str(temp_path), "--indent", "0", "-i"])
        with temp_path.open() as tmp:
            out = tmp.read()
        assert out == '{\n"key": "value"\n}'

    finally:
        # Clean up - delete the temporary file
        temp_path.unlink()
        tempout_path.unlink()

    # Prepare a JSON string that needs to be repaired.
    test_input = "{key:value"
    # Expected output when running cli with --indent 0.
    expected_output = '{\n"key": "value"\n}\n'
    # Patch sys.stdin so that cli() reads from it instead of a file.
    with patch("sys.stdin", new=io.StringIO(test_input)):
        cli(inline_args=["--indent", "0"])
    captured = capsys.readouterr()
    assert captured.out == expected_output


def test_cli_inline_requires_filename(capsys):
    """cli() should exit with an error when --inline is passed without a filename."""
    with pytest.raises(SystemExit) as exc:
        cli(inline_args=["--inline"])
    captured = capsys.readouterr()
    assert captured.err.strip() == "Error: Inline mode requires a filename"
    assert exc.value.code != 0


def test_cli_inline_and_output_error(tmp_path, capsys):
    """cli() should exit with an error when --inline and --output are used together."""
    outfile = tmp_path / "out.json"
    with pytest.raises(SystemExit) as exc:
        cli(inline_args=["dummy.json", "--inline", "--output", str(outfile)])
    captured = capsys.readouterr()
    assert captured.err.strip() == "Error: You cannot pass both --inline and --output"
    assert exc.value.code != 0


def test_cli_schema_file_guides_repair(tmp_path, capsys):
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


def test_cli_schema_skip_json_loads_controls_validation(tmp_path, capsys):
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
    assert captured.out == '{\n"value": "1"\n}\n'

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


def test_cli_schema_model_guides_repair(tmp_path, capsys, monkeypatch):
    pytest.importorskip("jsonschema")
    pydantic = pytest.importorskip("pydantic")
    version = getattr(pydantic, "VERSION", getattr(pydantic, "__version__", "0"))
    if int(version.split(".")[0]) < 2:
        pytest.skip("pydantic v2 required")

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


def test_cli_schema_and_strict_error(tmp_path, capsys):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"type": "integer"}))
    input_path = tmp_path / "input.json"
    input_path.write_text('{"value": }')

    with pytest.raises(SystemExit) as exc:
        cli(inline_args=[str(input_path), "--schema", str(schema_path), "--strict"])
    captured = capsys.readouterr()
    assert "schema" in captured.err.lower()
    assert exc.value.code != 0


def test_cli_schema_and_schema_model_are_mutually_exclusive(tmp_path, capsys):
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
