"""Modelo de datos `MemoryClaim` — núcleo técnico de `docs/01-MEMORIA-NIVELADA.md`.

Sin equivalente directo en MagnusAgent: es "el único componente sin
equivalente directo en Magnus" según `docs/02-COMPONENTES-REUTILIZABLES.md`.
El hash de `id` reusa el mismo patrón que el hash de chunk de
`FileWikiStore` en Magnus — detectar que dos conversaciones distintas
produjeron el mismo candidato sin comparar texto libre cada vez.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Tier(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class Status(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    REJECTED = "rejected"


def normalize_text(text: str) -> str:
    """Normalización determinista para hash e igualdad de candidatos.

    Minúsculas, sin acentos, espacios colapsados — suficiente para detectar
    que dos formulaciones casi idénticas son "el mismo texto normalizado"
    sin meter comparación semántica en la identidad del claim (eso es
    trabajo del embedder en la deduplicación, ver `memory/dedup.py`).
    """
    t = text.strip().lower()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t)


def claim_id(agent_id: str, subject: str, text: str) -> str:
    """Hash de `(agent_id, subject, texto_normalizado)`."""
    base = f"{agent_id}\x00{normalize_text(subject)}\x00{normalize_text(text)}"
    return hashlib.blake2b(base.encode("utf-8"), digest_size=16).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class MemoryClaim:
    id: str
    agent_id: str
    subject: str
    text: str
    tier: Tier
    confidence: float
    source_conversation_ids: list[str] = field(default_factory=list)
    first_seen_at: str = ""
    last_reinforced_at: str = ""
    reinforcement_count: int = 1
    supersedes: str | None = None
    superseded_by: str | None = None
    decay_half_life_days: int = 180
    status: Status = Status.ACTIVE

    @classmethod
    def new_candidate(
        cls, *, agent_id: str, subject: str, text: str, source_conversation_id: str,
        confidence: float, decay_half_life_days: int = 180,
    ) -> "MemoryClaim":
        """Un candidato T1 recién extraído: cuenta de refuerzo = 1, activo."""
        now = _now()
        return cls(
            id=claim_id(agent_id, subject, text), agent_id=agent_id,
            subject=subject, text=text, tier=Tier.T1, confidence=confidence,
            source_conversation_ids=[source_conversation_id],
            first_seen_at=now, last_reinforced_at=now, reinforcement_count=1,
            decay_half_life_days=decay_half_life_days, status=Status.ACTIVE,
        )

    def as_dict(self) -> dict:
        return {
            "id": self.id, "agente": self.agent_id, "tema": self.subject,
            "texto": self.text, "nivel": self.tier.value,
            "confianza": self.confidence,
            "conversaciones_origen": list(self.source_conversation_ids),
            "visto_primera_vez": self.first_seen_at,
            "reforzado_ultima_vez": self.last_reinforced_at,
            "veces_reforzado": self.reinforcement_count,
            "reemplaza_a": self.supersedes,
            "reemplazado_por": self.superseded_by,
            "vida_media_dias": self.decay_half_life_days,
            "estado": self.status.value,
        }
