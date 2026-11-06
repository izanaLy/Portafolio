from ticket_triage import Ticket, summarize, triage, triage_all


def make(**overrides):
    data = {"id": "T-1", "title": "Titulo", "description": "Descripcion"}
    data.update(overrides)
    return Ticket.from_dict(data)


def test_triage_result_is_explainable():
    result = triage(make(title="VPN caída", description="Nadie puede conectarse. Urgente.", affected_users=12))
    assert result.category == "red"
    assert result.reasons, "cada resultado debe incluir razones"
    assert any("vpn" in r for r in result.reasons)
    assert any("matriz" in r for r in result.reasons)


def test_p1_is_escalated_immediately():
    result = triage(
        make(title="Servidor caído", description="Producción detenida.", affected_users=50)
    )
    assert result.priority.label == "P1"
    assert result.escalation_level == "nivel_3"
    assert result.escalate and result.escalate_immediately


def test_level_1_ticket_is_not_escalated():
    result = triage(make(title="Olvidé mi contraseña", description="Necesito restablecerla."))
    assert result.escalation_level == "nivel_1"
    assert not result.escalate
    assert not result.escalate_immediately


def test_uncategorized_ticket_requests_manual_review():
    result = triage(make(title="Necesito ayuda", description="Algo no funciona."))
    assert result.category == "otros"
    assert result.needs_manual_review
    assert any("manual" in r for r in result.reasons)


def test_triage_is_deterministic():
    ticket = make(title="Impresora sin tóner", description="No imprime.", affected_users=3)
    assert triage(ticket) == triage(ticket)


def test_to_dict_is_json_friendly():
    import json

    result = triage(make(title="Laptop no enciende", description="No puedo trabajar."))
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["category"] == "hardware"
    assert payload["urgency"] == "alto"
    assert payload["priority"] == "P3"


def test_summarize_counts():
    tickets = [
        make(id="A", title="VPN caída", description="Urgente", affected_users=20),
        make(id="B", title="Contraseña olvidada", description="Restablecer"),
        make(id="C", title="Contraseña bloqueada", description="Restablecer"),
    ]
    summary = summarize(triage_all(tickets))
    assert summary["total"] == {"tickets": 3}
    assert summary["por_categoria"] == {"cuenta_acceso": 2, "red": 1}
    assert sum(summary["por_prioridad"].values()) == 3
    assert sum(summary["por_escalacion"].values()) == 3


# --- seguridad P1 y política conservadora (revisión PR #2) ---------------------


def test_security_p1_end_to_end_uses_independent_channel():
    result = triage(
        make(
            title="Posible ransomware",
            description="Archivos cifrados y nota de rescate. Urgente.",
            affected_users=3,
        )
    )
    assert result.category == "seguridad"
    assert result.priority.label == "P1"
    assert result.escalation_level == "seguridad"
    assert result.escalate is True
    assert result.escalate_immediately is True
    assert result.escalation_team == "Equipo de seguridad"
    reasons = " ".join(result.reasons)
    assert "independiente de la jerarquía nivel 1/2/3" in reasons
    assert "atención inmediata por el canal de seguridad" in reasons


def test_security_below_p1_is_escalated_but_not_immediately():
    result = triage(
        make(title="Posible phishing", description="Correo sospechoso, no hice clic.")
    )
    assert result.category == "seguridad"
    assert result.priority.label == "P2"  # piso de seguridad
    assert result.escalation_level == "seguridad"
    assert result.escalate is True
    assert result.escalate_immediately is False


def test_ransomware_with_workaround_remains_p1():
    base = dict(
        title="Ransomware en contabilidad",
        description="Archivos cifrados. Desconectamos el equipo de la red.",
        affected_users=3,
    )
    sin = triage(make(**base))
    con = triage(make(workaround_available=True, **base))
    assert con.urgency == sin.urgency
    assert con.priority == sin.priority
    assert con.priority.label == "P1"
    assert con.escalate_immediately is True
    assert any("señal crítica de seguridad" in r for r in con.reasons)


def test_critical_signal_urgency_is_not_lowered_by_workaround_end_to_end():
    base = dict(title="Acceso no autorizado", description="Intentos de acceso no autorizado a una cuenta.")
    sin = triage(make(**base))
    con = triage(make(workaround_available=True, **base))
    assert con.urgency == sin.urgency
    assert con.urgency.label == "medio"
    assert con.priority == sin.priority


def test_non_critical_security_ticket_still_gets_workaround_reduction():
    base = dict(title="Posible phishing", description="Correo sospechoso, no hice clic.")
    sin = triage(make(**base))
    con = triage(make(workaround_available=True, **base))
    assert sin.urgency.label == "medio"
    assert con.urgency.label == "bajo"
    assert con.category == "seguridad" and con.priority.label == "P2"  # el piso sigue vigente


def test_security_category_always_maps_to_security_channel_on_dataset():
    from ticket_triage import load_dataset

    for ticket in load_dataset().tickets:
        result = triage(ticket)
        assert (result.category == "seguridad") == (result.escalation_level == "seguridad")
