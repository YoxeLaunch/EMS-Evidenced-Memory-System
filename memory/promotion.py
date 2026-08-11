"""Evaluador de promoción (T2 → T3) — Fase 4 del roadmap, el punto de mayor
riesgo del sistema (`docs/01-MEMORIA-NIVELADA.md`).

Reusa el patrón de `Evaluator` como `Protocol` de MagnusAgent
(`orchestration/evaluation/`, ver `docs/02-COMPONENTES-REUTILIZABLES.md`):
estructural y determinista primero — mismo criterio que
`citation_evaluator.py` — con el puerto ya definido para que un LLM-as-judge
se enchufe más adelante sin tocar `promote_to_t3`.

Dos rutas, no mutuamente excluyentes (`docs/01-MEMORIA-NIVELADA.md`):

  1. **Evaluador automático** (`StructuralPromotionEvaluator`): refuerzo
     suficiente, procedencia diversa (no todo de una sola sesión larga) y
     ausencia de contradicción con otro T3 activo del mismo subject.
  2. **Confirmación humana**, obligatoria en dominios de alto riesgo — pero
     el evaluador automático corre SIEMPRE, incluso ahí: un claim
     inconsistente no debe promoverse aunque un humano lo confirme sin saber
     que ya contradice algo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memory.claims import MemoryClaim, Status, Tier, normalize_text
from memory.reinforcement import DEFAULT_REINFORCEMENT_THRESHOLD
from memory.store import InMemoryClaimStore

#: Mínimo de conversaciones distintas de origen para promover — evita que
#: una sesión larga hablando del mismo tema, sin repetirse en otra ocasión,
#: cuente como consistencia entre conversaciones.
DEFAULT_MIN_PROVENANCE_DIVERSITY = 2


@dataclass(frozen=True)
class PromotionResult:
    approved: bool
    reason: str
    claim: MemoryClaim | None = None

    def __bool__(self) -> bool:
        return self.approved


class Evaluator(Protocol):
    """Puerto de evaluación de promoción — habilita un LLM-as-judge futuro
    sin tocar `promote_to_t3`."""

    def evaluate(self, claim: MemoryClaim, store: InMemoryClaimStore) -> PromotionResult: ...


class StructuralPromotionEvaluator:
    """Determinista: refuerzo + procedencia diversa + sin contradicción T3 activa."""

    def __init__(self, *, min_reinforcement: int = DEFAULT_REINFORCEMENT_THRESHOLD,
                min_provenance_diversity: int = DEFAULT_MIN_PROVENANCE_DIVERSITY):
        self._min_reinforcement = min_reinforcement
        self._min_diversity = min_provenance_diversity

    def evaluate(self, claim: MemoryClaim, store: InMemoryClaimStore) -> PromotionResult:
        if claim.status != Status.ACTIVE:
            return PromotionResult(False, f"el claim no está activo (estado='{claim.status.value}')")

        if claim.reinforcement_count < self._min_reinforcement:
            return PromotionResult(
                False,
                f"refuerzo insuficiente: {claim.reinforcement_count} < {self._min_reinforcement}")

        diversidad = len(set(claim.source_conversation_ids))
        if diversidad < self._min_diversity:
            return PromotionResult(
                False,
                f"procedencia poco diversa: {diversidad} conversación(es) distinta(s), "
                f"se requieren al menos {self._min_diversity}")

        contradiccion = _t3_contradictorio(claim, store)
        if contradiccion is not None:
            return PromotionResult(
                False, f"contradice al claim T3 activo '{contradiccion.id}'")

        return PromotionResult(
            True, "consistencia verificada: refuerzo, procedencia y sin contradicción")


def _t3_contradictorio(claim: MemoryClaim, store: InMemoryClaimStore) -> MemoryClaim | None:
    cand_norm = normalize_text(claim.text)
    for existente in store.by_subject(claim.agent_id, claim.subject):
        if existente.tier != Tier.T3 or existente.id == claim.id:
            continue
        exist_norm = normalize_text(existente.text)
        if cand_norm == f"no {exist_norm}" or exist_norm == f"no {cand_norm}":
            return existente
    return None


def promote_to_t3(
    claim: MemoryClaim, store: InMemoryClaimStore, *,
    evaluator: Evaluator | None = None, high_risk: bool = False,
    human_confirmed: bool = False,
) -> PromotionResult:
    """Promueve un claim T2 a T3, o lo bloquea con el motivo registrado.

    `high_risk=True` exige `human_confirmed=True` ADEMÁS de pasar el
    evaluador automático — nunca en su lugar.
    """
    if claim.tier != Tier.T2:
        return PromotionResult(
            False, f"solo se promueven claims T2 (tier actual: {claim.tier.value})")

    ev = evaluator or StructuralPromotionEvaluator()
    resultado = ev.evaluate(claim, store)
    if not resultado:
        return resultado

    if high_risk and not human_confirmed:
        return PromotionResult(
            False,
            "dominio de alto riesgo: requiere confirmación humana explícita antes de promover")

    claim.tier = Tier.T3
    store.add(claim)
    return PromotionResult(True, resultado.reason, claim=claim)
