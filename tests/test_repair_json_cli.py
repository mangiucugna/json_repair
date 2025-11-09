import io
import os
import tempfile
from unittest.mock import patch

import pytest

from src.json_repair.json_repair import cli


def test_cli(capsys):
    # Create a temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".json")
    _, tempout_path = tempfile.mkstemp(suffix=".json")
    try:
        # Write content to the temporary file
        with os.fdopen(temp_fd, "w") as tmp:
            tmp.write("{key:value")
        cli(inline_args=[temp_path, "--indent", "0", "--ensure_ascii"])
        captured = capsys.readouterr()
        assert captured.out == '{\n"key": "value"\n}\n'

        # Test the output option
        cli(inline_args=[temp_path, "--indent", "0", "-o", tempout_path])
        with open(tempout_path) as tmp:
            out = tmp.read()
        assert out == '{\n"key": "value"\n}'

        # Test the inline option
        cli(inline_args=[temp_path, "--indent", "0", "-i"])
        with open(temp_path) as tmp:
            out = tmp.read()
        assert out == '{\n"key": "value"\n}'

    finally:
        # Clean up - delete the temporary file
        os.remove(temp_path)
        os.remove(tempout_path)

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
