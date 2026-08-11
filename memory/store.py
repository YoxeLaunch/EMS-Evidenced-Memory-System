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

    def by_subject(self, agent_id: str, subject: str) -> list[MemoryClaim]:
        """Claims activos del mismo agente y mismo `subject` normalizado —
        el candidato a match previo a la comparación de embedding
        (`memory/dedup.py`)."""
        s = normalize_text(subject)
        return [c for c in self.active(agent_id=agent_id)
                if normalize_text(c.subject) == s]
