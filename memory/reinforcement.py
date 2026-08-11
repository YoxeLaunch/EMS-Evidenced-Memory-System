"""Refuerzo (T1 → T2) y sucesión por contradicción — Fase 3 del roadmap.

Orquesta lo que un candidato nuevo hace contra el store de claims:

  1. ¿Contradice explícitamente un T2/T3 activo del mismo subject? → sucesión
     (`supersedes`/`superseded_by`), nunca sobrescritura.
  2. Si no, ¿coincide con un claim existente (`memory/dedup.py`)? → refuerzo:
     `reinforcement_count += 1`, y si cruza el umbral, asciende a T2.
  3. Si no coincide con nada → es un candidato nuevo, se guarda tal cual.

El orden importa: la contradicción se comprueba ANTES del match por
embedding. "como carne" y "no como carne" comparten casi todo su
vocabulario ("no" es stopword para `HashingEmbedder`) y su coseno sería
alto — si se comprobara el match primero, una contradicción se leería como
un refuerzo del mismo claim. Por eso la detección de contradicción no usa el
embedder: es una comparación estructural explícita sobre el texto
normalizado, exactamente el criterio de `docs/01-MEMORIA-NIVELADA.md`
("empezar con contradicciones explícitas... antes de intentar detectar
contradicciones implícitas o inferidas").

Repetición dentro de la misma conversación NO cuenta como señal de refuerzo
(mismo criterio del documento): si el `source_conversation_id` del
candidato ya está en `source_conversation_ids` del claim que matchea, se
devuelve el claim sin incrementar nada.
"""
from __future__ import annotations

from rag.embedder import HashingEmbedder
from memory.claims import MemoryClaim, Status, Tier, normalize_text
from memory.dedup import find_match
from memory.store import InMemoryClaimStore

#: Nº de refuerzos en conversaciones distintas para ascender T1 → T2.
DEFAULT_REINFORCEMENT_THRESHOLD = 3


def detect_contradiction(candidate: MemoryClaim, store: InMemoryClaimStore) -> MemoryClaim | None:
    """Un T2/T3 activo del mismo subject cuyo texto es la negación directa
    del candidato (o viceversa) — contradicción EXPLÍCITA, no inferida."""
    activos = [c for c in store.by_subject(candidate.agent_id, candidate.subject)
               if c.tier in (Tier.T2, Tier.T3)]
    cand_norm = normalize_text(candidate.text)
    for existente in activos:
        exist_norm = normalize_text(existente.text)
        if cand_norm == f"no {exist_norm}" or exist_norm == f"no {cand_norm}":
            return existente
    return None


def supersede(new: MemoryClaim, old: MemoryClaim, store: InMemoryClaimStore) -> MemoryClaim:
    """Marca `old` como reemplazado por `new`. Nunca borra ni sobrescribe
    contenido — solo cambia estado y pointers de sucesión."""
    old.status = Status.SUPERSEDED
    old.superseded_by = new.id
    new.supersedes = old.id
    store.add(old)
    store.add(new)
    return new


def reinforce_or_create(
    candidate: MemoryClaim, store: InMemoryClaimStore, *,
    embedder: HashingEmbedder | None = None,
    threshold: int = DEFAULT_REINFORCEMENT_THRESHOLD,
) -> MemoryClaim:
    """Procesa un candidato T1 recién extraído contra el store.

    Devuelve el claim resultante: el existente reforzado (posiblemente ya
    ascendido a T2), el nuevo candidato reemplazando a uno contradicho, o el
    candidato mismo si es genuinamente nuevo.
    """
    contradicho = detect_contradiction(candidate, store)
    if contradicho is not None:
        store.add(candidate)  # el candidato entra como T1 nuevo, no hereda tier
        return supersede(candidate, contradicho, store)

    match = find_match(candidate, store, embedder=embedder)
    if match is None:
        store.add(candidate)
        return candidate

    origen = candidate.source_conversation_ids[0]
    if origen in match.source_conversation_ids:
        return match  # misma conversación: no es una señal independiente

    match.source_conversation_ids.append(origen)
    match.reinforcement_count += 1
    match.last_reinforced_at = candidate.first_seen_at
    match.confidence = max(match.confidence, candidate.confidence)
    if match.tier == Tier.T1 and match.reinforcement_count >= threshold:
        match.tier = Tier.T2
    store.add(match)
    return match
