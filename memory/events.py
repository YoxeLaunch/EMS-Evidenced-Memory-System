"""Cargas útiles canónicas de eventos de custodia — T-06 / A4.

Requisito del humano (2026-08-16, registrado en COLABORACION.md): cada
evento automático debe llevar un payload suficiente para RECONSTRUIR la
transición sin ejecutarla — estado anterior/nuevo, tier, contador,
proveniencia, relaciones de sucesión y motivo/evaluador cuando aplique.
Una secuencia que existe pero no explica el cambio no es cadena de
custodia.

`CustodyStore` detecta en runtime qué stores aceptan eventos: el pipeline
emite solo contra ellos, y los stores que no (p. ej. `InMemoryClaimStore`)
siguen funcionando sin eventos — auditoría por capacidad del store, no por
bandera global. Así el pipeline no bifurca en dos versiones.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Protocol, runtime_checkable

from memory.claims import MemoryClaim


@runtime_checkable
class CustodyStore(Protocol):
    """Store capaz de escribir eventos de custodia transaccionales.

    `runtime_checkable` verifica presencia de métodos (no firmas): todo
    store que quiera custodia debe aceptar los kwargs de eventos de `add`.
    """

    def add(self, claim: MemoryClaim, *, event_type: str | None = ...,
            conversation_id: str | None = ...,
            event_payload: dict | None = ...) -> None: ...

    def append_event(self, tipo: str, *, claim_id: str | None = ...,
                     conversation_id: str | None = ...,
                     payload: dict | None = ...) -> int: ...


def copia(claim: MemoryClaim) -> MemoryClaim:
    """Copia suficiente para el snapshot ANTERIOR. `replace` es shallow y
    `source_conversation_ids` es una lista que el pipeline muta in place
    después — sin copiarla, el 'anterior' se contaminaría con el
    'posterior' y el payload dejaría de explicar la transición."""
    return replace(claim, source_conversation_ids=list(claim.source_conversation_ids))


def payload_transicion(antes: MemoryClaim | None, despues: MemoryClaim, *,
                       conversacion: str | None = None,
                       motivo: str | None = None, evaluador: str | None = None,
                       **extra) -> dict:
    """Payload canónico de una transición de claim.

    `antes=None` marca una creación (extracción): no hay estado previo.
    `conversaciones_origen` va SIEMPRE (proveniencia posterior a la
    transición); `sucesion` solo si hay punteros; `motivo`/`evaluador`
    solo cuando aplican (promoción). Claves extra (p. ej.
    `confianza_efectiva` en expiración) se añaden sin romper el esquema.
    """
    payload: dict = {
        "estado_anterior": antes.status.value if antes is not None else None,
        "estado_nuevo": despues.status.value,
        "tier_anterior": antes.tier.value if antes is not None else None,
        "tier_nuevo": despues.tier.value,
        "contador_anterior": (antes.reinforcement_count
                              if antes is not None else None),
        "contador_nuevo": despues.reinforcement_count,
        "conversaciones_origen": list(despues.source_conversation_ids),
    }
    if conversacion is not None:
        payload["conversacion_disparadora"] = conversacion
    if despues.supersedes is not None or despues.superseded_by is not None:
        payload["sucesion"] = {
            "reemplaza_a": despues.supersedes,
            "reemplazado_por": despues.superseded_by,
        }
    if motivo is not None:
        payload["motivo"] = motivo
    if evaluador is not None:
        payload["evaluador"] = evaluador
    payload.update(extra)
    return payload
