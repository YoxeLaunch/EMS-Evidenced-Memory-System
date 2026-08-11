"""Store en memoria de `MemoryClaim` — sin equivalente en MagnusAgent.

Deliberadamente el backend más simple que cumple el contrato, mismo criterio
que `InMemoryVectorStore` en `rag/vector_store.py`. Persistencia real (SQLite,
archivo) es sustituir esta clase, no tocar el pipeline de memoria nivelada.
"""
from __future__ import annotations

from memory.claims import MemoryClaim, Status, Tier, normalize_text


class InMemoryClaimStore:
    def __init__(self) -> None:
        self._claims: dict[str, MemoryClaim] = {}

    def add(self, claim: MemoryClaim) -> None:
        self._claims[claim.id] = claim

    def get(self, claim_id: str) -> MemoryClaim | None:
        return self._claims.get(claim_id)

    def all(self) -> list[MemoryClaim]:
        return list(self._claims.values())

    def active(self, *, agent_id: str | None = None,
               tier: Tier | None = None) -> list[MemoryClaim]:
        out = [c for c in self._claims.values() if c.status == Status.ACTIVE]
        if agent_id is not None:
            out = [c for c in out if c.agent_id == agent_id]
        if tier is not None:
            out = [c for c in out if c.tier == tier]
        return out

    def by_subject(self, agent_id: str, subject: str, *,
                   include_expired: bool = False) -> list[MemoryClaim]:
        """Claims del mismo agente y mismo `subject` normalizado — el
        candidato a match previo a la comparación de embedding
        (`memory/dedup.py`).

        `include_expired=True` añade los `status=expired` a la búsqueda: es
        lo que permite que un refuerzo nuevo revive un claim caducado
        (`memory/decay.py`) en vez de crear un duplicado desde cero. Por
        defecto solo activos — la detección de contradicción y el match
        normal no deben considerar algo que ya dejó de ser evidencia vigente.
        """
        s = normalize_text(subject)
        estados = {Status.ACTIVE} | ({Status.EXPIRED} if include_expired else set())
        return [c for c in self._claims.values()
                if c.agent_id == agent_id and c.status in estados
                and normalize_text(c.subject) == s]
