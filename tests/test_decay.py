"""Caducidad — criterio de hecho de la Fase 6 (`docs/03-ROADMAP.md`): un
claim sin refuerzo reciente deja de recuperarse como evidencia activa pero
conserva su historial.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from memory.claims import MemoryClaim, Status, Tier
from memory.decay import DEFAULT_EXPIRY_THRESHOLD, effective_confidence, expire_stale_claims
from memory.reinforcement import reinforce_or_create
from memory.store import InMemoryClaimStore


def _claim(*, confidence: float, half_life_days: int, dias_desde_refuerzo: float) -> MemoryClaim:
    c = MemoryClaim.new_candidate(
        agent_id="a1", subject="cafe", text="me gusta el cafe negro",
        source_conversation_id="c1", confidence=confidence,
        decay_half_life_days=half_life_days)
    entonces = datetime.now(timezone.utc) - timedelta(days=dias_desde_refuerzo)
    c.last_reinforced_at = entonces.isoformat(timespec="seconds")
    return c


# -- confianza efectiva ---------------------------------------------------------------
def test_sin_tiempo_transcurrido_la_confianza_efectiva_es_la_original():
    c = _claim(confidence=0.8, half_life_days=30, dias_desde_refuerzo=0)
    assert abs(effective_confidence(c) - 0.8) < 1e-5


def test_a_una_vida_media_la_confianza_efectiva_es_la_mitad():
    c = _claim(confidence=0.8, half_life_days=30, dias_desde_refuerzo=30)
    assert abs(effective_confidence(c) - 0.4) < 1e-6


def test_a_dos_vidas_medias_la_confianza_cae_a_un_cuarto():
    c = _claim(confidence=0.8, half_life_days=30, dias_desde_refuerzo=60)
    assert abs(effective_confidence(c) - 0.2) < 1e-6


def test_vida_media_no_positiva_significa_indefinida_no_decae():
    c = _claim(confidence=0.8, half_life_days=0, dias_desde_refuerzo=1000)
    assert effective_confidence(c) == 0.8


# -- expiración -------------------------------------------------------------------------
def test_un_claim_bajo_el_umbral_pasa_a_expired():
    store = InMemoryClaimStore()
    viejo = _claim(confidence=0.5, half_life_days=10, dias_desde_refuerzo=200)  # ~20 vidas medias
    store.add(viejo)

    expirados = expire_stale_claims(store)

    assert viejo in expirados
    assert viejo.status == Status.EXPIRED
    assert store.get(viejo.id) is viejo, "sigue en el store, solo que no activo"


def test_un_claim_reciente_no_expira():
    store = InMemoryClaimStore()
    reciente = _claim(confidence=0.5, half_life_days=180, dias_desde_refuerzo=1)
    store.add(reciente)

    expirados = expire_stale_claims(store)

    assert expirados == []
    assert reciente.status == Status.ACTIVE


def test_expirar_conserva_la_proveniencia_completa():
    store = InMemoryClaimStore()
    viejo = _claim(confidence=0.5, half_life_days=10, dias_desde_refuerzo=200)
    texto_original, sujeto_original = viejo.text, viejo.subject
    store.add(viejo)

    expire_stale_claims(store)

    assert viejo.text == texto_original
    assert viejo.subject == sujeto_original
    assert viejo.source_conversation_ids == ["c1"]


def test_un_claim_expirado_no_es_evidencia_activa():
    store = InMemoryClaimStore()
    viejo = _claim(confidence=0.5, half_life_days=10, dias_desde_refuerzo=200)
    viejo.tier = Tier.T2
    store.add(viejo)

    expire_stale_claims(store)

    assert viejo not in store.active(agent_id="a1")


def test_el_umbral_por_defecto_esta_definido_y_es_positivo():
    assert 0 < DEFAULT_EXPIRY_THRESHOLD < 1


# -- revival por refuerzo nuevo (integración con Fase 3) ---------------------------------
def test_un_refuerzo_nuevo_revive_un_claim_expirado():
    store = InMemoryClaimStore()
    expirado = MemoryClaim.new_candidate(
        agent_id="a1", subject="cafe", text="me gusta el cafe negro",
        source_conversation_id="c1", confidence=0.5)
    expirado.status = Status.EXPIRED
    store.add(expirado)

    candidato = MemoryClaim.new_candidate(
        agent_id="a1", subject="cafe", text="me gusta el cafe negro",
        source_conversation_id="c2", confidence=0.5)
    resultado = reinforce_or_create(candidato, store)

    assert resultado.id == expirado.id
    assert resultado.status == Status.ACTIVE
    assert resultado.reinforcement_count == 2
    assert set(resultado.source_conversation_ids) == {"c1", "c2"}


def test_sin_revive_expired_no_se_reactiva_un_claim_caducado():
    store = InMemoryClaimStore()
    expirado = MemoryClaim.new_candidate(
        agent_id="a1", subject="cafe", text="me gusta el cafe negro",
        source_conversation_id="c1", confidence=0.5)
    expirado.status = Status.EXPIRED
    store.add(expirado)

    candidato = MemoryClaim.new_candidate(
        agent_id="a1", subject="cafe", text="me gusta el cafe negro",
        source_conversation_id="c2", confidence=0.5)
    resultado = reinforce_or_create(candidato, store, revive_expired=False)

    assert resultado.id == candidato.id
    assert expirado.status == Status.EXPIRED, "no debe tocarse si revive_expired=False"
