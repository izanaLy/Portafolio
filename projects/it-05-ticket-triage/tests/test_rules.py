import itertools

import pytest

from ticket_triage import rules
from ticket_triage.models import Level, Priority


# --- normalización y coincidencias ---------------------------------------------


def test_normalize_lowercases_and_strips_accents_and_punctuation():
    assert rules.normalize("¡La VPN está CAÍDA! (Wi-Fi)") == "la vpn esta caida wi fi"


def test_keywords_match_whole_words_only():
    text = rules.normalize("Necesito redactar un informe")
    assert rules.find_matches(text, ["red"]) == []


def test_keywords_accept_simple_plurals():
    text = rules.normalize("Las impresoras no funcionan")
    assert rules.find_matches(text, ["impresora"]) == ["impresora"]


# --- categoría ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("La VPN no conecta desde casa", "red"),
        ("Olvidé mi contraseña", "cuenta_acceso"),
        ("Mi laptop no enciende", "hardware"),
        ("Necesito instalar Excel", "software"),
        ("Outlook no sincroniza el buzón", "correo_colaboracion"),
        ("La impresora no tiene tóner", "impresion"),
        ("El servidor de la base de datos está lento", "infraestructura"),
        ("Posible phishing en un correo", "seguridad"),
    ],
)
def test_category_examples(text, expected):
    category, matches = rules.classify_category(rules.normalize(text))
    assert category == expected
    assert matches  # siempre hay evidencia explicable


def test_category_falls_back_to_otros_without_matches():
    category, matches = rules.classify_category(rules.normalize("Algo raro pasó ayer"))
    assert category == rules.FALLBACK_CATEGORY
    assert matches == []


def test_security_signal_beats_other_categories():
    # «contraseña» + «cuenta» puntúan 4 en cuenta_acceso, pero seguridad pesa 5.
    text = rules.normalize("Acceso no autorizado a mi cuenta, cambié la contraseña")
    assert rules.classify_category(text)[0] == "seguridad"


def test_product_name_beats_generic_symptoms():
    text = rules.normalize("Teams se cierra y no abre")
    assert rules.classify_category(text)[0] == "correo_colaboracion"


def test_ties_are_resolved_by_category_order():
    # 'servidor' (infraestructura, 3) vs 'vpn' (red, 3): gana infraestructura.
    text = rules.normalize("servidor vpn")
    assert rules.classify_category(text)[0] == "infraestructura"


# --- impacto --------------------------------------------------------------------


@pytest.mark.parametrize(
    "users, expected",
    [(1, Level.LOW), (2, Level.MEDIUM), (9, Level.MEDIUM), (10, Level.HIGH), (500, Level.HIGH)],
)
def test_impact_by_affected_users(users, expected):
    level, _ = rules.assess_impact("texto sin pistas", users, "software")
    assert level == expected


def test_impact_keywords_raise_level():
    high, _ = rules.assess_impact(rules.normalize("Cayó el sistema de producción"), 1, "software")
    medium, _ = rules.assess_impact(rules.normalize("Afecta al departamento de ventas"), 1, "software")
    assert high == Level.HIGH
    assert medium == Level.MEDIUM


@pytest.mark.parametrize("category", ["infraestructura", "seguridad"])
def test_category_impact_floor(category):
    level, reasons = rules.assess_impact("texto sin pistas", 1, category)
    assert level == Level.MEDIUM
    assert any(category in r for r in reasons)


def test_impact_takes_the_maximum_of_all_rules():
    level, _ = rules.assess_impact(rules.normalize("ransomware"), 1, "seguridad")
    assert level == Level.HIGH


# --- urgencia -------------------------------------------------------------------


def test_urgency_defaults_to_medium():
    level, _ = rules.assess_urgency(rules.normalize("La pantalla se ve rara"), None)
    assert level == Level.MEDIUM


def test_urgency_high_keywords():
    level, _ = rules.assess_urgency(rules.normalize("No puedo trabajar, es crítico"), None)
    assert level == Level.HIGH


def test_urgency_low_keywords():
    level, _ = rules.assess_urgency(rules.normalize("Es una sugerencia, sin prisa"), None)
    assert level == Level.LOW


def test_negated_urgent_is_not_high():
    level, _ = rules.assess_urgency(rules.normalize("Cuando pueda, no es urgente"), None)
    assert level == Level.LOW


def test_real_urgency_still_wins_next_to_a_low_phrase():
    level, _ = rules.assess_urgency(
        rules.normalize("Es una consulta pero el servicio está caído"), None
    )
    assert level == Level.HIGH


def test_workaround_lowers_urgency_one_level_but_not_below_low():
    text = rules.normalize("Urgente")
    assert rules.assess_urgency(text, True)[0] == Level.MEDIUM
    assert rules.assess_urgency(text, False)[0] == Level.HIGH
    assert rules.assess_urgency(rules.normalize("sin prisa"), True)[0] == Level.LOW


# --- prioridad ------------------------------------------------------------------


def test_priority_matrix_is_complete():
    pairs = set(itertools.product(Level, Level))
    assert set(rules.PRIORITY_MATRIX) == pairs


def test_priority_matrix_is_monotonic():
    """Subir impacto o urgencia nunca debe empeorar (aumentar el número de) la prioridad."""
    for impact, urgency in itertools.product(Level, Level):
        base = rules.PRIORITY_MATRIX[(impact, urgency)]
        if impact < Level.HIGH:
            assert rules.PRIORITY_MATRIX[(Level(impact + 1), urgency)] <= base
        if urgency < Level.HIGH:
            assert rules.PRIORITY_MATRIX[(impact, Level(urgency + 1))] <= base


def test_priority_extremes():
    assert rules.compute_priority(Level.HIGH, Level.HIGH, "red")[0] == Priority.P1
    assert rules.compute_priority(Level.LOW, Level.LOW, "red")[0] == Priority.P4


def test_security_priority_floor():
    priority, reasons = rules.compute_priority(Level.LOW, Level.LOW, "seguridad")
    assert priority == Priority.P2
    assert any("seguridad" in r for r in reasons)


def test_security_floor_does_not_lower_p1():
    assert rules.compute_priority(Level.HIGH, Level.HIGH, "seguridad")[0] == Priority.P1


# --- escalación -----------------------------------------------------------------


@pytest.mark.parametrize(
    "category, priority, expected",
    [
        ("seguridad", Priority.P4, rules.SECURITY),
        ("seguridad", Priority.P1, rules.SECURITY),
        ("red", Priority.P1, rules.LEVEL_3),
        ("hardware", Priority.P2, rules.LEVEL_2),
        ("infraestructura", Priority.P3, rules.LEVEL_2),
        ("infraestructura", Priority.P4, rules.LEVEL_2),
        ("hardware", Priority.P3, rules.LEVEL_1),
        ("otros", Priority.P4, rules.LEVEL_1),
    ],
)
def test_escalation_rules(category, priority, expected):
    level, reasons = rules.decide_escalation(category, priority)
    assert level == expected
    assert reasons


# --- política conservadora: señales críticas de seguridad (revisión PR #2) -----


@pytest.mark.parametrize("signal", rules.CRITICAL_SECURITY_SIGNALS)
def test_workaround_does_not_lower_urgency_for_critical_security_signals(signal):
    text = rules.normalize(f"Se detecta {signal} en un equipo")
    without, _ = rules.assess_urgency(text, None)
    with_workaround, reasons = rules.assess_urgency(text, True)
    assert with_workaround == without
    assert any("señal crítica de seguridad" in r for r in reasons)


def test_ransomware_with_workaround_stays_high_urgency():
    text = rules.normalize("Ransomware en el equipo, ya lo desconectamos de la red")
    assert rules.assess_urgency(text, True)[0] == Level.HIGH


def test_critical_signal_exception_is_not_universal():
    """El phishing no es una señal crítica: la alternativa temporal sí baja la urgencia."""
    text = rules.normalize("Posible phishing, no hice clic")
    assert "phishing" not in rules.CRITICAL_SECURITY_SIGNALS
    assert rules.assess_urgency(text, None)[0] == Level.MEDIUM
    assert rules.assess_urgency(text, True)[0] == Level.LOW


def test_workaround_still_lowers_urgency_outside_security():
    text = rules.normalize("La impresora no imprime")
    assert rules.assess_urgency(text, True)[0] == Level.LOW


def test_critical_signals_are_security_keywords():
    """Toda señal crítica debe clasificar el ticket como seguridad."""
    assert set(rules.CRITICAL_SECURITY_SIGNALS) <= set(rules.CATEGORY_KEYWORDS["seguridad"])


def test_workaround_false_does_not_change_urgency_for_critical_signals():
    text = rules.normalize("Fuga de datos detectada")
    assert rules.assess_urgency(text, False)[0] == rules.assess_urgency(text, None)[0]


# --- canal de seguridad independiente de la jerarquía 1/2/3 --------------------


def test_security_p1_goes_to_security_channel_and_explains_it():
    level, reasons = rules.decide_escalation("seguridad", Priority.P1)
    assert level == rules.SECURITY
    joined = " ".join(reasons)
    assert "independiente de la jerarquía nivel 1/2/3" in joined
    assert "P1" in joined and "inmediata" in joined


@pytest.mark.parametrize("priority", [Priority.P2, Priority.P3, Priority.P4])
def test_security_below_p1_has_no_immediate_reason(priority):
    level, reasons = rules.decide_escalation("seguridad", priority)
    assert level == rules.SECURITY
    assert "independiente de la jerarquía nivel 1/2/3" in " ".join(reasons)
    assert "inmediata" not in " ".join(reasons)


def test_security_is_not_part_of_the_numbered_hierarchy():
    assert rules.SECURITY not in (rules.LEVEL_1, rules.LEVEL_2, rules.LEVEL_3)


# --- parámetros visibles y editables -------------------------------------------


def test_visible_parameters_have_the_documented_values():
    assert rules.USERS_FOR_MEDIUM_IMPACT == 2
    assert rules.USERS_FOR_HIGH_IMPACT == 10
    assert rules.SECURITY_PRIORITY_FLOOR == Priority.P2
    assert rules.CATEGORY_MIN_ESCALATION == {"infraestructura": rules.LEVEL_2}
    assert rules.CATEGORY_IMPACT_FLOOR == {
        "infraestructura": Level.MEDIUM,
        "seguridad": Level.MEDIUM,
    }


def test_category_min_escalation_is_applied_and_explained():
    level, reasons = rules.decide_escalation("infraestructura", Priority.P4)
    assert level == rules.LEVEL_2
    assert any("infraestructura" in r for r in reasons)


def test_category_min_escalation_does_not_lower_higher_levels():
    assert rules.decide_escalation("infraestructura", Priority.P1)[0] == rules.LEVEL_3
