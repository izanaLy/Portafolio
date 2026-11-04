import json

from ticket_triage.cli import main


def test_triage_table_output(capsys):
    assert main(["triage"]) == 0
    out = capsys.readouterr().out
    assert "TKT-0001" in out and "TKT-0024" in out
    assert "inmediata" in out
    assert "revisión manual" in out


def test_triage_explain_adds_reasons(capsys):
    assert main(["triage", "--explain"]) == 0
    out = capsys.readouterr().out
    assert "    - categoría" in out


def test_triage_json_output_is_valid(capsys):
    assert main(["triage", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 24
    assert {"ticket_id", "category", "priority", "escalation_level", "reasons"} <= set(payload[0])


def test_summary_output(capsys):
    assert main(["summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["total"]["tickets"] == 24
    assert sum(summary["por_prioridad"].values()) == 24


def test_missing_file_returns_error_code(capsys, tmp_path):
    assert main(["triage", str(tmp_path / "no_existe.json")]) == 2
    assert "Error" in capsys.readouterr().err


def test_non_synthetic_file_is_rejected(capsys, tmp_path):
    path = tmp_path / "real.json"
    path.write_text(json.dumps({"meta": {}, "tickets": []}), encoding="utf-8")
    assert main(["triage", str(path)]) == 2
    assert "synthetic" in capsys.readouterr().err


def test_invalid_json_returns_error_code(capsys, tmp_path):
    path = tmp_path / "roto.json"
    path.write_text("{no es json", encoding="utf-8")
    assert main(["summary", str(path)]) == 2


# --- entradas estructuralmente inválidas: código 2, sin trazas ------------------

import pytest  # noqa: E402

GOOD_TICKET = {"id": "X", "title": "t", "description": "d"}

INVALID_PAYLOADS = {
    "meta_null": {"meta": None, "tickets": []},
    "meta_lista": {"meta": [], "tickets": []},
    "meta_texto": {"meta": "x", "tickets": []},
    "meta_ausente": {"tickets": []},
    "tickets_null": {"meta": {"synthetic": True}, "tickets": None},
    "tickets_objeto": {"meta": {"synthetic": True}, "tickets": {"a": 1}},
    "item_texto": {"meta": {"synthetic": True}, "tickets": ["hola"]},
    "item_null": {"meta": {"synthetic": True}, "tickets": [None]},
    "expected_lista": {"meta": {"synthetic": True}, "tickets": [dict(GOOD_TICKET, expected=["a"])]},
    "expected_null": {"meta": {"synthetic": True}, "tickets": [dict(GOOD_TICKET, expected=None)]},
    "expected_clave_desconocida": {
        "meta": {"synthetic": True},
        "tickets": [dict(GOOD_TICKET, expected={"foo": "bar"})],
    },
    "expected_valor_no_texto": {
        "meta": {"synthetic": True},
        "tickets": [dict(GOOD_TICKET, expected={"priority": 1})],
    },
    "raiz_null": None,
    "raiz_lista": [],
}


@pytest.mark.parametrize("command", [["triage"], ["triage", "--format", "json"], ["summary"]])
@pytest.mark.parametrize("name", sorted(INVALID_PAYLOADS))
def test_structurally_invalid_json_exits_with_code_2(capsys, tmp_path, name, command):
    path = tmp_path / "invalido.json"
    path.write_text(json.dumps(INVALID_PAYLOADS[name]), encoding="utf-8")
    assert main(command + [str(path)]) == 2  # no debe propagar excepciones
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error: ")
    assert "Traceback" not in captured.err


def test_non_utf8_file_exits_with_code_2(capsys, tmp_path):
    path = tmp_path / "binario.json"
    path.write_bytes(b"\xff\xfe\x00\x01")
    assert main(["triage", str(path)]) == 2
    assert capsys.readouterr().err.startswith("Error: ")


def test_directory_instead_of_file_exits_with_code_2(capsys, tmp_path):
    assert main(["triage", str(tmp_path)]) == 2
    assert capsys.readouterr().err.startswith("Error: ")


def test_error_message_points_to_the_problem(capsys, tmp_path):
    path = tmp_path / "tickets.json"
    path.write_text(json.dumps({"meta": None, "tickets": []}), encoding="utf-8")
    main(["triage", str(path)])
    assert "'meta' debe ser un objeto JSON, no null" in capsys.readouterr().err
