from pathlib import Path

import pytest

mypy_api = pytest.importorskip("mypy.api")

SNIPPET_TEMPLATE = """\
from json_repair import JSONReturnType
from json_repair.json_repair import repair_json

{assignment}
"""


def _run_type_check(tmp_path: Path, assignment: str) -> tuple[int, str, str]:
    snippet = tmp_path / "typecheck_repair_json.py"
    snippet.write_text(SNIPPET_TEMPLATE.format(assignment=assignment), encoding="utf-8")
    stdout, stderr, exit_code = mypy_api.run([str(snippet)])
    return exit_code, stdout, stderr


@pytest.mark.parametrize(
    "assignment",
    [
        'text: str = repair_json("test")',
        'text: str = repair_json("test", return_objects=False)',
        'value: JSONReturnType = repair_json("test", return_objects=True)',
        'logged: tuple[JSONReturnType, list[dict[str, str]]] = repair_json("test", logging=True)',
        'text: str = repair_json("test", logging=False)',
        'logged: tuple[JSONReturnType, list[dict[str, str]]] = repair_json("test", return_objects=True, logging=True)',
    ],
)
def test_repair_json_type_inference(tmp_path: Path, assignment: str) -> None:
    exit_code, stdout, stderr = _run_type_check(tmp_path, assignment)

    assert exit_code == 0, stderr or stdout
