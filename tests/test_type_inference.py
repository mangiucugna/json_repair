from pathlib import Path

from mypy import api as mypy_api

SNIPPET = """\
from json_repair import JSONReturnType
from json_repair.json_repair import repair_json

text_default: str = repair_json("test")
text_explicit: str = repair_json("test", return_objects=False)
value: JSONReturnType = repair_json("test", return_objects=True)
logged: tuple[JSONReturnType, list[dict[str, str]]] = repair_json("test", logging=True)
text_unlogged: str = repair_json("test", logging=False)
logged_objects: tuple[JSONReturnType, list[dict[str, str]]] = repair_json("test", return_objects=True, logging=True)
"""


def test_repair_json_type_inference(tmp_path: Path) -> None:
    snippet = tmp_path / "typecheck_repair_json.py"
    snippet.write_text(SNIPPET, encoding="utf-8")
    stdout, stderr, exit_code = mypy_api.run([str(snippet)])

    assert exit_code == 0, stderr or stdout
