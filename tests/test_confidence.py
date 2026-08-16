"""B2 / T-05 — confianza acumulativa derivada ([D-09]).

Los tres requisitos de la decisión que estos tests fijan:
1. Separada de la base: llamarla no muta `claim.confidence`.
2. No es gate: `memory/promotion.py` no la consume (la promoción sigue
   siendo estructural).
3. Monótona en la evidencia y decaída por tiempo — reusando la vida media
   de `decay`, no una segunda noción de tiempo.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import memory.promotion
from memory.claims import MemoryClaim
from memory.confidence import accumulated_confidence

_TS = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _claim(*, count: int = 1, base: float = 0.5) -> MemoryClaim:
    claim = MemoryClaim.new_candidate(
        agent_id="a1", subject="cafe", text="me gusta el cafe negro",
        source_conversation_id="conv-1", confidence=base)
    claim.reinforcement_count = count
    claim.source_conversation_ids = [f"conv-{i}" for i in range(1, count + 1)]
    return claim


def test_es_monotona_en_refuerzos_distintos():
    scores = [accumulated_confidence(_claim(count=n)) for n in (1, 2, 3, 7)]
    assert scores == sorted(scores), "más evidencia, nunca menos"
    assert scores[-1] > scores[0]


def test_no_muta_la_confianza_base():
    claim = _claim(count=5)
    antes = claim.confidence
    accumulated_confidence(claim)
    assert claim.confidence == antes, "[D-09]: la base queda fija, la derivada se recalcula"


def test_decae_con_el_tiempo_con_la_misma_vida_media():
    claim = _claim(count=3)
    ahora = datetime.now(timezone.utc)
    fresco = accumulated_confidence(claim, now=ahora)
    viejo = accumulated_confidence(
        claim, now=ahora + timedelta(days=claim.decay_half_life_days))

    assert viejo < fresco
    assert abs(viejo - fresco / 2) < 0.01, "una vida media = mitad de la cifra"


def test_vida_media_indefinida_no_decae():
    claim = _claim(count=3)
    claim.decay_half_life_days = 0
    en_un_anio = accumulated_confidence(
        claim, now=datetime.now(timezone.utc) + timedelta(days=365))
    assert en_un_anio == accumulated_confidence(claim)


def test_la_evidencia_se_tope_a_1():
    claim = _claim(count=500)
    assert accumulated_confidence(claim) <= 1.0


def test_no_es_gate_de_promocion():
    """La promoción sigue decidiéndola el evaluador estructural: el módulo
    de promoción no consume la confianza acumulada ([D-09] literal)."""
    fuente = Path(memory.promotion.__file__).read_text(encoding="utf-8")
    assert "accumulated_confidence" not in fuente
    assert "memory.confidence" not in fuente


def test_el_termino_diversidad_es_un_hook_inactivo_por_defecto():
    """Hallazgo T-05: hoy diversidad == contador, así que w_diversidad=0
    evita contar dos veces la misma señal. El hook existe para cuando el
    modelo separe confirmación explícita de repetición."""
    claim = _claim(count=4)
    ahora = datetime.now(timezone.utc)  # now fijo: las dos llamadas comparan igual
    assert accumulated_confidence(claim, now=ahora) == accumulated_confidence(
        claim, now=ahora, w_diversidad=0.0)
    assert accumulated_confidence(claim, now=ahora, w_diversidad=0.05) > \
        accumulated_confidence(claim, now=ahora)
