"""Recuperación integrada — criterio de hecho de la Fase 5 (`docs/03-ROADMAP.md`):
una consulta real recupera claims de ambos niveles cuando existen, y la
respuesta distingue explícitamente su nivel de confianza.
"""
from __future__ import annotations

from memory.claims import MemoryClaim, Tier
from memory.retrieval import build_tiered_context
from memory.store import InMemoryClaimStore


def _claim(agent_id: str, subject: str, text: str, tier: Tier) -> MemoryClaim:
    c = MemoryClaim.new_candidate(
        agent_id=agent_id, subject=subject, text=text,
        source_conversation_id="c1", confidence=0.6)
    c.tier = tier
    return c


def test_recupera_claims_de_ambos_niveles_cuando_existen():
    store = InMemoryClaimStore()
    store.add(_claim("a1", "cafe", "me gusta el cafe negro sin azucar", Tier.T2))
    store.add(_claim("a1", "alergia", "soy alergico a la penicilina", Tier.T3))

    ctx = build_tiered_context(store, "cuentame sobre el cafe y la alergia", "a1")

    assert ctx.t2 and ctx.t3


def test_un_t2_se_etiqueta_como_confianza_media_y_un_t3_como_autoridad_plena():
    store = InMemoryClaimStore()
    store.add(_claim("a1", "cafe", "me gusta el cafe negro sin azucar", Tier.T2))
    store.add(_claim("a1", "alergia", "soy alergico a la penicilina", Tier.T3))

    ctx = build_tiered_context(store, "cafe negro sin azucar alergico penicilina", "a1")

    etiquetas = {e.confidence_label for e in ctx.evidence}
    assert "confianza_media" in etiquetas
    assert "autoridad_plena" in etiquetas


def test_un_t2_nunca_se_etiqueta_como_autoridad_plena():
    store = InMemoryClaimStore()
    store.add(_claim("a1", "cafe", "me gusta el cafe negro sin azucar", Tier.T2))

    ctx = build_tiered_context(store, "cafe negro sin azucar", "a1")

    assert all(e.tier == Tier.T2 for e in ctx.evidence)
    assert all(e.confidence_label == "confianza_media" for e in ctx.evidence)


def test_no_recupera_claims_de_otro_agente():
    store = InMemoryClaimStore()
    store.add(_claim("a1", "cafe", "me gusta el cafe negro sin azucar", Tier.T2))
    store.add(_claim("a2", "cafe", "me gusta el cafe negro sin azucar", Tier.T2))

    ctx = build_tiered_context(store, "cafe negro sin azucar", "a1")

    assert all(e.chunk.namespace == "a1" for e in ctx.evidence)


def test_un_claim_t1_no_se_recupera_nunca():
    """T1 no es citable como evidencia — solo T2/T3 (`docs/01-MEMORIA-NIVELADA.md`)."""
    store = InMemoryClaimStore()
    store.add(_claim("a1", "cafe", "me gusta el cafe negro sin azucar", Tier.T1))

    ctx = build_tiered_context(store, "cafe negro sin azucar", "a1")

    assert ctx.evidence == []


def test_sin_claims_activos_el_contexto_queda_vacio():
    store = InMemoryClaimStore()
    ctx = build_tiered_context(store, "cualquier cosa", "a1")
    assert ctx.evidence == []


def test_as_prompt_block_marca_visiblemente_el_nivel():
    store = InMemoryClaimStore()
    store.add(_claim("a1", "alergia", "soy alergico a la penicilina", Tier.T3))

    ctx = build_tiered_context(store, "alergico a la penicilina", "a1")
    bloque = ctx.as_prompt_block()

    assert "autoridad_plena" in bloque
    assert "soy alergico a la penicilina" in bloque
