"""Contrato del store de claims — Fase A de `docs/04-PLAN-MEJORAS.md`.

Define el comportamiento que CUALQUIER backend de `MemoryClaim` debe cumplir
(hoy `InMemoryClaimStore`; `SqliteClaimStore` cuando se decida [P-01]). Un
backend nuevo se certifica añadiendo su fábrica a `BACKENDS`: el resto de la
suite no cambia. Es lo que permite desarrollar la persistencia sin tocar el
pipeline de memoria nivelada — mismo espíritu del docstring de
`memory/store.py`: "persistencia real es sustituir esta clase".
"""
from __future__ import annotations

import pytest

from memory.claims import MemoryClaim, Status, Tier
from memory.store import InMemoryClaimStore

#: Cada entrada: (fábrica de store). Una fábrica devuelve un store vacío.
BACKENDS = [
    pytest.param(InMemoryClaimStore, id="in-memory"),
]


@pytest.fixture(params=BACKENDS)
def store(request) -> InMemoryClaimStore:
    return request.param()


def _claim(subject: str, *, text: str | None = None, agent_id: str = "a1",
           source: str = "conv-1") -> MemoryClaim:
    return MemoryClaim.new_candidate(
        agent_id=agent_id, subject=subject, text=text or f"declaracion sobre {subject}",
        source_conversation_id=source, confidence=0.5)


# -- escritura y lectura ----------------------------------------------------------------
def test_add_y_get_preservan_todos_los_campos(store):
    claim = _claim("cafe", text="me gusta el cafe negro")
    store.add(claim)

    leido = store.get(claim.id)
    assert leido is claim or (
        leido.id == claim.id and leido.text == claim.text
        and leido.subject == claim.subject and leido.agent_id == claim.agent_id
        and leido.tier == claim.tier and leido.status == claim.status
        and leido.source_conversation_ids == claim.source_conversation_ids
        and leido.supersedes == claim.supersedes
        and leido.superseded_by == claim.superseded_by
        and leido.decay_half_life_days == claim.decay_half_life_days
    )


def test_get_de_id_desconocido_devuelve_none(store):
    assert store.get("inexistente") is None


def test_add_dos_veces_con_el_mismo_id_es_upsert(store):
    """El mismo claim mutado (refuerzo, ascenso, sucesión) se re-añade bajo
    su id: la última escritura gana, sin duplicados."""
    claim = _claim("cafe", text="me gusta el cafe negro")
    store.add(claim)
    claim.reinforcement_count = 2
    store.add(claim)

    assert len(store.all()) == 1
    assert store.get(claim.id).reinforcement_count == 2


# -- filtros -----------------------------------------------------------------------------
def test_all_devuelve_tambien_los_no_activos(store):
    activo = _claim("cafe", text="me gusta el cafe")
    viejo = _claim("te", text="me gusta el te")
    viejo.status = Status.SUPERSEDED
    store.add(activo)
    store.add(viejo)

    assert {c.id for c in store.all()} == {activo.id, viejo.id}


def test_active_filtra_por_estado_agente_y_nivel(store):
    cafe_a1 = _claim("cafe", text="me gusta el cafe")
    te_a1 = _claim("te", text="me gusta el te")
    te_a1.tier = Tier.T2
    cafe_otro = _claim("cafe", text="me gusta el cafe", agent_id="a2")
    viejo = _claim("te", text="odio el te")
    viejo.status = Status.EXPIRED
    for c in (cafe_a1, te_a1, cafe_otro, viejo):
        store.add(c)

    assert {c.id for c in store.active()} == {cafe_a1.id, te_a1.id, cafe_otro.id}
    assert {c.id for c in store.active(agent_id="a1")} == {cafe_a1.id, te_a1.id}
    assert {c.id for c in store.active(agent_id="a1", tier=Tier.T2)} == {te_a1.id}


def test_by_subject_normaliza_y_excluye_los_no_vigentes(store):
    claim = _claim("Café", text="me gusta el cafe")  # acento y mayúscula
    store.add(claim)
    superseded = _claim("cafe", text="odio el cafe")
    superseded.status = Status.SUPERSEDED
    store.add(superseded)

    # el subject se compara normalizado; superseded no participa
    assert [c.id for c in store.by_subject("a1", "café")] == [claim.id]
    assert store.by_subject("a2", "cafe") == []


def test_by_subject_con_include_expired_encuentra_caducados(store):
    """Es el mecanismo del revival (Fase 6): un refuerzo nuevo revive un
    claim caducado en vez de crear un duplicado desde cero."""
    expirado = _claim("cafe", text="me gusta el cafe")
    expirado.status = Status.EXPIRED
    store.add(expirado)

    assert store.by_subject("a1", "cafe") == []
    assert [c.id for c in store.by_subject("a1", "cafe", include_expired=True)] == [expirado.id]
