# Roadmap — EMS (Evidenced Memory System)

Fases pensadas para poder cerrarse de forma independiente y verificable,
siguiendo el mismo principio de orden que `MagnusAgent/ROADMAP.md`: no abrir
la fase siguiente sin criterio de hecho cumplido en la anterior. Añadir
memoria y aprendizaje sobre una base sin tests ni auditoría multiplica el
costo de arreglarla después — más aún aquí, donde el sistema escribe su
propia fuente de verdad.

## Fase 0 — Empaquetado y vendorización de infraestructura

**Qué hacer:**
- `git init`, `pyproject.toml` propio, `pytest` como runner.
- Vendorizar/portar, en el orden de `02-COMPONENTES-REUTILIZABLES.md`:
  `ProviderRegistry`, `RAGPipeline` + `HashingEmbedder` + `InMemoryVectorStore`,
  `PermissionEngine`, política de privacidad, `orchestration/audit.py`
  adaptado.
- Fixtures offline (proveedor fake, sin red ni credenciales en tests) — mismo
  patrón que `conftest.py` de Magnus, que borra del entorno cualquier clave
  de proveedor real.

**Criterio de hecho:** en un checkout limpio, sin credenciales, `pytest`
corre en verde con la infraestructura portada cubierta por tests de
integración mínimos (no hay memoria nivelada todavía, solo la base).

## Fase 1 — Captura (T0) con privacidad desde el diseño

**Qué hacer:**
- Registro de conversación cruda, con la política de egreso denegado por
  defecto ya activa (principio 5) desde el primer dato guardado — no
  añadirla después.
- Consentimiento explícito de qué se guarda; sin eso, no hay materia prima
  para ningún nivel posterior.

**Criterio de hecho:** una conversación se guarda como T0 con proveniencia
completa (quién, cuándo, con qué agente) y ningún dato sale del dispositivo
sin política explícita que lo autorice.

## Fase 2 — Extracción de candidatos (T1)

**Qué hacer:**
- Extractor determinista y estructural (marcadores explícitos: correcciones,
  confirmaciones, declaraciones en primera persona) — no basado en LLM
  todavía, mismo criterio que llevó a Magnus a empezar el evaluador de citas
  sin LLM-as-judge.
- Deduplicación contra claims existentes usando el `HashingEmbedder` portado.

**Criterio de hecho:** un set de conversaciones de prueba con marcadores
conocidos produce los `MemoryClaim` T1 esperados, sin falsos candidatos
inventados por inferencia libre. Tests dedicados a "cero candidatos
alucinados" antes de medir cobertura.

## Fase 3 — Refuerzo y sucesión (T1 → T2)

**Qué hacer:**
- Tracking de `reinforcement_count` por repetición entre conversaciones
  distintas (nunca dentro de la misma).
- Confirmación explícita del usuario como vía alterna de refuerzo.
- Detección de contradicción explícita + creación de relación
  `supersedes`/`superseded_by` — nunca sobrescritura.

**Criterio de hecho:** un claim reforzado tres veces en conversaciones
distintas asciende a T2; un claim que contradice a otro T2 activo genera
sucesión trazable, ambos siguen siendo consultables con su estado correcto
(`active` / `superseded`).

## Fase 4 — Evaluador de promoción (T2 → T3)

**Qué hacer:**
- Evaluador estructural determinista (patrón de `citation_evaluator.py`):
  consistencia entre conversaciones, diversidad de procedencia, ausencia de
  contradicción con T3 activos.
- Ruta de confirmación humana obligatoria para dominios de alto riesgo,
  configurable por agente igual que `guardrails.yaml` en Magnus.
- Puerto `Evaluator` como `Protocol`, para que un LLM-as-judge se pueda
  enchufar más adelante sin tocar el pipeline.

**Criterio de hecho:** un claim T2 con refuerzo suficiente y sin contradicción
se promueve a T3 solo, y uno con contradicción activa se bloquea con el
motivo registrado; un dominio marcado de alto riesgo nunca promueve sin
confirmación humana, verificado por test.

## Fase 5 — Recuperación integrada

**Qué hacer:**
- `RAGPipeline` consumiendo `MemoryClaim` T2/T3 activos como documentos
  indexables, junto con cualquier fuente curada opcional (T3 desde el día
  uno, si existe).
- El evaluador de respuesta final aplica el umbral correcto según el tier de
  cada claim recuperado, y la respuesta marca visiblemente cuándo se apoyó
  en T2 (confianza media) frente a T3 (autoridad plena).

**Criterio de hecho:** una consulta real recupera claims de ambos niveles
cuando existen, y la respuesta distingue explícitamente su nivel de
confianza — nunca presenta un T2 con la misma seguridad que un T3.

## Fase 6 — Caducidad y retención

**Qué hacer:**
- Scheduler de decaimiento por `decay_half_life_days`, con `status=expired`
  cuando la confianza efectiva cae bajo el umbral del nivel.
- Retención/rotación del registro de auditoría — deuda que Magnus dejó
  abierta (`MagnusAgent/docs/06-ANALISIS-MEJORAS-SEGURIDAD.md`, punto 2):
  resolverla aquí desde el diseño, no como parche posterior.

**Criterio de hecho:** un claim sin refuerzo reciente deja de recuperarse
como evidencia activa pero conserva su historial; el registro de auditoría
tiene una política de retención configurable, no crecimiento sin límite.

## Fase 7 — Piloto acotado

**Qué hacer:**
- Un solo agente, un dominio acotado y de riesgo medio-bajo (no médico ni
  financiero en el primer piloto), corriendo el pipeline completo T0→T3
  durante un periodo de prueba real con conversaciones genuinas.
- Medir, igual que Magnus midió su banco de recuperación y enrutado antes de
  fijar defaults: tasa de candidatos correctos, tasa de falsas promociones
  detectadas después (si las hay), tiempo medio hasta primera promoción.

**Criterio de hecho:** al menos un claim T3 promovido a partir de
conversaciones reales, con su cadena completa de proveniencia auditable
desde T0 hasta la promoción, y ningún caso detectado de T1 citado con
autoridad de T3 durante el piloto.

## No empezar el resto sin cerrar 0-4

Los pasos 5-7 dependen de que el pipeline de niveles (0-4) sea correcto y
esté cubierto por tests — exactamente el mismo principio de orden que
`MagnusAgent/ROADMAP.md` aplicó a su propio circuito principal. Recuperación,
caducidad y piloto sobre un pipeline de promoción que no se ha verificado
multiplican el costo de encontrar después que algo se promovió sin deberlo.
