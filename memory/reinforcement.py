"""Refuerzo (T1 → T2) y sucesión por contradicción — Fase 3 del roadmap.

Orquesta lo que un candidato nuevo hace contra el store de claims:

  1. ¿Contradice explícitamente un claim ACTIVO del mismo subject (T1, T2 o
     T3)? → sucesión (`supersedes`/`superseded_by`), nunca sobrescritura.
     Desde la Fase B (`docs/04-PLAN-MEJORAS.md`) también participan los T1:
     sin ellos, una negación temprana matchea por embedding y REFUERZA al
     claim que contradice — exactamente el eco que el sistema evita.
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

Revivir un claim caducado (Fase 6, `memory/decay.py`)
--------------------------------------------------------
Si no hay match activo, se busca también entre los claims `EXPIRED` del
mismo subject (`find_match(..., include_expired=True)`). Un refuerzo nuevo
sobre algo que había dejado de recuperarse por caducidad lo revive
(`status` vuelve a `active`) en vez de crear un candidato T1 duplicado desde
cero — mismo criterio de `docs/01-MEMORIA-NIVELADA.md`: "conserva
proveniencia por si se reactiva".
"""
from __future__ import annotations

from rag.embedder import HashingEmbedder
from memory.claims import (
    MemoryClaim, Status, Tier, es_negacion_de, normalize_text, sin_prefijo_discurso,
)
from memory.dedup import find_match
from memory.events import CustodyStore, copia, payload_transicion
from memory.store import InMemoryClaimStore

#: Nº de refuerzos en conversaciones distintas para ascender T1 → T2.
DEFAULT_REINFORCEMENT_THRESHOLD = 3


def detect_contradiction(candidate: MemoryClaim, store: InMemoryClaimStore) -> MemoryClaim | None:
    """Un claim ACTIVO (T1/T2/T3) del mismo subject cuyo texto es la negación
    directa del candidato (o viceversa) — contradicción EXPLÍCITA, no inferida.

    La sucesión resultante no infla autoridad: el candidato entra como T1
    (no hereda el tier del reemplazado) y el reemplazado baja a
    `superseded` conservando proveniencia.
    """
    activos = store.by_subject(candidate.agent_id, candidate.subject)
    cand_norm = sin_prefijo_discurso(normalize_text(candidate.text))
    for existente in activos:
        exist_norm = sin_prefijo_discurso(normalize_text(existente.text))
        if es_negacion_de(cand_norm, exist_norm) or es_negacion_de(exist_norm, cand_norm):
            return existente
    return None


def supersede(new: MemoryClaim, old: MemoryClaim, store: InMemoryClaimStore, *,
              conversacion: str | None = None) -> MemoryClaim:
    """Marca `old` como reemplazado por `new`. Nunca borra ni sobrescribe
    contenido — solo cambia estado y pointers de sucesión.

    Contra un store con custodia, el cambio de estado de `old` se escribe
    con su evento `supersession` en la misma transición ([D-07]).
    """
    antes = copia(old)
    old.status = Status.SUPERSEDED
    old.superseded_by = new.id
    new.supersedes = old.id
    if isinstance(store, CustodyStore):
        store.add(old, event_type="supersession", conversation_id=conversacion,
                  event_payload=payload_transicion(antes, old, conversacion=conversacion))
        store.add(new)
    else:
        store.add(old)
        store.add(new)
    return new


def reinforce_or_create(
    candidate: MemoryClaim, store: InMemoryClaimStore, *,
    embedder: HashingEmbedder | None = None,
    threshold: int = DEFAULT_REINFORCEMENT_THRESHOLD,
    revive_expired: bool = True,
) -> MemoryClaim:
    """Procesa un candidato T1 recién extraído contra el store.

    Devuelve el claim resultante: el existente reforzado (posiblemente ya
    ascendido a T2 o revivido desde `expired`), el nuevo candidato
    reemplazando a uno contradicho, o el candidato mismo si es genuinamente
    nuevo.

    Contra un store con custodia (`CustodyStore`), cada cambio de estado
    emite su evento automáticamente — el llamante no pasa `event_type`:
    extracción al entrar un claim nuevo, refuerzo al mutar uno existente
    (incluido el revival desde `expired`), sucesión en la contradicción.
    """
    custodia = isinstance(store, CustodyStore)
    origen = (candidate.source_conversation_ids[0]
              if candidate.source_conversation_ids else None)

    contradicho = detect_contradiction(candidate, store)
    if contradicho is not None:
        # el puntero se fija ANTES del add para que el payload de extracción
        # nazca documentando la relación (supersede re-asigna el mismo valor)
        candidate.supersedes = contradicho.id
        if custodia:
            store.add(candidate, event_type="extraction", conversation_id=origen,
                      event_payload=payload_transicion(None, candidate, conversacion=origen))
        else:
            store.add(candidate)  # el candidato entra como T1 nuevo, no hereda tier
        return supersede(candidate, contradicho, store, conversacion=origen)

    match = find_match(candidate, store, embedder=embedder)
    if match is None and revive_expired:
        match = find_match(candidate, store, embedder=embedder, include_expired=True)

    if match is None:
        if custodia:
            store.add(candidate, event_type="extraction", conversation_id=origen,
                      event_payload=payload_transicion(None, candidate, conversacion=origen))
        else:
            store.add(candidate)
        return candidate

    era_expirado = match.status == Status.EXPIRED
    if origen in match.source_conversation_ids and not era_expirado:
        return match  # misma conversación: no es una señal independiente

    antes = copia(match)
    if era_expirado:
        match.status = Status.ACTIVE
    if origen not in match.source_conversation_ids:
        match.source_conversation_ids.append(origen)
        match.reinforcement_count += 1
    match.last_reinforced_at = candidate.first_seen_at
    match.confidence = max(match.confidence, candidate.confidence)
    if match.tier == Tier.T1 and match.reinforcement_count >= threshold:
        match.tier = Tier.T2
    if custodia:
        store.add(match, event_type="reinforcement", conversation_id=origen,
                  event_payload=payload_transicion(antes, match, conversacion=origen))
    else:
        store.add(match)
    return match
