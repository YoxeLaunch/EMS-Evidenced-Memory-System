"""Extracción de candidatos T0 → T1 — `docs/01-MEMORIA-NIVELADA.md`.

Determinista y estructural, no basado en LLM — mismo criterio que llevó a
Magnus a empezar `citation_evaluator.py` sin LLM-as-judge
(`docs/02-COMPONENTES-REUTILIZABLES.md`). Un extractor demasiado libre desde
el principio introduce el mismo riesgo que se está tratando de evitar:
alucinar candidatos que no se dijeron.

Solo se extrae de turnos del usuario (`role == "user"`) con uno de cuatro
marcadores explícitos, y nunca de preguntas:

  1. **Corrección directa** — la frase empieza con una marca de corrección
     explícita ("corrijo:", "en realidad,", "de hecho,", "me equivoqué,").
  2. **Confirmación explícita** — el turno es una afirmación corta de una
     lista cerrada ("sí", "correcto", "así es", "exacto", ...) que responde a
     una AFIRMACIÓN previa del asistente (no a una pregunta). El candidato es
     el enunciado del asistente que el usuario acaba de confirmar.
  3. **Cambio de estado** — la frase empieza con "ya no", "dejé de" o
     "ahora" (Fase B de `docs/04-PLAN-MEJORAS.md`): es el ejemplo canónico de
     `docs/01-MEMORIA-NIVELADA.md` ("ya no como carne" tras "como carne
     todos los días"), que antes no producía candidato. "ahora" solo cuenta
     si lo que sigue es una declaración reconocible — "ahora bien, eso es
     otro tema" es discurso, no un cambio declarado.
  4. **Declaración en primera persona** — la frase empieza con un verbo de
     primera persona de una lista cerrada ("soy", "tengo", "vivo en",
     "prefiero", "me gusta", "como", ...).

Ninguna inferencia sobre lo que "probablemente" quiso decir el usuario: si
la frase no calza con un marcador de la lista, no produce candidato. Eso es
lo que valida el criterio de hecho de la Fase 2 (`docs/03-ROADMAP.md`): cero
candidatos alucinados antes de medir cobertura.
"""
from __future__ import annotations

import re

from memory.claims import MemoryClaim
from memory.capture import ConversationRecord, Turn

#: Interrogativos usados para detectar preguntas SIN "?" al final. Con
#: acento y sobre el texto ORIGINAL (no el normalizado sin acentos): "cómo"
#: (pregunta) y "como" (verbo, primera persona de "comer") son la MISMA
#: palabra una vez que se le quitan los acentos, y "como carne todos los
#: días" es justo el ejemplo canónico de declaración en primera persona de
#: `docs/01-MEMORIA-NIVELADA.md`. Sin el acento como señal, cualquier frase
#: que empiece con "como" se leería como pregunta y bloquearía ese caso. El
#: costo es no detectar como pregunta un "como..." interrogativo escrito sin
#: tilde y sin signo "?" — un caso que además ya cubre la comprobación de
#: puntuación (`?` o `¿`) en la inmensa mayoría de veces.
_INTERROGATIVOS_CON_ACENTO = (
    "qué", "cómo", "cuándo", "dónde", "por qué", "cuál", "quién", "cuánto",
)

_MARCADORES_CORRECCION = (
    "corrijo:", "corrección:", "correccion:", "en realidad,", "de hecho,",
    "me equivoqué,", "me equivoque,", "no es así,", "no es asi,",
)

#: Verbos/frases de primera persona. Cada uno debe aparecer al INICIO de la
#: frase (con o sin "no " delante) para contar como declaración — en medio
#: de la frase es demasiado ambiguo para un extractor determinista.
_MARCADORES_PRIMERA_PERSONA = (
    "soy", "tengo", "vivo en", "trabajo en", "me llamo", "mi nombre es",
    "prefiero", "me gusta", "odio", "amo", "quiero", "como", "necesito",
)

#: Marcadores de cambio de estado (Fase B), en forma NORMALIZADA (sin
#: acentos): "dejé de" → "deje de", "dejó de" → "dejo de". Los de cesación
#: califican solos — "ya no como carne" es un cambio declarado pase lo que
#: siga. "ahora" es más débil como marcador discursivo ("ahora bien...") y
#: por eso exige además una declaración reconocible tras él (ver
#: `_candidato_cambio`).
_MARCADORES_CESACION = ("ya no", "deje de", "dejo de")
_MARCADORES_CAMBIO = _MARCADORES_CESACION + ("ahora",)

#: Formas normalizadas (sin acentos, sin puntuación) — la comparación en
#: `_es_confirmacion` normaliza el turno de la misma manera antes de comparar.
_CONFIRMACIONES = {
    "si", "correcto", "asi es", "exacto", "confirmado",
    "eso es", "si correcto", "exactamente",
}

CONFIDENCE_CORRECCION = 0.60
CONFIDENCE_CONFIRMACION = 0.70
#: Un cambio de estado declarado ("ya no...", "dejé de...") es una corrección
#: del mundo por parte del usuario — misma clase epistémica que una corrección
#: directa, no una declaración cualquiera.
CONFIDENCE_CAMBIO = 0.60
CONFIDENCE_PRIMERA_PERSONA = 0.50

_STOPWORDS_SUJETO = {
    "no", "de", "la", "el", "en", "y", "a", "los", "las", "un", "una", "que",
    "con", "por", "para", "del", "al", "se", "su", "sus", "mi", "tu", "yo",
    "me", "te", "le", "lo", "es", "soy", "estoy",
}


def _normalizar_sin_acentos(s: str) -> str:
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return t.lower().strip()


def _empieza_con(o_norm: str, marcadores: tuple[str, ...]) -> bool:
    """¿`o_norm` (YA normalizado) empieza con alguno de los marcadores,
    como palabra completa?"""
    return any(o_norm == m or o_norm.startswith(m + " ") for m in marcadores)


def _strip_cambio(o_norm: str) -> str:
    """Quita hasta dos prefijos de cambio de estado ("ahora ya no como
    carne" → "como carne"). Solo sobre texto YA normalizado; devuelve el
    texto sin cambios si no hay prefijo."""
    for _ in range(2):
        for marcador in _MARCADORES_CAMBIO:
            if o_norm == marcador or o_norm.startswith(marcador + " "):
                o_norm = o_norm[len(marcador):].strip()
                break
    return o_norm


def _es_pregunta(oracion: str) -> bool:
    o = oracion.strip()
    if o.endswith("?") or "¿" in o:
        return True
    o_lower = o.lower()
    return any(o_lower.startswith(q + " ") or o_lower == q for q in _INTERROGATIVOS_CON_ACENTO)


def _oraciones(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?])\s+|\n+", texto.strip())
    return [p.strip() for p in partes if p.strip()]


def _sujeto_desde(texto_restante: str) -> str:
    """Primera palabra de contenido tras quitar el marcador — heurística
    determinista, no NLP: sin sujeto claro, el sujeto es el texto entero."""
    tokens = _normalizar_sin_acentos(texto_restante).split()
    for t in tokens:
        t_limpio = t.strip(".,;:!¡")
        if t_limpio and t_limpio not in _STOPWORDS_SUJETO:
            return t_limpio
    return _normalizar_sin_acentos(texto_restante) or texto_restante


def _sujeto_para_texto(texto: str) -> str:
    """Sujeto de CUALQUIER texto candidato, reconociendo un marcador de
    primera persona embebido si lo hay ("vivo en Santiago" → "santiago", no
    "vivo"). Se usa tanto para declaraciones directas como para el texto que
    queda tras una corrección o una confirmación — así "vivo en Santo
    Domingo" y "en realidad, vivo en Santiago" producen el MISMO subject
    ("santo"/"santiago" en este caso vienen del resto tras el marcador) y la
    corrección puede encontrar y suceder al claim original en vez de crear
    uno sin relación.

    Los prefijos de cambio de estado también se quitan antes de buscar el
    marcador: "en realidad, ya no como carne" debe dar subject "carne", no
    "ya" — mismo subject que "como carne todos los días" para que la
    sucesión los encuentre.
    """
    o_norm = _strip_cambio(_normalizar_sin_acentos(texto))
    cuerpo = o_norm[3:] if o_norm.startswith("no ") else o_norm
    for marcador in _MARCADORES_PRIMERA_PERSONA:
        if cuerpo == marcador or cuerpo.startswith(marcador + " "):
            resto = cuerpo[len(marcador):].strip()
            return _sujeto_desde(resto) if resto else marcador
    return _sujeto_desde(texto)


def _candidato_correccion(oracion: str) -> tuple[str, str] | None:
    o_norm = _normalizar_sin_acentos(oracion)
    for marcador in _MARCADORES_CORRECCION:
        if o_norm.startswith(marcador):
            resto = oracion[len(marcador):].strip()
            if not resto:
                return None
            return _sujeto_para_texto(resto), resto
    return None


def _candidato_cambio(oracion: str) -> tuple[str, str] | None:
    """Candidato por cambio de estado declarado (Fase B): "ya no como
    carne", "dejé de fumar", "ahora vivo en Santiago".

    El texto del claim conserva la oración COMPLETA (el "ya no" es parte del
    significado); el subject se deriva del resto tras el prefijo, alineado
    con la declaración original que corrige. "ahora" solo califica si lo que
    sigue es una declaración reconocible — ver `_MARCADORES_CESACION`.
    """
    o_norm = _normalizar_sin_acentos(oracion)
    resto = _strip_cambio(o_norm)
    if resto == o_norm or not resto:
        return None
    es_cesacion = _empieza_con(o_norm, _MARCADORES_CESACION)
    if not es_cesacion and _candidato_primera_persona(resto) is None:
        return None
    return _sujeto_para_texto(resto), oracion.strip()


def _candidato_primera_persona(oracion: str) -> tuple[str, str] | None:
    o_norm = _normalizar_sin_acentos(oracion)
    prefijo_no = o_norm.startswith("no ")
    cuerpo = o_norm[3:] if prefijo_no else o_norm
    for marcador in _MARCADORES_PRIMERA_PERSONA:
        if cuerpo == marcador or cuerpo.startswith(marcador + " "):
            return _sujeto_para_texto(oracion), oracion.strip()
    return None


def _es_confirmacion(oracion: str) -> bool:
    o_norm = _normalizar_sin_acentos(oracion)
    o_norm = re.sub(r"[.,;:!¡¿?]", "", o_norm)
    o_norm = re.sub(r"\s+", " ", o_norm).strip()
    return o_norm in _CONFIRMACIONES


def extract_candidates(
    record: ConversationRecord, *, decay_half_life_days: int = 180,
) -> list[MemoryClaim]:
    """Extrae candidatos T1 de un `ConversationRecord` (T0).

    Devuelve una lista de `MemoryClaim` con `tier=T1`, `reinforcement_count=1`
    y `source_conversation_ids=[record.id]`. No hace deduplicación contra
    claims existentes — eso es `memory/dedup.py`, deliberadamente separado
    para poder probar la extracción sola sin un store de por medio.
    """
    candidatos: list[MemoryClaim] = []
    turnos = list(record.turns)

    for i, turno in enumerate(turnos):
        if turno.role != "user":
            continue

        for oracion in _oraciones(turno.content):
            if _es_pregunta(oracion):
                continue

            correccion = _candidato_correccion(oracion)
            if correccion is not None:
                sujeto, texto = correccion
                candidatos.append(MemoryClaim.new_candidate(
                    agent_id=record.agent_id, subject=sujeto, text=texto,
                    source_conversation_id=record.id,
                    confidence=CONFIDENCE_CORRECCION,
                    decay_half_life_days=decay_half_life_days))
                continue

            if _es_confirmacion(oracion):
                previo = _asistente_anterior(turnos, i)
                if previo is not None and not _es_pregunta(previo):
                    sujeto = _sujeto_para_texto(previo)
                    candidatos.append(MemoryClaim.new_candidate(
                        agent_id=record.agent_id, subject=sujeto, text=previo.strip(),
                        source_conversation_id=record.id,
                        confidence=CONFIDENCE_CONFIRMACION,
                        decay_half_life_days=decay_half_life_days))
                continue

            cambio = _candidato_cambio(oracion)
            if cambio is not None:
                sujeto, texto = cambio
                candidatos.append(MemoryClaim.new_candidate(
                    agent_id=record.agent_id, subject=sujeto, text=texto,
                    source_conversation_id=record.id,
                    confidence=CONFIDENCE_CAMBIO,
                    decay_half_life_days=decay_half_life_days))
                continue

            primera_persona = _candidato_primera_persona(oracion)
            if primera_persona is not None:
                sujeto, texto = primera_persona
                candidatos.append(MemoryClaim.new_candidate(
                    agent_id=record.agent_id, subject=sujeto, text=texto,
                    source_conversation_id=record.id,
                    confidence=CONFIDENCE_PRIMERA_PERSONA,
                    decay_half_life_days=decay_half_life_days))

    return candidatos


def _asistente_anterior(turnos: list[Turn], indice_usuario: int) -> str | None:
    """El texto del turno del asistente inmediatamente anterior, si existe."""
    if indice_usuario == 0:
        return None
    anterior = turnos[indice_usuario - 1]
    if anterior.role != "assistant":
        return None
    return anterior.content
