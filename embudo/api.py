"""Fachada `Embudo` — el orquestador del bucle que antes solo existía en
los tests de integración (hallazgo de la auditoría 2026-08-16: "el único
uso como llamante real es el test").

Un llamante real necesita: registrar conversación (con consentimiento) →
extraer candidatos → reforzar → promocionar → recuperar → estadística. Esta
clase cablea esas piezas sobre los stores que el llamante elija, con
recuperación cacheada (Fase A2) y cadena de custodia automática (T-06) si
el store la soporta.

Es deliberadamente fina: cada paso delega en el módulo dueño del criterio.
Ninguna decisión epistémica vive aquí.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from memory.capture import Consent, ConsentRequired, ConversationRecord, \
    JsonlConversationStore, Turn, record_conversation
from memory.claims import MemoryClaim, Tier
from memory.decay import expire_stale_claims
from memory.extraction import extract_candidates
from memory.promotion import Evaluator, PromotionResult, promote_to_t3
from memory.reinforcement import reinforce_or_create
from memory.retrieval import CachedTieredRetriever, TieredRAGContext
from memory.sqlite_store import SqliteClaimStore
from memory.store import InMemoryClaimStore


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Embudo:
    """Fachada estable del sistema de memoria nivelada ([D-08]).

    Uso típico::

        from embudo import Embudo
        from memory.capture import Consent, Turn

        with Embudo.open("memoria.db") as embudo:
            record, claims = embudo.register_conversation(
                [Turn("user", "soy alergico a la penicilina", _ts)],
                agent_id="dr_soma", user_id="user-1",
                consent=Consent(True, "raw_conversation", "user-1", _ts))
            ctx = embudo.recall("alergias del usuario", agent_id="dr_soma")
    """

    def __init__(self, *, claim_store: InMemoryClaimStore,
                 t0_store: JsonlConversationStore | None = None):
        self._claims = claim_store
        self._t0 = t0_store
        self._retriever = CachedTieredRetriever(claim_store)

    @classmethod
    def open(cls, path: str | Path, *, conversations_dir: str | Path | None = None,
             busy_timeout_ms: int = 250) -> "Embudo":
        """Abre (o crea) una memoria persistente: DB SQLite de claims + JSONL
        de conversaciones T0. Por defecto, las conversaciones van a
        `<db>-conversations/` junto a la DB."""
        path = Path(path)
        conv_dir = conversations_dir or path.parent / f"{path.stem}-conversations"
        return cls(
            claim_store=SqliteClaimStore(path, busy_timeout_ms=busy_timeout_ms),
            t0_store=JsonlConversationStore(conv_dir))

    # -- bucle de memoria ------------------------------------------------------------------
    def register_conversation(self, turns: list[Turn], *, agent_id: str,
                              user_id: str, consent: Consent,
                              sha256: str | None = None
                              ) -> tuple[ConversationRecord, list[MemoryClaim]]:
        """Registra T0 (consentimiento exigido ANTES de tocar disco), sus
        metadatos de fuente, y corre el pipeline extract→reinforce.

        Devuelve `(record, resultados)` — el registro crudo con su id de
        proveniencia y los claims resultantes de cada candidato. Sin
        `t0_store` (uso en RAM) el registro se construye sin persistirse —
        pero la puerta de consentimiento es la MISMA: no hay registro sin
        autorización explícita, persista o no.
        """
        if self._t0 is not None:
            record = record_conversation(
                self._t0, agent_id=agent_id, user_id=user_id,
                turns=list(turns), consent=consent)
        else:
            if not consent.granted:
                raise ConsentRequired(
                    f"'{user_id}' no concedió consentimiento explícito para "
                    f"procesar esta conversación con el agente '{agent_id}' "
                    f"(alcance solicitado: '{consent.scope}')")
            record = ConversationRecord(
                id=str(uuid.uuid4()), agent_id=agent_id, user_id=user_id,
                started_at=_utcnow(), turns=tuple(turns), consent=consent)
        registrar_fuente = getattr(self._claims, "record_conversation_source", None)
        if registrar_fuente is not None:  # stores con custodia [ALT-02]
            registrar_fuente(record.id, agent_id=agent_id, user_id=user_id,
                             started_at=record.started_at, sha256=sha256)
        resultados = [reinforce_or_create(c, self._claims)
                      for c in extract_candidates(record)]
        return record, resultados

    def recall(self, query: str, *, agent_id: str, top_k: int = 8
               ) -> TieredRAGContext:
        """Evidencia T2/T3 activa del agente, etiquetada por nivel — el
        bloque de prompt va en `ctx.as_prompt_block()`."""
        self._retriever._top_k = top_k
        return self._retriever.context_for(query, agent_id)

    def promote(self, claim_or_id: MemoryClaim | str, *, high_risk: bool = False,
                human_confirmed: bool = False, evaluator: Evaluator | None = None
                ) -> PromotionResult:
        claim = (self._claims.get(claim_or_id) if isinstance(claim_or_id, str)
                 else claim_or_id)
        return promote_to_t3(claim, self._claims, high_risk=high_risk,
                             human_confirmed=human_confirmed, evaluator=evaluator)

    def expire_stale(self, *, now: datetime | None = None) -> list[MemoryClaim]:
        """Mantenimiento perezoso de caducidad — invocarlo periódicamente
        (arranque, antes de recuperar) es responsabilidad del llamante."""
        return expire_stale_claims(self._claims, now=now)

    # -- consulta --------------------------------------------------------------------------
    def claims(self, *, agent_id: str | None = None, tier: Tier | None = None,
               active_only: bool = True) -> list[MemoryClaim]:
        if active_only:
            return self._claims.active(agent_id=agent_id, tier=tier)
        return [c for c in self._claims.all()
                if (agent_id is None or c.agent_id == agent_id)
                and (tier is None or c.tier == tier)]

    def stats(self) -> dict:
        """Resumen de salud de la memoria — la base de `embudo stats` (G1).
        Degrada sin error sobre stores sin custodia (RAM)."""
        activos = self._claims.active()
        por_tier = {t.value: 0 for t in Tier}
        por_estado: dict[str, int] = {}
        for c in self._claims.all():
            por_estado[c.status.value] = por_estado.get(c.status.value, 0) + 1
        for c in activos:
            por_tier[c.tier.value] += 1

        eventos: dict[str, int] | None = None
        leer_eventos = getattr(self._claims, "events", None)
        if leer_eventos is not None:
            eventos = {}
            for e in leer_eventos():
                eventos[e.tipo] = eventos.get(e.tipo, 0) + 1

        return {
            "claims_activos": len(activos),
            "por_tier": por_tier,
            "por_estado": por_estado,
            "eventos": eventos,
            "conversaciones_t0": len(self._t0.read_all()) if self._t0 else None,
            "construcciones_indice": self._retriever.builds,
            "esquema": getattr(self._claims, "schema_version", None),
        }

    # -- ciclo de vida ---------------------------------------------------------------------
    def close(self) -> None:
        cerrar = getattr(self._claims, "close", None)
        if cerrar is not None:
            cerrar()

    def __enter__(self) -> "Embudo":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
