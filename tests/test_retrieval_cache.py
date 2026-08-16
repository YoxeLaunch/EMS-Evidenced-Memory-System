"""Fase A2 — índice de recuperación con invalidación por snapshot.

Criterio de hecho: entre escrituras, consultar no reconstruye; una
escritura que cambia el corpus (refuerzo, promoción, sucesión, expiración)
invalida. Y paridad: mismos resultados que `build_tiered_context`.
"""
from __future__ import annotations

from memory.claims import MemoryClaim, Tier
from memory.promotion import promote_to_t3
from memory.reinforcement import reinforce_or_create
from memory.retrieval import CachedTieredRetriever, build_tiered_context
from memory.store import InMemoryClaimStore


def _candidato(source: str) -> MemoryClaim:
    return MemoryClaim.new_candidate(
        agent_id="a1", subject="cafe", text="me gusta el cafe negro",
        source_conversation_id=source, confidence=0.5)


def _store_con_t2() -> InMemoryClaimStore:
    store = InMemoryClaimStore()
    for conv in ("conv-1", "conv-2", "conv-3"):
        reinforce_or_create(_candidato(conv), store)
    return store


def test_paridad_construida_una_vez_mismos_resultados_que_sin_cache():
    store = _store_con_t2()
    retriever = CachedTieredRetriever(store)

    cached = retriever.context_for("que le gusta tomar", "a1")
    directo = build_tiered_context(store, "que le gusta tomar", "a1")

    assert [e.chunk.chunk_id for e in cached.evidence] == \
        [e.chunk.chunk_id for e in directo.evidence]
    assert all(e.tier == Tier.T2 for e in cached.evidence)


def test_consultas_sin_escrituras_no_reconstruyen():
    store = _store_con_t2()
    retriever = CachedTieredRetriever(store)

    retriever.context_for("cafe", "a1")
    retriever.context_for("te", "a1")
    retriever.context_for("cafe negro", "a1")

    assert retriever.builds == 1, "misma huella, mismo índice"


def test_una_escritura_invalida_y_la_siguiente_consulta_reconstruye():
    store = _store_con_t2()
    retriever = CachedTieredRetriever(store)
    retriever.context_for("cafe", "a1")
    assert retriever.builds == 1

    reinforce_or_create(_candidato("conv-4"), store)  # corpus cambia
    retriever.context_for("cafe", "a1")

    assert retriever.builds == 2
    [claim] = store.active(agent_id="a1", tier=Tier.T2)
    assert claim.reinforcement_count == 4


def test_la_promocion_invalida_por_cambio_de_tier():
    store = _store_con_t2()
    retriever = CachedTieredRetriever(store)
    retriever.context_for("cafe", "a1")

    [claim] = store.active(agent_id="a1", tier=Tier.T2)
    promote_to_t3(claim, store)
    ctx = retriever.context_for("cafe", "a1")

    assert retriever.builds == 2, "tier cambia la huella aunque no cambie el texto"
    assert ctx.t3 and not ctx.t2, "y el resultado refleja el nuevo nivel"


def test_agentes_distintos_no_comparten_cache():
    store = _store_con_t2()
    for conv in ("conv-x", "conv-y", "conv-z"):  # a2 también llega a T2:
        reinforce_or_create(MemoryClaim.new_candidate(  # T1 no se indexa
            agent_id="a2", subject="cafe", text="me gusta el cafe con leche",
            source_conversation_id=conv, confidence=0.5), store)
    retriever = CachedTieredRetriever(store)

    retriever.context_for("cafe", "a1")
    retriever.context_for("cafe", "a2")

    assert retriever.builds == 2, "un índice por agente (parcela de conocimiento)"


def test_agente_sin_claims_devuelve_contexto_vacio_sin_construir():
    retriever = CachedTieredRetriever(InMemoryClaimStore())
    ctx = retriever.context_for("lo que sea", "nadie")
    assert ctx.evidence == [] and retriever.builds == 0
