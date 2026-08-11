"""Caducidad — Fase 6 del roadmap (`docs/01-MEMORIA-NIVELADA.md`).

La confianza efectiva de un claim decae exponencialmente desde
`last_reinforced_at`, con vida media `decay_half_life_days`:

    confianza_efectiva = confidence * 0.5 ** (dias_transcurridos / vida_media)

Un claim cuya confianza efectiva cae bajo `DEFAULT_EXPIRY_THRESHOLD` no se
borra — `expire_stale_claims()` lo pasa a `status=expired`. Deja de
recuperarse como evidencia activa (`InMemoryClaimStore.active()` y
`memory/retrieval.py` solo consultan claims `ACTIVE`), pero conserva su
proveniencia completa; un refuerzo nuevo lo revive
(`memory/reinforcement.py`, vía `find_match(..., include_expired=True)`).

Es un "scheduler" en el sentido del roadmap, no un daemon: `expire_stale_claims`
es una función pura que el llamante invoca periódicamente (cron, antes de
cada recuperación, al arrancar un proceso de mantenimiento) — igual que la
purga por tamaño de `orchestration/audit.py` y `memory/capture.py` es
perezosa (un chequeo por escritura), no un proceso en segundo plano.

`decay_half_life_days <= 0` se trata como "vida media indefinida": un claim
así (p.ej. una preferencia declarada, ver `docs/01-MEMORIA-NIVELADA.md`,
sección "Caducidad") nunca decae por tiempo — solo puede expirar si algo lo
contradice y lo sucede.
"""
from __future__ import annotations

from datetime import datetime, timezone

from memory.claims import MemoryClaim, Status
from memory.store import InMemoryClaimStore

#: Confianza efectiva por debajo de la cual un claim activo expira. Un solo
#: umbral para los tres niveles reforzables (T1/T2/T3): el nivel ya se
#: refleja en `confidence` de partida, así que no hay evidencia para
#: justificar umbrales de expiración distintos por tier sin datos reales de
#: uso — mismo criterio de no ajustar un parámetro sin banco de medición que
#: llevó a Magnus a fijar `OVERSAMPLE` en la meseta medida, no en el extremo.
DEFAULT_EXPIRY_THRESHOLD = 0.10


def effective_confidence(claim: MemoryClaim, *, now: datetime | None = None) -> float:
    if claim.decay_half_life_days <= 0:
        return claim.confidence

    ahora = now or datetime.now(timezone.utc)
    reforzado = datetime.fromisoformat(claim.last_reinforced_at)
    if reforzado.tzinfo is None:
        reforzado = reforzado.replace(tzinfo=timezone.utc)
    dias_transcurridos = max(0.0, (ahora - reforzado).total_seconds() / 86400)
    return claim.confidence * (0.5 ** (dias_transcurridos / claim.decay_half_life_days))


def expire_stale_claims(
    store: InMemoryClaimStore, *, threshold: float = DEFAULT_EXPIRY_THRESHOLD,
    now: datetime | None = None,
) -> list[MemoryClaim]:
    """Pasa a `status=expired` los claims activos cuya confianza efectiva
    cayó bajo `threshold`. Devuelve los recién expirados (para auditoría,
    ver `orchestration/audit.build_entry(event="expiration", ...)`)."""
    expirados = []
    for claim in store.active():
        if effective_confidence(claim, now=now) < threshold:
            claim.status = Status.EXPIRED
            store.add(claim)
            expirados.append(claim)
    return expirados
