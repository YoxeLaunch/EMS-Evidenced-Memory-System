"""Evaluador de promoción — criterio de hecho de la Fase 4
(`docs/03-ROADMAP.md`): un T2 con refuerzo suficiente y sin contradicción se
promueve solo; uno con contradicción activa se bloquea con el motivo
registrado; un dominio de alto riesgo nunca promueve sin confirmación humana.
"""
from __future__ import annotations

from memory.claims import MemoryClaim, Status, Tier
from memory.promotion import (
    DEFAULT_MIN_PROVENANCE_DIVERSITY, PromotionResult,
    StructuralPromotionEvaluator, promote_to_t3,
)
from memory.store import InMemoryClaimStore


def _t2_claim(subject: str, text: str, *, sources: list[str],
             agent_id: str = "a1") -> MemoryClaim:
    c = MemoryClaim.new_candidate(
        agent_id=agent_id, subject=subject, text=text,
        source_conversation_id=sources[0], confidence=0.6)
    c.source_conversation_ids = list(sources)
    c.reinforcement_count = len(sources)
    c.tier = Tier.T2
    return c


# -- promoción exitosa ------------------------------------------------------------------
def test_un_t2_con_refuerzo_y_procedencia_suficiente_se_promueve_solo():
    store = InMemoryClaimStore()
    claim = _t2_claim("cafe", "me gusta el cafe negro", sources=["c1", "c2", "c3"])
    store.add(claim)

    resultado = promote_to_t3(claim, store)

    assert resultado.approved is True
    assert resultado.claim.tier == Tier.T3
    assert store.get(claim.id).tier == Tier.T3


# -- bloqueos --------------------------------------------------------------------------
def test_solo_se_promueven_claims_t2():
    store = InMemoryClaimStore()
    t1 = _t2_claim("cafe", "me gusta el cafe", sources=["c1", "c2", "c3"])
    t1.tier = Tier.T1
    store.add(t1)

    resultado = promote_to_t3(t1, store)

    assert not resultado
    assert "solo se promueven claims T2" in resultado.reason
    assert store.get(t1.id).tier == Tier.T1


def test_refuerzo_insuficiente_bloquea_la_promocion():
    store = InMemoryClaimStore()
    claim = _t2_claim("cafe", "me gusta el cafe", sources=["c1", "c2"])
    claim.reinforcement_count = 2  # por debajo del umbral por defecto (3)
    store.add(claim)

    resultado = promote_to_t3(claim, store)

    assert not resultado
    assert "refuerzo insuficiente" in resultado.reason
    assert store.get(claim.id).tier == Tier.T2, "un rechazo no debe mutar el tier"


def test_procedencia_poco_diversa_bloquea_la_promocion():
    """Refuerzo suficiente pero todo desde UNA sola conversación de origen
    (ej. reinforcement_count inflado manualmente) no basta."""
    store = InMemoryClaimStore()
    claim = _t2_claim("cafe", "me gusta el cafe", sources=["c1"])
    claim.reinforcement_count = 5
    store.add(claim)

    resultado = promote_to_t3(claim, store)

    assert not resultado
    assert "procedencia poco diversa" in resultado.reason


def test_contradiccion_con_t3_activo_bloquea_la_promocion():
    store = InMemoryClaimStore()
    t3_existente = _t2_claim("dieta", "como carne todos los dias", sources=["c1", "c2", "c3"])
    t3_existente.tier = Tier.T3
    store.add(t3_existente)

    candidato = _t2_claim("dieta", "no como carne todos los dias", sources=["c4", "c5", "c6"])
    store.add(candidato)

    resultado = promote_to_t3(candidato, store)

    assert not resultado
    assert t3_existente.id in resultado.reason
    assert store.get(candidato.id).tier == Tier.T2


def test_un_claim_no_activo_no_se_promueve():
    store = InMemoryClaimStore()
    claim = _t2_claim("cafe", "me gusta el cafe", sources=["c1", "c2", "c3"])
    claim.status = Status.SUPERSEDED
    store.add(claim)

    resultado = promote_to_t3(claim, store)

    assert not resultado
    assert "no está activo" in resultado.reason


# -- dominios de alto riesgo --------------------------------------------------------------
def test_dominio_de_alto_riesgo_no_promueve_sin_confirmacion_humana():
    store = InMemoryClaimStore()
    claim = _t2_claim("salud", "soy alergico a la penicilina", sources=["c1", "c2", "c3"])
    store.add(claim)

    resultado = promote_to_t3(claim, store, high_risk=True)

    assert not resultado
    assert "confirmación humana" in resultado.reason
    assert store.get(claim.id).tier == Tier.T2


def test_dominio_de_alto_riesgo_promueve_con_confirmacion_humana():
    store = InMemoryClaimStore()
    claim = _t2_claim("salud", "soy alergico a la penicilina", sources=["c1", "c2", "c3"])
    store.add(claim)

    resultado = promote_to_t3(claim, store, high_risk=True, human_confirmed=True)

    assert resultado.approved is True
    assert resultado.claim.tier == Tier.T3


def test_confirmacion_humana_no_rescata_una_inconsistencia_estructural():
    """La confirmación humana se suma al evaluador automático, no lo reemplaza."""
    store = InMemoryClaimStore()
    claim = _t2_claim("salud", "soy alergico a la penicilina", sources=["c1"])
    claim.reinforcement_count = 1  # refuerzo insuficiente
    store.add(claim)

    resultado = promote_to_t3(claim, store, high_risk=True, human_confirmed=True)

    assert not resultado
    assert "refuerzo insuficiente" in resultado.reason


# -- evaluador estructural aislado ------------------------------------------------------------
def test_el_evaluador_estructural_es_configurable():
    store = InMemoryClaimStore()
    claim = _t2_claim("cafe", "me gusta el cafe", sources=["c1", "c2"])
    store.add(claim)

    evaluador_laxo = StructuralPromotionEvaluator(min_reinforcement=2, min_provenance_diversity=2)
    resultado = evaluador_laxo.evaluate(claim, store)

    assert resultado.approved is True
