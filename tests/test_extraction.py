"""Extracción determinista T0 → T1 — criterio de hecho de la Fase 2
(`docs/03-ROADMAP.md`): candidatos esperados a partir de marcadores
conocidos, y CERO candidatos alucinados por inferencia libre.
"""
from __future__ import annotations

from datetime import datetime, timezone

from memory.capture import ConversationRecord, Consent, Turn
from memory.claims import Tier
from memory.extraction import extract_candidates

_TS = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record(turns: list[tuple[str, str]], *, record_id: str = "conv-1") -> ConversationRecord:
    return ConversationRecord(
        id=record_id, agent_id="a1", user_id="user-1", started_at=_TS,
        turns=tuple(Turn(role, content, _TS) for role, content in turns),
        consent=Consent(True, "raw_conversation", "user-1", _TS),
    )


# -- cero candidatos alucinados (el criterio central de la fase) ------------------------
def test_una_pregunta_no_produce_candidato():
    record = _record([("user", "¿te gusta el café?")])
    assert extract_candidates(record) == []


def test_un_turno_del_asistente_nunca_produce_candidato():
    record = _record([("assistant", "tengo acceso a tu calendario")])
    assert extract_candidates(record) == []


def test_una_frase_sin_marcador_explicito_no_produce_candidato():
    record = _record([("user", "el clima estuvo raro esta semana")])
    assert extract_candidates(record) == []


def test_una_confirmacion_sin_afirmacion_previa_del_asistente_no_produce_candidato():
    record = _record([("user", "sí, correcto")])
    assert extract_candidates(record) == []


def test_una_confirmacion_a_una_pregunta_del_asistente_no_produce_candidato():
    """Confirmar 'sí' a una pregunta no es confirmar un hecho declarado."""
    record = _record([
        ("assistant", "¿quieres que programe la reunión para el lunes?"),
        ("user", "sí"),
    ])
    assert extract_candidates(record) == []


# -- corrección directa -----------------------------------------------------------------
def test_correccion_directa_produce_un_candidato():
    record = _record([("user", "en realidad, vivo en Santo Domingo")])
    [c] = extract_candidates(record)
    assert c.tier == Tier.T1
    assert c.text == "vivo en Santo Domingo"
    assert c.subject == "vivo"
    assert c.agent_id == "a1"
    assert c.source_conversation_ids == ["conv-1"]


def test_correccion_sin_contenido_no_produce_candidato():
    record = _record([("user", "corrijo:")])
    assert extract_candidates(record) == []


# -- confirmación explícita ---------------------------------------------------------------
def test_confirmacion_a_una_afirmacion_usa_el_texto_del_asistente():
    record = _record([
        ("assistant", "así que no comes carne los martes"),
        ("user", "sí, correcto"),
    ])
    [c] = extract_candidates(record)
    assert c.text == "así que no comes carne los martes"
    assert c.confidence > 0


# -- declaración en primera persona --------------------------------------------------------
def test_declaracion_en_primera_persona_produce_un_candidato():
    record = _record([("user", "no como carne los martes")])
    [c] = extract_candidates(record)
    assert c.text == "no como carne los martes"
    assert c.tier == Tier.T1


def test_varias_oraciones_en_un_turno_producen_varios_candidatos():
    record = _record([("user", "tengo alergia a los mariscos. me gusta el café negro.")])
    candidatos = extract_candidates(record)
    assert len(candidatos) == 2
    assert {c.subject for c in candidatos} == {"alergia", "cafe"}


def test_declaracion_negativa_en_primera_persona():
    record = _record([("user", "no tengo mascotas")])
    [c] = extract_candidates(record)
    assert c.text == "no tengo mascotas"


def test_cada_candidato_tiene_proveniencia_a_t0():
    record = _record([("user", "soy programador")], record_id="conv-especifico")
    [c] = extract_candidates(record)
    assert c.source_conversation_ids == ["conv-especifico"]
    assert c.reinforcement_count == 1
    assert c.first_seen_at and c.last_reinforced_at
