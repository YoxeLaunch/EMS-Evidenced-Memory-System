"""Confianza acumulativa derivada — B2 / T-05, decisión [D-09].

La `confidence` base de un claim queda FIJA según el marcador de extracción
(0.50 primera persona, 0.60 corrección/cambio, 0.70 confirmación). Esta
función calcula la confianza DERIVADA de la evidencia acumulada después —
separada por diseño ([D-09]: "fórmula logarítmica separada de la confidence
base"), a partir de los conteos brutos que el claim ya guarda
(`reinforcement_count`, `source_conversation_ids`), sin escribir nada de
vuelta al claim.

**No es un gate.** La promoción T2→T3 la sigue decidiendo el evaluador
estructural (`memory/promotion.py`); esta cifra es telemetría (G1,
`ems stats`) y superficie de consulta — convertir la cifra en evidencia
de promoción sería el eco que el sistema promete evitar.

Fórmula::

    evidencia  = base + w_refuerzo · ln(1 + refuerzos_extra)
                       + w_diversidad · (conversaciones_distintas − 1)
    acumulada  = min(1.0, evidencia) · factor_temporal

`factor_temporal` reusa el decaimiento de `memory/decay.py` (misma vida
media, mismo `last_reinforced_at`) — la evidencia vieja pesa menos aunque
hubiera mucha.

Hallazgo de implementación (documentado en COLABORACION.md, T-05): hoy
`reinforcement_count` y la diversidad de `source_conversation_ids` son la
MISMA señal — el refuerzo solo cuenta en conversación nueva y siempre
empareja el append del id con el incremento del contador. Con el modelo
actual, dos términos sumarían dos veces lo mismo, por eso
`W_DIVERSIDAD = 0.0` por defecto. Cuando el modelo distinga confirmación
explícita de repetición (señales hoy no separadas), el término diversidad
vuelve a tener señal propia y se recalibra.
"""
from __future__ import annotations

import math
from datetime import datetime

from memory.claims import MemoryClaim
from memory.decay import effective_confidence

#: Ganancia por refuerzo en conversación distinta, escala logarítmica:
#: ln(1+n). Sin calibrar con datos reales ([D-09]: calibrar antes de usar
#: como gate — y no se usa como gate). Valor inicial conservador: el primer
#: refuerzo suma ~0.07 sobre una base de 0.50.
W_REFUERZO = 0.10

#: Ver docstring del módulo: 0.0 porque hoy diversidad == contador. Es un
#: hook para la señal separada (confirmación vs repetición), no un término
#: activo.
W_DIVERSIDAD = 0.0


def accumulated_confidence(
    claim: MemoryClaim, *, now: datetime | None = None,
    w_refuerzo: float = W_REFUERZO, w_diversidad: float = W_DIVERSIDAD,
) -> float:
    """Confianza derivada de la evidencia acumulada, decaída por tiempo.

    No muta el claim: la base queda intacta y esta cifra se recalcula
    siempre desde los conteos brutos — mismo principio que
    `effective_confidence`, extendido con la evidencia de refuerzo.
    """
    if claim.confidence <= 0:
        return 0.0
    refuerzos_extra = max(0, claim.reinforcement_count - 1)
    diversidad = max(0, len(set(claim.source_conversation_ids)) - 1)
    evidencia = (claim.confidence
                 + w_refuerzo * math.log1p(refuerzos_extra)
                 + w_diversidad * diversidad)
    factor_temporal = effective_confidence(claim, now=now) / claim.confidence
    return min(1.0, evidencia) * factor_temporal
