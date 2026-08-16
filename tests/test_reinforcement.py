"""Refuerzo y sucesión — criterio de hecho de la Fase 3 (`docs/03-ROADMAP.md`):
un claim reforzado tres veces en conversaciones distintas asciende a T2; un
claim que contradice a otro T2 activo genera sucesión trazable, ambos
consultables con su estado correcto.
"""
from __future__ import annotations

from memory.claims import MemoryClaim, Status, Tier
from memory.reinforcement import (
    DEFAULT_REINFORCEMENT_THRESHOLD, detect_contradiction, reinforce_or_create,
    supersede,
)
from memory.store import InMemoryClaimStore


def _candidato(subject: str, text: str, *, source: str, agent_id: str = "a1") -> MemoryClaim:
    return MemoryClaim.new_candidate(
        agent_id=agent_id, subject=subject, text=text,
        source_conversation_id=source, confidence=0.5)


# -- refuerzo -----------------------------------------------------------------------
def test_un_candidato_nuevo_se_guarda_como_t1():
    store = InMemoryClaimStore()
    candidato = _candidato("cafe", "me gusta el cafe negro", source="conv-1")

    resultado = reinforce_or_create(candidato, store)

    assert resultado is candidato
    assert resultado.tier == Tier.T1
    assert resultado.reinforcement_count == 1


def test_repeticion_en_conversaciones_distintas_incrementa_el_contador():
    store = InMemoryClaimStore()
    store.add(_candidato("cafe", "me gusta el cafe negro", source="conv-1"))

    resultado = reinforce_or_create(
        _candidato("cafe", "me gusta el cafe negro", source="conv-2"), store)

    assert resultado.reinforcement_count == 2
    assert set(resultado.source_conversation_ids) == {"conv-1", "conv-2"}


def test_repeticion_dentro_de_la_misma_conversacion_no_cuenta():
    store = InMemoryClaimStore()
    existente = _candidato("cafe", "me gusta el cafe negro", source="conv-1")
    store.add(existente)

    resultado = reinforce_or_create(
        _candidato("cafe", "me gusta el cafe negro", source="conv-1"), store)

    assert resultado.reinforcement_count == 1
    assert resultado.source_conversation_ids == ["conv-1"]


def test_tres_refuerzos_en_conversaciones_distintas_ascienden_a_t2():
    store = InMemoryClaimStore()
    assert DEFAULT_REINFORCEMENT_THRESHOLD == 3

    store.add(_candidato("cafe", "me gusta el cafe negro", source="conv-1"))
    reinforce_or_create(_candidato("cafe", "me gusta el cafe negro", source="conv-2"), store)
    resultado = reinforce_or_create(
        _candidato("cafe", "me gusta el cafe negro", source="conv-3"), store)

    assert resultado.tier == Tier.T2
    assert resultado.reinforcement_count == 3


def test_dos_refuerzos_no_alcanzan_para_ascender():
    store = InMemoryClaimStore()
    store.add(_candidato("cafe", "me gusta el cafe negro", source="conv-1"))
    resultado = reinforce_or_create(
        _candidato("cafe", "me gusta el cafe negro", source="conv-2"), store)

    assert resultado.tier == Tier.T1


# -- contradicción y sucesión ---------------------------------------------------------
def test_contradiccion_explicita_genera_sucesion_trazable():
    store = InMemoryClaimStore()
    viejo = _candidato("dieta", "como carne todos los dias", source="conv-1")
    viejo.tier = Tier.T2
    store.add(viejo)

    contradicho = detect_contradiction(
        _candidato("dieta", "no como carne todos los dias", source="conv-2"), store)

    assert contradicho is viejo


def test_negar_un_t1_produce_sucesion_no_refuerzo():
    """Fase B (docs/04): la grieta que cierra este test — sin T1 en la
    detección de contradicción, 'no como carne' matchea por embedding
    (coseno ≈ 1.0, 'no' es stopword) y REFUERZA al claim que contradice."""
    store = InMemoryClaimStore()
    viejo = _candidato("dieta", "como carne todos los dias", source="conv-1")  # T1
    store.add(viejo)

    resultado = reinforce_or_create(
        _candidato("dieta", "no como carne todos los dias", source="conv-2"), store)

    assert resultado.supersedes == viejo.id
    assert viejo.status == Status.SUPERSEDED
    assert resultado.reinforcement_count == 1, "es un claim nuevo, no un refuerzo"
    assert resultado.tier == Tier.T1, "la sucesión no hereda autoridad"


def test_ya_no_como_carne_niega_al_claim_con_detalle_por_prefijo():
    """El ejemplo LITERAL de docs/01: al corregir, el usuario no repite el
    detalle completo — 'ya no como carne' niega 'como carne todos los dias'
    por prefijo por palabra."""
    store = InMemoryClaimStore()
    viejo = _candidato("carne", "como carne todos los dias", source="conv-1")
    viejo.tier = Tier.T2
    store.add(viejo)

    resultado = reinforce_or_create(
        _candidato("carne", "ya no como carne", source="conv-2"), store)

    assert resultado.supersedes == viejo.id
    assert viejo.status == Status.SUPERSEDED


def test_reafirmacion_tras_un_cambio_tambien_genera_sucesion():
    """Dirección inversa: 'como carne' tras 'ya no como carne' — la
    reafirmación sucede a la cesación, no la refuerza."""
    store = InMemoryClaimStore()
    viejo = _candidato("carne", "ya no como carne", source="conv-1")
    viejo.tier = Tier.T2
    store.add(viejo)

    resultado = reinforce_or_create(
        _candidato("carne", "como carne", source="conv-2"), store)

    assert resultado.supersedes == viejo.id
    assert viejo.status == Status.SUPERSEDED


def test_procesar_un_candidato_contradictorio_marca_sucesion_sin_borrar_el_viejo():
    store = InMemoryClaimStore()
    viejo = _candidato("dieta", "como carne todos los dias", source="conv-1")
    viejo.tier = Tier.T2
    store.add(viejo)

    nuevo_candidato = _candidato("dieta", "no como carne todos los dias", source="conv-2")
    resultado = reinforce_or_create(nuevo_candidato, store)

    assert resultado.id == nuevo_candidato.id
    assert resultado.supersedes == viejo.id
    assert viejo.status == Status.SUPERSEDED
    assert viejo.superseded_by == resultado.id
    # el viejo sigue en el store, consultable, solo que no activo
    assert store.get(viejo.id) is viejo
    assert viejo not in store.active(agent_id="a1")
    assert resultado in store.active(agent_id="a1")


def test_una_contradiccion_no_se_confunde_con_refuerzo_por_vocabulario_compartido():
    """'como carne' y 'no como carne' comparten casi todo el vocabulario —
    el match por embedding solo (sin chequeo de contradicción antes) los
    trataría como el mismo claim reforzado. No debe pasar."""
    store = InMemoryClaimStore()
    viejo = _candidato("dieta", "como carne todos los dias", source="conv-1")
    viejo.tier = Tier.T2
    store.add(viejo)

    resultado = reinforce_or_create(
        _candidato("dieta", "no como carne todos los dias", source="conv-2"), store)

    assert resultado.text == "no como carne todos los dias"
    assert resultado.reinforcement_count == 1, "es un claim nuevo, no un refuerzo del viejo"


def test_supersede_no_borra_proveniencia_del_reemplazado():
    store = InMemoryClaimStore()
    viejo = _candidato("dieta", "como carne todos los dias", source="conv-1")
    store.add(viejo)
    nuevo = _candidato("dieta", "no como carne todos los dias", source="conv-2")

    supersede(nuevo, viejo, store)

    assert viejo.source_conversation_ids == ["conv-1"]
    assert viejo.text == "como carne todos los dias"
