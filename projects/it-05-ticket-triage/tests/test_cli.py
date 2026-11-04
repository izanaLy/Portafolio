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
