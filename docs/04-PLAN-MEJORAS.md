---
titulo: "Plan de Mejoras — EMS (Evidenced Memory System) v0.2"
tipo: diseno_tecnico
estado: propuesto_para_revision
fecha: 2026-08-16
redactado_por: ZCode (agente de implementación)
revisado_por: pendiente — ChatGPT (contraparte de diseño) + decisión humana final
padre: docs/00-VISION-Y-ARQUITECTURA.md
hermano: docs/03-ROADMAP.md
---

# Plan de Mejoras — EMS (Evidenced Memory System)

## 0. Cómo revisar este documento

- Audiencia: revisión de diseño por un segundo ingeniero antes de implementar.
- Las preguntas abiertas están marcadas **[P-nn]**. Las respuestas se registran en
  `COLABORACION.md` (raíz del repo), no editando este archivo.
- Cada fase cierra con un **criterio de hecho**: condición verificable, misma
  convención que `docs/03-ROADMAP.md`.
- Regla de orden heredada del ROADMAP: no abrir una fase sin cerrar sus
  dependencias.

## 1. Resumen ejecutivo

EMS tiene Fases 0-6 completas y en verde: el pipeline de memoria nivelada
T0→T3 es funcional y testeado, pero vive dentro de sus propios tests. Los gaps
identificados por la auditoría del 2026-08-16 son: sin persistencia de claims,
sin superficie pública, dos grietas en el anti-eco, cero integración con
consumidores reales (MAS, wiki), y sin medición.

Este plan organiza el cierre en 7 fases (A→G) que culminan en el circuito
completo del ecosistema:

> conversación → memoria nivelada → wiki curada → dominio verificable por
> niveles ("Camino de Aprendizaje").

## 2. Decisiones de diseño ya tomadas [D-nn]

Estas decisiones se consideran cerradas salvo que la revisión las reabra con
argumento:

- **[D-01] Dos ejes, nunca mezclados.** La confianza epistémica (T0-T3,
  "¿con qué autoridad afirmo esto?") y el dominio ("¿qué nivel de comprensión
  representa?") son ortogonales. Subir de nivel de dominio jamás otorga
  confianza; ganar confianza jamás implica profundidad. El eje dominio usa la
  taxonomía de Bloom por ser medible por conducta (recordar → entender →
  aplicar → analizar → evaluar → crear), mapeado informalmente a
  secundaria/universitario/maestría/doctorado.
- **[D-02] La heurística determinista es el suelo.** El LLM (Fase E) solo
  amplifica cobertura de extracción y juzga promociones *después* del evaluador
  estructural, nunca en su lugar. Sin API keys el sistema debe comportarse
  exactamente igual que hoy.
- **[D-03] Append-only en todo.** Claims con sucesión, eventos como log
  inmutable. Ningún UPDATE que borre rastro (principio 2 de `docs/00`).
- **[D-04] Local-first.** SQLite y stdlib únicamente; ninguna dependencia
  nueva sin decisión explícita registrada.
- **[D-05] La wiki es nivel máximo de confianza, no de dominio.** Una nota de
  wiki aporta autoridad plena (T4) sea cual sea su profundidad.

## 3. Fases

### Fase A — Cimientos (bloquea todo lo demás)

**A1. `SqliteClaimStore`** (tamaño M)
Sustituye `memory/store.py:12-51` (dict en RAM) preservando el contrato.
Esquema propuesto:
- Tabla `claims` (columnas = campos de `MemoryClaim`, `memory/claims.py:56-71`).
- Tabla `events` append-only: `(ts, tipo, claim_id, payload_json)` con tipos
  `extraction|reinforcement|promotion|supersession|expiration|wiki_sync` —
  los mismos que `orchestration/audit.py:122-128` ya documenta y nadie emite.
- WAL mode, un solo writer (ems es single-process por diseño).
- Los claims son regenerables desde T0 JSONL; los **events no** — son la
  cadena de custodia. El backupprioriza events.
- Ver [P-01], [P-02].

**A2. Índice de recuperación persistente** (M)
Hoy `memory/retrieval.py:99-135` re-fitea el embedder y re-embedde todos los
T2/T3 en cada consulta. Con SQLite: tabla `embeddings (claim_id, vector,
embedder_version)`, escritura al persistir el claim, invalidación solo del
claim modificado. `build_tiered_context` pasa de O(n) a O(1) amortizado.

**A3. Superficie pública** (S)
- Exports en `memory/__init__.py` (hoy 0 bytes): `record_conversation`,
  `extract_candidates`, `reinforce_or_create`, `promote_to_t3`,
  `build_tiered_context`, `SqliteClaimStore`, `expire_stale_claims`.
- CLI `ems` (console_script en `pyproject.toml`):
  `ems stats | capture | reinforce | promote | export`.
- Ver [P-03].

**A4. Auditoría cableada** (S)
Emitir eventos a la tabla `events` desde extracción/refuerzo/promoción/
sucesión/decay, además del `JsonlTraceStore` existente si está configurado.
Cada promoción T3 debe poder reconstruir su cadena T0→T3 desde la DB.

**Criterio de hecho de la Fase A:** matar el proceso, reabrir, y los claims
persisten con su historial completo; `ems stats` reporta claims por nivel;
una promoción ejecutada en una sesión anterior es trazable evento a evento.

### Fase B — Corrección epistémica (protege la garantía mientras escala)

**B1. Contradicción contra T1 + marcadores de cambio** (M)
- Extender `detect_contradiction` (`memory/reinforcement.py:46-56`) para
  comprobar también contra claims T1 activos. Hoy una negación de un T1, por
  coseno ≈ 1.0, **refuerza a su opuesto** — la grieta más seria del anti-eco.
- Añadir marcadores "ya no", "dejé de", "ahora" a `memory/extraction.py` para
  que generen candidato de corrección. El ejemplo canónico de `docs/01:139-140`
  ("ya no como carne") debe funcionar end-to-end.

**B2. Confianza acumulativa** (M)
Hoy `confidence` es casi decorativo (constantes fijas, `max()` sin acumular en
`reinforcement.py:107`). Propuesta base:
`confidence_efectiva = base + w1·log(1 + refuerzos_extra) + w2·diversidad_conversaciones`
sobre la que ya calcula `effective_confidence` (`memory/decay.py:42-51`).
Requiere calibrar con los datos del piloto. Ver [P-04].

**B3. Tests de regresión canónicos** (S)
Todos los ejemplos de `docs/01` deben existir como tests que pasan. Hoy al
menos uno no funciona end-to-end.

**Criterio de hecho de la Fase B:** negar un T1 produce sucesión, no refuerzo;
"ya no como carne" tras "como carne todos los días" genera cadena
`supersedes/superseded_by`; suite verde incluyendo los canónicos.

### Fase C — Interop con el MAS (primer consumidor real)

**C1. Adaptador `EMSMemoryEngine`** (L)
Implementa el puerto `MemoryEngine` de Magnus
(`MagnusAgent/orchestration/memory/memory_engine.py`) como módulo puente
(propuesto: `integration/magnus_bridge.py`). Mapeo:

| MAS (puerto) | EMS |
|---|---|
| `short_term.recall` | turnos de sesión (T0 en RAM) |
| `long_term.recall` | `build_tiered_context` (etiquetas confianza_media/autoridad_plena ya diseñadas para prompt) |
| `semantic.propose/approve` | candidato T1 → promoción T3 (P7 ya implementado) |
| `episodic` | `ConversationRecord` T0 persistido |

Ver [P-05].

**C2. `session_id`/`user_id` en `magnus_ask`** (S, lado Magnus)
~5 líneas en `MagnusAgent/mcp_server/protocol.py:138-146` +
`call_tool()`. `engine.ask()` ya los soporta.

**C3. Ciclo de vida** (S)
- Al cerrar sesión MCP: `record_conversation` → `extract_candidates` →
  `reinforce_or_create` (batch).
- Al arrancar el servidor: `expire_stale_claims` como mantenimiento.

**Criterio de hecho de la Fase C:** una sesión MCP real contra un agente Magnus
produce claims T1 visibles en `ems stats`; turnos posteriores de la misma
 sesión reciben contexto T2/T3 etiquetado; cero casos de T1 citado como T3.

### Fase D — Puente bidireccional con la wiki

**D1. `WikiSource` — la wiki como T4** (M)
Ingieren notas Markdown con frontmatter como claims `tier=T4`, nivel máximo:
no decaen (`decay_half_life_days <= 0` ya existe en `claims.py:70`),
`knowledge_version = wiki:<snapshot>` (mismo versionado por hash de Magnus).
Un T4 contradictorio con un T3 **gana por diseño** y genera alerta
"la conversación contradice la wiki". Ver [P-06].

**D2. Exportador T3 → borrador de nota** (M)
Claims T3 promovidos de un mismo subject se compilan a un Markdown con
frontmatter (`origen: ems`, `evidencia: [conversation_ids]`,
`promovido: fecha`) en una carpeta de staging — **nunca escribe la wiki
directamente**. El humano cura y al aprobar se ingiere como T4. Es el
mecanismo del nivel "doctorado" del Camino y el autoabastecimiento del
segundo cerebro.

**D3. Egresos alineados** (M)
`agent_id`/`subject` de EMS ↔ namespaces de la wiki/Magnus, para que la
política de egreso aplique por claim (un claim de salud jamás sale del
dispositivo, hereda el `local_only` de su dominio).

**Criterio de hecho de la Fase D:** una nota wiki aparece como T4 sin decay y
responde con `knowledge_version` correcto; un T3 promovido genera borrador en
staging con su evidencia; contradicción T3↔T4 produce alerta y no sobrescribe.

### Fase E — Inteligencia opcional (LLM)

**E1. Adaptador `AnthropicProvider`** (S) — portar el de Magnus (testeado
allí); el extra `anthropic` ya está declarado en `pyproject.toml`.

**E2. Extractor asistido por LLM** (M) — `docs/01:93-96` ya lo postula:
el LLM propone candidatos con `confidence` inferior al marcador determinista,
mismo pipeline de refuerzo/promoción. Amplía cobertura (hoy solo frases que
arrancan con listas cerradas) sin tocar la garantía.

**E3. `LLMJudgePromotionEvaluator`** (M) — puerto `Evaluator`
(`memory/promotion.py:45-49`) + patrón fail-closed probado en Magnus
(`LLMJudgeEvaluator`): si el juez cae o no parsea, la promoción no pasa.
Siempre **después** del estructural, como segundo gate.

**Criterio de hecho de la Fase E:** sin API keys, todo el suite pasa idéntico
(degradación total a heurística, cero cambios de comportamiento); con keys, la
tasa de extracción sube medible en `ems stats` sin que cambie ningún
criterio de promoción estructural.

### Fase F — Camino de Aprendizaje (dominio verificable)

**F1. Esquema `curriculum.yaml`** (L)
Por dominio: temas con prerrequisitos (DAG), fuentes (namespaces wiki, libros
`raw/`), goldens por nivel Bloom, criterio de aprobación. Declarativo,
versionado, validable — misma filosofía que `agent.yaml` en Magnus.
Ver [P-07].

**F2. Examen de dominio** (M)
Subconjunto de goldens del tema → recuperación + `CitationEvaluator` (o el
evaluador de Magnus) → nivel alcanzado, anclado al `snapshot` de la wiki con
que se examinó. El expediente es auditable por construcción.

**F3. Expediente** (M)
Tabla `progress (tema, nivel, snapshot, fecha, resultado)`. El decaimiento de
dominio reusa `decay`: un tema sin repaso baja confianza efectiva y el Camino
lo marca "a repasar" — repetición espaciada gratis con lo existente.

**F4. Ingesta `raw/` → nivel recordar/entender** (L)
Pipeline libro → troceado → notas de nivel básico → goldens generados del
propio texto con validación humana. Los 483 MB de `raw/` en BRAIN son el
combustible sin quemar; `wiki/index.md` ya documenta qué libro cubre qué
concepto.

**Criterio de hecho de la Fase F:** un dominio (economía, candidato natural)
completa el ciclo: libro ingerido → nota básica → examen aprobado con citas →
nivel registrado en expediente → decaimiento por desuso visible.

**Advertencia de scope:** esta fase es la más propensa a sobre-ingeniería.
Solo se abre con D1+D2 cerradas y empezando por UN dominio.

### Fase G — Operación

- **G1. `ems stats` extendido** (S): claims por nivel, tasa de promoción,
  edad mediana, contradicciones pendientes, próximos a caducar — telemetría
  del piloto.
- **G2. Derecho al olvido** (M): purga por `user_id`/`subject` de claims Y sus
  T0 asociados (con SQLite deja de ser difícil).
- **G3. Portabilidad** (S): export/import del store como archivo único
  (claims + events + conversaciones referenciadas).
- **G4. Memoria multi-agente** (M): claims compartidos con visibilidad
  restringida por namespace (el agente de finanzas no cita memoria de salud).
- **G5. CI** (S): pytest + gates estilo bench de Magnus (exit ≠ 0 si empeora).

## 4. Orden y dependencias

```
A (cimientos) ──► B (anti-eco) ──► C (MAS) ──► D (wiki) ──► F (Camino)
                        │                        ▲
                        └──── E (LLM, paralelo a C/D) ──┘
G1-G3 pueden colarse en cualquier momento tras A; G4 tras C; G5 ya.
```

Recomendado: **A → B → C → D → (E en paralelo) → F → G**. El piloto de Fase 7
de `docs/03` se ejecuta con C cerrada; F no se toca antes de D.

## 5. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Scope creep del Camino (F) | Un solo dominio, gate de entrada D1+D2 |
| Contradicción semántica perfecta es problema abierto | Incremental: T1 + marcadores primero; medir en piloto |
| Umbral dedup 0.55 sin calibrar | Telemetría G1 + datos del piloto antes de moverlo |
| Deriva documental (lección MagnusAgent) | Este doc se marca obsoleto por entrada en COLABORACION.md, no se edita en silencio |
| Doble escritor SQLite si MAS y CLI corren a la vez | [P-01]: single-process por diseño o queue |

## 6. Preguntas abiertas para la revisión

- **[P-01]** SQLite: ¿WAL + single-writer basta, o anticipamos acceso
  concurrente desde el proceso MAS y el CLI simultáneamente (cola/queue)?
- **[P-02]** ¿Tabla `events` en SQLite o JSONL append-only (consistente con
  T0 y trazas de Magnus) con SQLite solo para claims?
- **[P-03]** ¿API pública como exports de `memory/__init__` o paquete
  agregador `api.py`/`ems/` nuevo?
- **[P-04]** Fórmula de confianza acumulativa: ¿suma logarítmica propuesta, o
  esquema tipo Beta-Bernoulli (cada refuerzo un éxito, prior según origen)?
- **[P-05]** ¿El bridge MAS vive en EMS (`integration/`) o en Magnus como
  dependencia opcional? Implica quién rompe si cambia el puerto.
- **[P-06]** ¿T4 como valor nuevo del enum `Tier` (rompe `match` exhaustivos)
  o como `status/source` especial fuera del enum de conversación?
- **[P-07]** ¿Currículo en YAML puro, o Markdown+frontmatter (mismo formato
  que la wiki, un solo parser)?
- **[P-08]** ¿Arrancar F-economía con los 3 libros ya sintetizados en la wiki
  (Mankiw/CORE/OpenStax, notas ya existen) o exigir pipeline raw/ primero?

## 7. Vínculo con el piloto (Fase 7 de docs/03)

Todo lo anterior converge en el piloto: un agente Magnus real, dominio de
riesgo medio-bajo, 2-4 semanas de conversaciones genuinas. Métricas del
criterio de éxito (ya definidas en `docs/03:116-123`): tasa de candidatos
correctos, tasa de falsas promociones, tiempo hasta primer T3, cero T1 citado
como T3, cadena T0→promoción auditable.
