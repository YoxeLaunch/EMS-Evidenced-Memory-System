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
from memory.claims import MemoryClaim, Status, Tier, normalize_text
from memory.dedup import find_match
from memory.store import InMemoryClaimStore

#: Nº de refuerzos en conversaciones distintas para ascender T1 → T2.
DEFAULT_REINFORCEMENT_THRESHOLD = 3

#: Marcadores discursivos de cambio (texto normalizado, sin acentos) que se
#: quitan antes de comparar negaciones. Solo la parte DISCURSIVA: "ya no como
#: carne" deja "no como carne" (el "no" es el negador, se conserva), y "dejo
#: de fumar" deja "fumar". Sin estos prefijos, "ya no como carne" no calzaría
#: con ningún patrón de negación literal.
_PREFIJOS_CAMBIO = ("ya", "ahora", "deje de", "dejo de")


def _sin_prefijo_cambio(t: str) -> str:
    """Quita prefijos discursivos de cambio ("ahora ya no como carne" →
    "no como carne") de un texto YA normalizado por `normalize_text`."""
    for _ in range(3):
        for prefijo in _PREFIJOS_CAMBIO:
            if t == prefijo or t.startswith(prefijo + " "):
                t = t[len(prefijo):].strip()
                break
    return t


def _es_negacion_de(a: str, b: str) -> bool:
    """¿`a` es la negación explícita de `b`?

    Caso exacto: `a == "no " + b` ("no como carne" niega "como carne").

    Caso prefijo: `a` niega un PREFIJO POR PALABRA de `b` — "no como carne"
    también niega "como carne todos los dias", porque al corregir el usuario
    no repite el detalle completo. Es el ejemplo canónico de `docs/01`
    ('ya no como carne' tras 'como carne todos los días'). El corte por
    palabra (nunca a mitad de palabra) mantiene la comparación estructural.
    """
    if not b or not a.startswith("no ") or len(a) <= 3:
        return False
    if a == f"no {b}":
        return True
    resto = a[3:]
    return bool(resto) and b.startswith(resto) and (
        len(b) == len(resto) or b[len(resto)] == " "
    )


def detect_contradiction(candidate: MemoryClaim, store: InMemoryClaimStore) -> MemoryClaim | None:
    """Un claim ACTIVO (T1/T2/T3) del mismo subject cuyo texto es la negación
    directa del candidato (o viceversa) — contradicción EXPLÍCITA, no inferida.

    La sucesión resultante no infla autoridad: el candidato entra como T1
    (no hereda el tier del reemplazado) y el reemplazado baja a
    `superseded` conservando proveniencia.
    """
    activos = store.by_subject(candidate.agent_id, candidate.subject)
    cand_norm = _sin_prefijo_cambio(normalize_text(candidate.text))
    for existente in activos:
        exist_norm = _sin_prefijo_cambio(normalize_text(existente.text))
        if _es_negacion_de(cand_norm, exist_norm) or _es_negacion_de(exist_norm, cand_norm):
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
    revive_expired: bool = True,
) -> MemoryClaim:
    """Procesa un candidato T1 recién extraído contra el store.

    Devuelve el claim resultante: el existente reforzado (posiblemente ya
    ascendido a T2 o revivido desde `expired`), el nuevo candidato
    reemplazando a uno contradicho, o el candidato mismo si es genuinamente
    nuevo.
    """
    contradicho = detect_contradiction(candidate, store)
    if contradicho is not None:
        store.add(candidate)  # el candidato entra como T1 nuevo, no hereda tier
        return supersede(candidate, contradicho, store)

    match = find_match(candidate, store, embedder=embedder)
    if match is None and revive_expired:
        match = find_match(candidate, store, embedder=embedder, include_expired=True)

    if match is None:
        store.add(candidate)
        return candidate

    origen = candidate.source_conversation_ids[0]
    era_expirado = match.status == Status.EXPIRED
    if origen in match.source_conversation_ids and not era_expirado:
        return match  # misma conversación: no es una señal independiente

    if era_expirado:
        match.status = Status.ACTIVE
    if origen not in match.source_conversation_ids:
        match.source_conversation_ids.append(origen)
        match.reinforcement_count += 1
    match.last_reinforced_at = candidate.first_seen_at
    match.confidence = max(match.confidence, candidate.confidence)
    if match.tier == Tier.T1 and match.reinforcement_count >= threshold:
        match.tier = Tier.T2
    store.add(match)
    return match
