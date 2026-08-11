"""Deduplicación de candidatos T1 contra claims existentes (`memory/dedup.py`)."""
from __future__ import annotations

from memory.claims import MemoryClaim
from memory.dedup import find_match
from memory.store import InMemoryClaimStore


def _claim(subject: str, text: str, *, agent_id: str = "a1",
          source: str = "conv-1") -> MemoryClaim:
    return MemoryClaim.new_candidate(
        agent_id=agent_id, subject=subject, text=text,
        source_conversation_id=source, confidence=0.5)


def test_un_candidato_sin_claims_previos_no_tiene_match():
    store = InMemoryClaimStore()
    candidato = _claim("cafe", "me gusta el cafe negro")
    assert find_match(candidato, store) is None


def test_un_candidato_con_texto_casi_identico_hace_match_por_subject_y_embedding():
    store = InMemoryClaimStore()
    existente = _claim("cafe", "me gusta el cafe negro sin azucar")
    store.add(existente)

    candidato = _claim("cafe", "me gusta el cafe negro sin azucar por las mananas")

    assert find_match(candidato, store) is existente


def test_mismo_subject_pero_texto_muy_distinto_no_hace_match():
    store = InMemoryClaimStore()
    existente = _claim("trabajo", "trabajo como programador en una empresa de software")
    store.add(existente)

    candidato = _claim("trabajo", "odio el ruido de los martillos neumaticos en la calle")

    assert find_match(candidato, store) is None


def test_texto_similar_pero_subject_distinto_no_hace_match():
    store = InMemoryClaimStore()
    existente = _claim("cafe", "me gusta el cafe negro")
    store.add(existente)

    candidato = _claim("te", "me gusta el te negro")  # subject distinto, texto casi igual

    assert find_match(candidato, store) is None


def test_solo_compara_contra_claims_del_mismo_agente():
    store = InMemoryClaimStore()
    existente = _claim("cafe", "me gusta el cafe negro", agent_id="agente-1")
    store.add(existente)

    candidato = _claim("cafe", "me gusta el cafe negro", agent_id="agente-2")

    assert find_match(candidato, store) is None
