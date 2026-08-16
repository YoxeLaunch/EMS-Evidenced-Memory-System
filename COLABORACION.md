# COLABORACION.md — Log compartido de trabajo conjunto

Sistema de colaboración entre dos ingenieros de IA sobre el proyecto EMS (antes Embudo)
(y su integración con MagnusAgent y la wiki BRAIN).

| Rol | Participante | Responsabilidad principal |
|---|---|---|
| Implementador | **ZCode** (agente local, tiene acceso al disco y al código) | Escribir código, ejecutar tests, auditar el estado real del repo |
| Revisor | **ChatGPT** (contraparte de diseño, sin acceso directo al disco) | Revisión crítica de diseño, alternativas, contrapunto |
| Árbitro + transporte | **El humano (JoseO)** | Decide conflictos, mueve bloques de handoff entre sesiones |

## Protocolo

1. **Append-only.** Las entradas se añaden al final, nunca se editan ni se
   borran (misma filosofía que la sucesión de claims). Si una decisión cambia,
   se escribe una entrada nueva que la supersede citándola.
2. **Formato de entrada:**
   ```
   ### YYYY-MM-DD HH:MM — De: <ZCode|ChatGPT|Humano> — <asunto>
   <contenido: decisiones [D-nn], respuestas [P-nn], alternativas [ALT-nn],
   hallazgos, preguntas>
   ```
3. **Numeración global:** decisiones `[D-nn]`, preguntas `[P-nn]`,
   alternativas `[ALT-nn]`, tareas `T-nn`. Nunca se reutilizan números.
4. **Regla de tokens:** nadie re-deriva contexto que ya está aquí o en los
   docs referenciados. Se cita `archivo:linea` en lugar de pegar código.
   Los bloques de handoff son autocontenidos y acotados.
5. **Regla de conflicto:** si ZCode y ChatGPT discrepan, gana el argumento,
   no el autor; si persiste, decide el humano y queda registrado como [D-nn].
6. **Estado de tareas:** la tabla de abajo es la única fuente de verdad de
   quién hace qué. Nadie trabaja una tarea asignada al otro sin entrada
   previa en el log.
7. **Regla de arranque:** al iniciar cualquier sesión, lo primero es leer el
   Tablero de Estado y las entradas nuevas desde la última visita — antes de
   trabajar. Nadie toma una tarea sin refrescar estado.
8. **Regla de checkpoint:** antes de cerrar la sesión, actualizar el Tablero
   de Estado y dejar una entrada breve: qué se hizo, qué queda a medias
   (y dónde quedó exactamente: archivo:linea), y qué se espera del otro.

## Estado de tareas

| ID | Tarea | Dueño | Estado | Notas |
|---|---|---|---|---|
| T-01 | Revisar `docs/04-PLAN-MEJORAS.md`: responder P-01..P-08, proponer ALT | ChatGPT | completada | Revisión registrada 2026-08-16 |
| T-02 | Decisión final sobre P-01..P-08 | Humano | **completada** | [D-06]..[D-13] registradas |
| T-03 | Fase A1 `SqliteClaimStore` + events + `conversation_sources` | ZCode | **completada** | Commit `b81c15a`; 149/149 |
| T-04 | Auditoría de factibilidad Fase F (Camino) | ChatGPT | completada | Incluida en revisión T-01 |
| T-05 | B2: confianza acumulativa (mecanismo separado de la base) | ZCode | **completada** | Commit `bae5372`; **Fase B completa** |
| T-06 | A4: cablear pipeline a events (`reinforce`/`promote`/`decay` emiten) | ZCode | **completada** | Commit `e1a4b42`; 159/159; [D-14] registrada |
| T-07 | A2: índice de recuperación con invalidación por snapshot | ZCode | **completada** | Commit `6915f88`; **Fase A completa** |
| T-08 | A3: API pública `embudo/` + CLI | ZCode | **completada** | Commit `e8e50d0`; v0.2.0 |

## Tablero de estado

> **Excepción mutable:** esta sección es la única parte editable del archivo
> (el registro de abajo sigue siendo append-only). Es el tablero kanban:
> qué hace cada uno AHORA, qué espera, qué está libre. Se actualiza en cada
> checkpoint (regla 8).

| Participante | Trabajando ahora | Esperando de | Libre para tomar |
|---|---|---|---|
| ZCode | — (sesión cerrada: Fases A y B completas) | Humano: abrir Fase C/D/E o piloto | Fase C (bridge en Magnus [D-10]), D (T4 [D-11]) |
| ChatGPT | Seguimiento de plan | — | Revisión de desviaciones A2/T-05 + estado Fase A |
| Humano | — | — | Abrir siguiente fase; pegar checkpoints a ChatGPT |

_Última actualización: 2026-08-16 por ZCode (A2+A3 completas, commits 6915f88 + e8e50d0, 177/177. **Fases A y B completas**.)_

## Registro

### 2026-08-16 — De: ZCode — Entrada inicial: plan redactado, protocolo abierto

Contexto para el revisor (lo mínimo, el detalle está en los docs):

- Embudo tiene Fases 0-6 de su roadmap completas y testeadas (118 tests
  offline, 100% determinista, sin LLM). El pipeline T0→T3 funciona pero solo
  es consumido por sus propios tests: sin persistencia de claims, sin API
  pública, sin consumidores reales.
- La auditoría completa (2026-08-16) identificó los gaps que estructura el
  plan: persistencia, superficie, 2 grietas anti-eco (negación de T1 refuerza
  su opuesto; marcadores "ya no" no funcionan end-to-end), integración MAS,
  puente wiki, y el "Camino de Aprendizaje" (eje de dominio por niveles,
  separado del eje de confianza).
- El plan con las 7 fases (A-G), criterios de hecho, riesgos y las 8
  preguntas abiertas está en `docs/04-PLAN-MEJORAS.md`. Las decisiones ya
  tomadas están marcadas [D-01..D-05] ahí y se consideran cerradas salvo
  argumento en contra.

Solicito al revisor: T-01 (responder P-01..P-08 del plan, con justificación
breve por respuesta, y proponer alternativas [ALT-nn] donde crea que hay un
camino mejor). Formato de entrega: una entrada nueva en este archivo, bajo
el protocolo de arriba.

— fin de la entrada —

### 2026-08-16 — De: ZCode — Checkpoint de cierre: Fase B completa, suite en verde (131/131)

**Qué se hizo** (baseline antes: 116 passed + 2 skipped; después: 131 passed
+ 2 skipped — 15 tests nuevos, cero regresiones):

1. **B1 — contradicción contra T1** (`memory/reinforcement.py:88`): la
   detección de contradicción ahora cubre claims T1 activos, no solo T2/T3.
   Cierra la grieta del anti-eco: una negación temprana ("no como carne"
   contra un "como carne" aún en T1) antes matcheaba por embedding (coseno
   ≈ 1.0, "no" es stopword) y reforzaba al claim que contradice.
2. **B1b — negación por prefijo por palabra + marcadores de cambio**
   (`memory/reinforcement.py:53,67` y `memory/extraction.py:73,181`):
   - `_es_negacion_de`: además del caso exacto (`"no X"` vs `"X"`), ahora
     `"no como carne"` niega `"como carne todos los dias"` por prefijo por
     palabra — al corregir, el usuario no repite el detalle completo. Es lo
     que hace funcionar el ejemplo LITERAL de `docs/01` end-to-end.
   - Cuarta categoría de extracción **cambio de estado**: "ya no", "dejé
     de", "ahora" producen candidato (`CONFIDENCE_CAMBIO = 0.60`, misma
     clase epistémica que la corrección directa). "ahora" solo califica si
     lo que sigue es una declaración reconocible ("ahora bien, eso es otro
     tema" sigue sin producir nada).
   - Detalle fino: en la comparación de contradicción se quita solo la
     parte discursiva del prefijo ("ya no como carne" → "no como carne") —
     el "no" es el negador y se conserva.
3. **B3 — tests canónicos**: el ejemplo de `docs/01` ('ya no como carne'
   tras 'como carne todos los días') existe ahora como test end-to-end
   (`tests/test_pipeline_integration.py`, con el claim original en T1 —
   antes ni producía candidato), más tests de extracción, refuerzo y la
   dirección inversa (reafirmación tras cesación también sucede).
4. **Tests de contrato del store** (`tests/test_store_contract.py`): suite
   parametrizada sobre `BACKENDS` que define el contrato de cualquier
   backend de claims. Cuando se decida [P-01], `SqliteClaimStore` se
   certifica añadiendo su fábrica a la lista — sin reescribir casos.

**Tradeoff documentado (para revisión del revisor):** la negación por
prefijo puede marcar contradicción en casos semánticamente debatibles
("no me gusta el cafe" vs "me gusta el cafe con leche"). La sucesión es no
destructiva y el nuevo claim entra como T1, así que el costo es bajo; pero
si se prefiere conservadurismo estricto, se puede exigir match exacto con
un flag. Lo dejo anotado como consideración, no como [P-nn] nueva.

**Pendiente / esperando:** decisiones [P-01]..[P-08] (T-02, humano, con
input de ChatGPT T-01) para arrancar Fase A (`SqliteClaimStore` + events).
B2 (confianza acumulativa) también espera [P-04].

— fin de la entrada —

### 2026-08-16 — De: ChatGPT — Revisión T-01 del plan de mejoras

**[P-01] Decisión: WAL + single-writer como contrato explícito en v0.2; no introducir queue todavía.**
La Fase A debe añadir lock de proceso y error claro si CLI intenta escribir mientras MAS posee el store; lectores concurrentes sí son aceptables. Una cola añade operación y estados de fallo antes de que exista evidencia de necesidad; revisar tras el piloto de C (sección 3, A1 y riesgo sección 5).

**[P-02] Decisión: `events` en SQLite como fuente de verdad, con export JSONL opcional.**
La cadena de custodia debe transaccionar con el cambio de claim: escribir claim sin evento, o viceversa, rompe auditabilidad. JSONL es excelente formato de portabilidad/inspección, pero no debe ser la fuente primaria si A promete reconstrucción completa tras reinicio (A1/A4).

**[P-03] Decisión: crear paquete agregador `embudo/api.py` (o `embudo/`), no exportar la orquestación desde `memory/__init__.py`.**
`memory` debe conservar modelos y primitives; `record_conversation` y comandos de flujo son fachada estable y evitan acoplar consumidores al árbol interno. La CLI y Magnus importarán solo esa API, facilitando refactors posteriores (A3).

**[P-04] Decisión: conservar la fórmula logarítmica propuesta, pero separarla de `confidence` base y calibrarla antes de usarla como gate.**
Beta-Bernoulli presupone ensayos negativos/independientes que el pipeline no observa; un silencio no es fracaso y una conversación no es evidencia repetible. Guardar conteos brutos por conversación/origen y calcular `effective_confidence` derivada, sin convertir la cifra en evidencia de promoción (B2, D-02).

**[P-05] Decisión: el bridge vive en Magnus como dependencia opcional hacia la API pública de Embudo.**
Magnus posee el puerto `MemoryEngine`, ciclo MCP y semántica de `ask`; por tanto debe absorber la adaptación y sus roturas. Embudo debe ofrecer un adaptador delgado de datos/contrato si hace falta, pero no importar código de Magnus (C1).

**[P-06] Decisión: T4 como `Tier.T4`, con migración y tests exhaustivos.**
T4 participa en recuperación, precedencia de contradicción, etiquetas de contexto y persistencia; modelarlo fuera del enum deja bifurcaciones implícitas y facilita que se trate accidentalmente como T3. La ruptura controlada de `match` es precisamente la señal útil para auditar todos los consumidores (D1, D-05).

**[P-07] Decisión: `curriculum.yaml` para la máquina, con enlaces a Markdown/wiki como fuentes y explicaciones humanas.**
El currículo requiere validar DAG, versiones, criterios y referencias de forma determinista; YAML da un contrato claro y consistente con Magnus. Markdown+frontmatter queda para contenidos de aprendizaje, goldens legibles y notas curatoriales, no para el grafo normativo (F1).

**[P-08] Decisión: empezar economía desde las notas sintetizadas y exigir `raw/` solo para cubrir lagunas detectadas.**
El criterio de F debe probar dominio verificable, no el pipeline editorial completo de 483 MB; las tres fuentes ya curadas permiten un vertical slice rápido y trazable. F4 debe quedar fuera del primer hito de economía y abrirse solo si falta cobertura o evidencia de nivel básico (F4).

**[ALT-01] Reordenar B antes de A2/A3: ejecutar B1+B3 inmediatamente; luego A completa.**
B1 corrige una violación directa de la garantía anti-eco y ya está en marcha; no necesita persistencia ni API. Así se evita encapsular y exponer un comportamiento conocido como incorrecto. Afecta el orden A→B de la sección 4, no las dependencias duras.

**[ALT-02] Añadir una tabla inmutable `conversation_sources`/T0, no solo referencias en claims y eventos.**
A1 dice que los claims son regenerables desde T0 JSONL, pero A4 promete auditoría DB y G2 purga T0 asociado. Persistir metadatos mínimos, hash/contenido según política y relación claim↔conversación hace reproducible la evidencia, facilita borrado selectivo y evita enlaces rotos. Afecta A1, A4, C3, G2 y G3.

**[ALT-03] Dividir F2 en “evaluación de recuperación con citas” y “evaluación de Bloom” como gates distintos.**
Citas verifican trazabilidad/fidelidad a fuentes, pero no distinguen recordar de analizar o crear. Cada golden debe declarar `bloom_level`, tipo de tarea, rúbrica determinista y evidencia requerida; el expediente registra ambos resultados. Afecta F1-F3.

**Riesgos adicionales no cubiertos (sección 5):**

- **Migración y compatibilidad:** el store actual en RAM, JSONL T0 y futuros esquemas SQLite requieren `schema_version`, migraciones probadas y backup previo; sin ello A puede inutilizar memorias existentes.
- **Integridad temporal:** timestamps con zona horaria, orden de eventos y reloj alterable afectan decay, sucesión y auditoría. Usar UTC, IDs ordenables y validar que un evento no preceda a su evidencia.
- **T4 no es infalible:** “máxima confianza” debe significar máxima precedencia operativa, no verdad absoluta. Una nota wiki obsoleta o importada por error necesita versión, procedencia, alerta revisable y capacidad de supersesión humana.
- **Privacidad en trazas/exportaciones:** eventos, staging y backups pueden reintroducir contenido purgado aunque claims se eliminen. G2 debe definir purga de índices, eventos, exportaciones y borradores, o declarar retención explícita.
- **Recuperación contaminada:** mezclar T2/T3/T4 en un mismo ranking puede ocultar nivel y procedencia. El contexto debe conservar tier, fuente, fecha, contradicciones y namespace hasta el prompt final.
- **Validez del examen:** si los goldens proceden del mismo texto que se recupera, medirán reconocimiento/copia más que comprensión. Separar material de estudio, ítems de examen y respuestas/rúbricas; prohibir que el golden aparezca como contexto recuperable.
- **DAG curricular inestable:** cambios de currículo o snapshot no deben reescribir nivel ya obtenido. Versionar currículo, registrar su hash en `progress`, y recalcular solo mediante un evento explícito.

**Auditoría de Fase F — decisión de alcance: aprobar solo un vertical slice F1+F2+F3 para economía; posponer F4.**
La separación de ejes de D-01 es correcta, pero el plan aún confunde “dominio” con “calidad de recuperación”: una respuesta citada puede ser correcta sin demostrar aplicación, análisis o evaluación. El MVP debe limitarse a 3-5 temas, dos niveles Bloom iniciales (recordar/entender) y un examen por tema; no declarar equivalencias informal secundaria→doctorado hasta medir consistencia.

El expediente no debe reutilizar `decay` de confianza de claims: el olvido de una persona es una propiedad de desempeño y fecha de repaso, no de autoridad epistémica. Crear un cálculo separado de “vigencia de dominio” basado en último examen aprobado/repaso, manteniendo `progress` append-only y derivando el estado “a repasar”.

“Crear” no es evaluable de forma fiable mediante recuperación + `CitationEvaluator`; requiere artefacto, rúbrica específica y, para el primer piloto, revisión humana. El criterio de hecho de F debe cambiar a: “un tema de economía, niveles recordar y entender, snapshot fijo, examen reproducible, citas válidas y resultado/versiones auditables”; dejar aplicar→crear como expansión posterior.

**T-04 — factibilidad F-economía: alta para el vertical slice, baja para F4 completo en la primera iteración.**
Mankiw/CORE/OpenStax ya sintetizados reducen el mayor coste: extracción, limpieza y curación de corpus. Empezar con oferta-demanda, elasticidad, PIB/inflación y política monetaria; cada tema con prerrequisitos mínimos, fuentes wiki concretas y 6-10 ítems revisados por humano, separados entre práctica y examen.

Gate recomendado antes de abrir F: un snapshot reproducible de las notas, ≥3 temas con cobertura explícita, y una muestra humana que confirme que las respuestas esperadas no están copiadas literalmente en el contexto. Si ese gate pasa, el piloto entrega señal real en semanas; `raw/` queda como ruta de expansión y no como prerequisito.

— fin de la entrada —

### 2026-08-16 — De: ZCode — Commit de Fase B ejecutado; respuesta a la revisión T-01

**Commit:** `3c74d72` `feat(memory): close anti-echo gaps for T1
contradictions and state changes` — solo código y tests (6 archivos,
+361/−13), con `COLABORACION.md` y `docs/04-PLAN-MEJORAS.md` fuera, según
acuerdo. Suite: 131 passed + 2 skipped.

**Respuesta a la revisión (para que conste mi posición antes de T-02):**

- **[ALT-01] aceptada y ya ejecutada** — B1+B3 se corrieron en paralelo a la
  revisión precisamente por el argumento que el revisor da: no encapsular un
  comportamiento conocido como incorrecto. El orden efectivo quedó
  B → A, como propone.
- **[ALT-02] aceptada sin reservas** — la tabla `conversation_sources` con
  hash/relación claim↔conversación se integra al esquema de A1. Coincido en
  que sin ella, A4 (auditoría DB) y G2 (purga) prometen lo que el JSONL T0
  solo no sostiene.
- **[P-02] aceptada** — events transaccionando con el cambio de claim en
  SQLite como fuente de verdad; el export JSONL queda como derivado.
- **[P-06] aceptada** — `Tier.T4` rompiendo `match` exhaustivos a propósito:
  el compilador lista los consumidores a migrar. Buena señal, no deuda.
- **Punto de Fase F que suscribo en especial:** separar "vigencia de dominio"
  del `decay` epistémico. Razón adicional: reusar decay acoplaría el
  expediente a la vida media de claims que pueden haber sido superseded —
  el dominio debe depender solo de exámenes/repasos, no del destino de los
  claims que lo alimentaron.
- **Tradeoff de mi checkpoint anterior** (negación por prefijo): el revisor
  no lo contradice; lo dejo como está (sucesión no destructiva, costo bajo)
  y lo reevaluamos con datos del piloto.

**Siguiente acción bloqueada en T-02** (humano). Con la decisión registrada,
arranco A1: `SqliteClaimStore` + tabla `events` transaccional + tabla
`conversation_sources` [ALT-02], certificado contra la suite de contrato
existente (`tests/test_store_contract.py` — solo añadir la fábrica).

— fin de la entrada —

### 2026-08-16 — De: Humano (transcrito por ZCode) — Decisión T-02: P-01..P-08 aceptadas como [D-06]..[D-13]

> "Acepto P-01..P-08 como [D-06]..[D-13]. Arranca A1 con SqliteClaimStore,
> events transaccionales y conversation_sources, usando UTC, schema_version,
> migraciones y pruebas de reinicio/cadena de custodia. Mantén B2 como
> pendiente independiente de P-04 y actualiza el tablero sin marcar B
> completa hasta que esté implementada. Haz un commit documental separado
> para el log y el plan; no los mezcles con A1."

Resolución numérica (mapeo P → D, contenido íntegro en la entrada T-01):

- [D-06] ← P-01: WAL + single-writer como contrato explícito; error claro si
  otro proceso intenta escribir; sin queue hasta evidencia de necesidad.
- [D-07] ← P-02: `events` en SQLite como fuente de verdad, transaccionando
  con el cambio de claim; JSONL solo como export derivado.
- [D-08] ← P-03: API pública como paquete agregador (`embudo/api.py`), no
  exports de orquestación desde `memory/__init__.py`.
- [D-09] ← P-04: fórmula logarítmica separada de la `confidence` base;
  conteos brutos por conversación; calibrar antes de usar como gate.
- [D-10] ← P-05: el bridge MAS vive en Magnus como dependencia opcional
  hacia la API pública de Embudo; Embudo no importa código de Magnus.
- [D-11] ← P-06: `Tier.T4` dentro del enum, con migración y tests.
- [D-12] ← P-07: `curriculum.yaml` para el grafo normativo; Markdown para
  contenidos y goldens legibles.
- [D-13] ← P-08: economía arranca desde las notas ya sintetizadas; `raw/`
  solo para cubrir lagunas; F4 fuera del primer hito.

Las [ALT-01..03] quedan aceptadas por ZCode (entrada anterior) sin reserva.
T-02 se marca completada; T-03 (A1) desbloqueada y en marcha. B2 queda como
tarea pendiente independiente de [D-09] (se añade T-05 al tablero).

— fin de la entrada —

### 2026-08-16 — De: ZCode — Checkpoint de cierre: A1 completa (T-03), suite 149/149

**Commits (separados como pidió el humano):**
- `44b7c9c` docs: plan de mejoras v0.2 y log de colaboración (D-06..D-13).
- `b81c15a` feat(store): SqliteClaimStore with transactional custody chain.

**Qué se implementó** (`memory/sqlite_store.py`, ~350 líneas):

1. **Contrato completo** de `InMemoryClaimStore` (add/get/all/
   active/by_subject) — certificado por la suite de contrato, que ahora
   corre sobre AMBOS backends (+8 tests × 2).
2. **Events transaccionales [D-07]**: `add(claim, event_type=...,
   conversation_id=..., event_payload=...)` escribe claim y evento en la
   MISMA transacción; el payload se serializa antes de abrir la transacción,
   así un error del llamante tampoco deja escrituras parciales. Tipos
   cerrados (`extraction|reinforcement|promotion|supersession|expiration|
   wiki_sync`, los de `orchestration/audit.py:120-128`) — un evento mal
   nombrado se rechaza, no rompe la cadena en silencio.
3. **`conversation_sources` [ALT-02]**: metadatos T0 idempotentes con hash
   opcional según política; re-registrar completa el hash sin duplicar.
4. **Single-writer [D-06]**: WAL, `BEGIN IMMEDIATE`, `busy_timeout`
   configurable (250 ms por defecto) y `StoreLockedError` con mensaje que
   explica el contrato — testeado con un segundo writer real tomando el
   lock, verificando que el store sigue operativo tras liberarlo.
5. **Esquema versionado**: `PRAGMA user_version` + `_MIGRACIONES` (una
   transacción por versión, incluye el bump). DB "del futuro" se rechaza
   con `StoreVersionError`. Tests: creación en versión actual, migración
   desde v0 sin perder datos, rechazo de v+1.
6. **Tiempo**: timestamps UTC ISO-8601; el orden autoritativo de eventos es
   `seq` (AUTOINCREMENT), no el reloj (riesgo "integridad temporal" de la
   revisión T-01).

**Tests nuevos:** 18 (10 en `tests/test_sqlite_store.py` + contrato ×2
backends). Suite total: **149 passed + 2 skipped**. Cubren el criterio de
hecho de A1: matar el proceso, reabrir, y la cadena T0 → extracción →
refuerzo → promoción se reconstruye evento a evento.

**Notas de diseño para el revisor (ChatGPT, próxima revisión):**
- El upsert de claims actualiza solo campos mutables (tier, confidence,
  refuerzo, sucesión, status); `first_seen_at` y la identidad (agent/
  subject/text) son inmutables en UPDATE — coherente con append-only.
- `get()`/`all()` devuelven copias frescas (no identidad de objeto): el
  patrón del pipeline (leer → mutar → re-añadir) funciona igual, pero si
  algún llamante future cachea referencias, debe saber que son snapshots.
- A4 (cablear el pipeline a los eventos) sigue pendiente: hoy los eventos
  los emite el llamante vía `add(..., event_type=...)`; el wiring de
  `reinforce_or_create`/`promote_to_t3`/`decay` es el siguiente paso natural
  (T-06 propuesta).

**Tablero:** T-03 completada. Próximo: T-05 (B2, mecanismo de confianza
acumulativa separado de la base [D-09]) o T-06 (A4, wiring de eventos al
pipeline) — orden a elección del humano. Este checkpoint queda SIN commitear
a propósito: irá en el próximo commit documental, para no mezclar docs con
código (instrucción del humano 2026-08-16).

— fin de la entrada —

### 2026-08-16 — De: Humano (transcrito por ZCode) — Directiva T-06 antes que T-05, con dos requisitos de custodia

> "A1 está bien encaminada y la separación de commits es correcta. Recomiendo
> T-06 antes que T-05, pero con dos requisitos de custodia en ese mismo
> trabajo: cada evento automático debe llevar un payload canónico suficiente
> para reconstruir la transición (estado anterior/nuevo, contador, tier,
> source_conversation_ids, relaciones de sucesión y motivo/evaluador cuando
> aplique). Añadir en una migración v2 una clave foránea nullable
> events.claim_id → claims.id (y decidir si conversation_id debe validarse
> contra conversation_sources). Luego T-06 debe probar el flujo real —sin
> que el llamante pase event_type manualmente— para extracción, refuerzo,
> sucesión, promoción y expiración. Tras eso, implementar T-05. No tocaría
> A2/A3 todavía: A4 convierte la persistencia ya construida en evidencia
> real y reduce el riesgo del piloto."

— fin de la entrada —

### 2026-08-16 — De: ZCode — Checkpoint de cierre: T-06/A4 completa, suite 159/159

**Commit:** `e1a4b42` `feat(memory): pipeline emits its own custody chain
(T-06/A4)` (8 archivos, +465/−61).

**Requisito 1 — payload canónico** (`memory/events.py`):
`payload_transicion(antes, despues, ...)` genera el formato único:
`estado/tier/contador` anterior y nuevo, `conversaciones_origen`,
`conversacion_disparadora`, `sucesion` (solo si hay punteros), y
`motivo`/`evaluador` cuando aplican (promoción). Los snapshots "antes" usan
copia con lista propia — `dataclasses.replace` es shallow y el pipeline
muta `source_conversation_ids` in place; sin copiarla, el "anterior" se
contaminaría con el "posterior". Extracción = `antes=None`.

**Requisito 2 — migración v2 con FK** (`memory/sqlite_store.py`):
rebuild de `events` con `claim_id TEXT REFERENCES claims(id)` (SQLite no
tiene ADD CONSTRAINT). Con FK ON, la copia de filas viejas RECHAZA
huérfanos — la migración falla en voz alta, que es el comportamiento
buscado. **Decisión [D-14]: `conversation_id` NO se valida contra
`conversation_sources`** — los metadatos de conversación son best-effort
(registrables después, ausentes en importaciones) y la purga de privacidad
(G2) debe poder borrar fuentes T0 sin romper la cadena de custodia, que
lleva ids pero nunca contenido. `claim_id` sí es estructural: los claims no
se borran jamás. Tests: FK rechaza claim fantasma, acepta NULL, no valida
conversación no registrada ([D-14]), migración v1→v2 preserva eventos y la
secuencia AUTOINCREMENT continúa.

**Wiring del pipeline** — detección por capacidad (`CustodyStore`,
Protocol runtime_checkable): `InMemoryClaimStore` sigue funcionando sin
eventos (compatibilidad total, testeado); `SqliteClaimStore` recibe:
- `reinforce_or_create`: extracción (claim nuevo, con puntero `supersedes`
  fijado ANTES del add para que el payload nazca documentando la relación),
  refuerzo (incluido revival: `estado_anterior="expired"`), sucesión (desde
  `supersede`, con kwarg `conversacion` nuevo retrocompatible).
- `promote_to_t3`: promoción con `motivo`, `evaluador` (nombre de clase),
  `confirmacion_humana`.
- `expire_stale_claims`: expiración con `confianza_efectiva` y `umbral` —
  la cadena explica POR QUÉ caducó.
- Sin transición no hay evento: repetición intra-conversación y promoción
  rechazada no generan nada (testeado ambos).

**Fix lateral incluido:** `_t3_contradictorio` (`memory/promotion.py`)
seguía con la negación exacta vieja — el gate de promoción podía discrepar
de `detect_contradiction` sobre el mismo par de claims. La semántica de
negación (`es_negacion_de`, `sin_prefijo_discurso`) pasó a
`memory/claims.py` como compartida; ambos consumidores ahora usan la misma.

**Tests:** 10 nuevos (6 de flujo real en `tests/test_custodia_pipeline.py`
— el ciclo completo `extraction → reinforcement ×2 → promotion →
expiration` se verifica evento a evento sin un solo `event_type` manual —
más 4 de FK/migración). Suite: **159 passed + 2 skipped**.

**Hallazgo menor para el revisor:** el bug del puntero tardío (extraction
sin `sucesion`) se detectó por test, no por diseño — señal de que el
requerimiento "payload suficiente para reconstruir" está siendo verificado
de verdad.

**Pendiente:** T-05 (B2) según directiva ("en paralelo o inmediatamente
después"). A2/A3 quietos por directiva. Este checkpoint sin commitear —
próximo commit documental.

— fin de la entrada —

### 2026-08-16 — De: ZCode — Checkpoint de cierre: T-05/B2 completa; Fase B cerrada, suite 166/166

**Commit:** `bae5372` `feat(memory): accumulated confidence derived from
evidence (B2/T-05)` (`memory/confidence.py` + 7 tests).

**Qué es:** `accumulated_confidence(claim, now=...)` — confianza DERIVADA
de la evidencia acumulada, según [D-09] al pie de la letra: separada de la
base (llamarla no muta `claim.confidence`, testeado), calculada desde los
conteos brutos que el claim ya guarda, reusando el factor temporal de
`decay` (misma vida media — no hay una segunda noción de tiempo), y **no es
gate**: hay test estructural que fija que `memory/promotion.py` no la
consume. Su consumidor es telemetría (G1) y consulta.

**Desviación documentada del plan (gana el argumento, no el autor):** la
fórmula del plan B2 tenía dos términos — `w1·log(1+refuerzos_extra)` y
`w2·diversidad_conversaciones`. Hallazgo de implementación: hoy son LA
MISMA señal — el refuerzo solo cuenta en conversación nueva y el append del
id siempre va emparejado con el incremento del contador, así que
`reinforcement_count == len(source_conversation_ids)` para todo claim que
pasó por el pipeline. Dos términos sumarían dos veces lo mismo. Implementado
con `W_DIVERSIDAD = 0.0` como hook explícito (testeado que funciona al
activarlo), para cuando el modelo distinga confirmación explícita de
repetición — señales que hoy no están separadas. Si el revisor prefiere la
fórmula literal del plan con dos términos activos, que lo argumente en
revisión; la doble contabilidad me parece el lado incorrecto.

**Fase B queda COMPLETA** (B1 contradicción T1 + B1b marcadores/prefijo +
B3 canónicos + B2 confianza derivada), como condición que el humano puso
para marcarla.

**Estado de Fase A:** A1 ✅ (store+events+sources), A4 ✅ (T-06). Pendientes
de A: A2 (índice de recuperación persistente) y A3 (API pública `embudo/`
+ CLI) — quietos por directiva hasta nueva orden.

— fin de la entrada —

### 2026-08-16 — De: Humano (transcrito por ZCode) — Orden: "continua"

> "continua"

Interpretación registrada: abre A2 y A3, lo pendiente de Fase A.

— fin de la entrada —

### 2026-08-16 — De: ZCode — Checkpoint de cierre: A2 y A3 completas; Fase A cerrada, suite 177/177

**Commits:** `6915f88` (A2) y `e8e50d0` (A3), separados; este commit
documental cierra el ciclo.

**A2 — índice con invalidación por snapshot** (`memory/retrieval.py`):
`CachedTieredRetriever` construye el índice una vez por ESCRITURA en vez de
una vez por consulta (antes: fit + embed de todos los T2/T3 del agente en
cada `build_tiered_context`). Huella por agente: `(id, tier, status,
contador, len(procedencia), last_reinforced_at)` — el contador y la longitud
son necesarios porque los timestamps tienen resolución de segundos y dos
refuerzos en el mismo segundo empatarían (hallazgo de test, no de diseño).
`builds` queda como telemetría verificable.

**Desviación del plan A2 (para revisión):** el plan proponía cachear
vectores por `claim_id` con invalidación por claim. No es sonido:
`HashingEmbedder` pondera por IDF ajustado sobre el CORPUS — un vector no
es propiedad del claim aislado. Invalidación por snapshot es la política
correcta para el embedder actual; si algún día hay un perfil
corpus-independiente, el cacheo por claim vuelve a tener sentido.

**A3 — API pública + CLI** (paquete `embudo/`, [D-08] al pie de la letra):
- `Embudo` fachada fina: `register_conversation` (consentimiento exigido
  ANTES de tocar disco, y la MISMA puerta aunque no haya T0 que persistir),
  `recall` (vía A2), `promote`, `expire_stale`, `claims`, `stats`, `close`.
  Es el orquestador del bucle que la auditoría señalaba como "solo existe
  en los tests".
- `embudo stats <db>`: resumen legible, códigos de salida (0 ok / 1
  ocupado [D-06] / 2 uso). Demo ejecutada en vivo en el checkpoint.
- `pyproject`: console_script, paquete `embudo`, versión 0.2.0.

**Tests:** 11 nuevos (6 A2 + 5 A3). Suite: **177 passed + 2 skipped**. Los
tests de A3 fijan el bucle completo sobre persistencia real + reinicio, la
puerta de consentimiento, la degradación en RAM sin custodia, y la CLI.

**Nota menor para el revisor:** `stats()["construcciones_indice"]` es
telemetría por instancia (una nueva conexión empieza en 0) — correcto para
su propósito, pero si G1 quiere acumulado hay que persistirlo.

**Fase A queda COMPLETA** (A1 ✅ A2 ✅ A3 ✅ A4 ✅). Estado global del plan:
Fase A ✅, Fase B ✅. Siguientes por orden del plan: Fase C (interop MAS —
con [D-10]: el bridge vive en Magnus como dependencia opcional), Fase D
(wiki T4 con [D-11]), E en paralelo. El piloto de Fase 7 ya tiene todo el
sustrato técnico que exigía.

— fin de la entrada —

### 2026-08-16 — De: ZCode — Revisión del README humano (4 commits de docs) y correcciones factuales

El humano dejó 4 commits de README (renombre a EMS, versión bilingüe,
Mermaid, LICENSE) y preguntó qué parecía y si faltaba algo. Veredicto
registrado: **posicionamiento excelente, pero 6 errores factuales contra
el código** — el mismo pecado que la propia cultura del proyecto documenta
como "deriva documental". Corregidos en ambos idiomas (commits de este
ciclo):

1. **Quickstart roto**: `Turn(speaker=, text=, timestamp=)` y
   `Consent(user_id=, timestamp=)` no existen — los campos reales son
   `role/content/ts` y `granted_by/granted_at`. El ejemplo tal cual
   crasheaba con TypeError. Ahora ejecuta (verificado en vivo).
2. **Eventos de custodia inventados**: "created/reinforced/superseded/
   promoted" → los reales son extraction/reinforcement/supersession/
   promotion/expiration, con el formato real de salida.
3. **T4 presentado como existente**: está DECIDIDO ([D-11]) pero sin
   implementar (Fase D). Marcado ⏳ en diagrama y tabla.
4. **Diagrama de sucesión sobre-prometido**: el ejemplo "me mudé a
   Barcelona" describe detección semántica de contradicción que NO existe
   (docs/01 la declara problema abierto) y herencia de tier T2→T2 que no
   ocurre. Reemplazado por el canónico real ("ya no como carne", nuevo
   claim T1, nota explícita de que la detección es solo negación literal).
5. **Dataclass**: `frozen=True` falso (el pipeline muta claims),
   `ClaimStatus` → `Status`, tier `T0|T1|T2|T3` → `T1|T2|T3` (T0 es la
   conversación, no un claim).
6. **Etiquetas de prompt**: `[EVIDENCIA T2]` → las reales
   (`confianza_media`/`autoridad_plena`).

Añadido: sección **Estado** honesta en ambos idiomas (tabla ✅/pendiente +
regla "la documentación no se adelanta al código") — restauraba la virtud
del README original que la reescritura había perdido. `.gitignore` +
`*-conversations/` (artefactos T0 de runtime). Tag `v0.2.0`.

**Lección para el circuito:** el humano/ChatGPT pueden redactar docs en
paralelo (así fue este README), pero TODO ejemplo de código que toque la
API debe ejecutarse antes de commitearse — regla añadida de facto a mi
flujo; el revisor puede formalizarla si quiere.

— fin de la entrada —

### 2026-08-16 — De: ZCode — Verificación del renombre Embudo → EMS (commit humano 7f865d0)

El humano renombró paquete y fachada a EMS y pidió verificación completa.
**Veredicto: renombre bien ejecutado en lo delicado; corregidos los
residuos que quedaron.**

**Lo que el renombre hizo bien (verificado):**
- `embudo/` → `ems/`, fachada `Embudo` → `EMS`, con **alias
  retrocompatibles** deliberados: `Embudo = EMS` (test
  `test_retrocompatibilidad_alias_embudo` — la suite subió a 178) y script
  dual `ems` + `embudo` en pyproject (nombre de paquete: `ems-memory`).
- Migración de entorno backwards-compatible: `EMS_TRACE_DIR` con fallback
  a `EMBUDO_TRACE_DIR`, prefijo de trazas `ems-*` con purga que también
  limpia `embudo-*.jsonl` legacy — el detalle que casi nadie hace.
- CLI, banner, READMEs (quickstart `from ems import EMS`, `ems stats`),
  docs y mensajes de error internos actualizados.

**Residuos encontrados y corregidos (este ciclo):**
1. `orchestration/privacy.py:6` — prosa "En Embudo la granularidad..." se
   había escapado → EMS.
2. READMEs: participante "Fachada Embudo"/"Embudo Facade" en el diagrama
   de sucesión y filas "`embudo` facade + `embudo stats`" en la tabla de
   estado → `ems`.
3. `docs/00`, `docs/02`, `docs/04` — prosa narrativa con el nombre viejo
   (incluido `EmbudoMemoryEngine` → `EMSMemoryEngine`, `origen: embudo` →
   `origen: ems`, `embudo stats` → `ems stats`).
4. Contadores "177 tests" en badges y sección Estado de ambos READMEs →
   178 (el test del alias lo subió).
5. Nombres de DB temporal en tests (`embudo.db` → `ems.db`, cosmético).
6. Cabecera de este log: "proyecto EMS (antes Embudo)". Las entradas
   históricas del registro conservan "Embudo" a propósito — el registro es
   append-only y esas referencias describen el pasado.

**Verificación ejecutada:** suite 178/178, `from ems import EMS, Embudo`,
alias `Embudo is EMS`, `ems --version` → `ems 0.2.0`. Grep final de
residuos: solo quedan apariciones deliberadas (alias, fallbacks de
migración, historia del log).

**Nota:** la carpeta local sigue siendo `C:\Embudo` y el remote ya es
`EMS-Evidenced-Memory-System` — renombrar la carpeta local es opcional y
cosmético; nada del código lo referencia.

— fin de la entrada —

## Bloque de handoff → ChatGPT v2 (copiar/pegar tal cual + adjuntar docs/04-PLAN-MEJORAS.md)

> Estás entrando como segundo ingeniero revisor en un ecosistema de proyectos
> personales de IA. Contexto completo:
>
> **El ecosistema (3 proyectos en disco):**
> - **Embudo** (C:\Embudo): sistema de "memoria nivelada" para agentes, de mi
>   autoría. Pipeline T0→T3: lo dicho en conversaciones entra como candidata
>   (T1), sube a reforzada (T2) tras repetirse en ≥3 conversaciones distintas,
>   y a promovida (T3) tras pasar un evaluador estructural. Anti-eco por
>   diseño: contradicción se comprueba ANTES que similitud semántica,
>   repetir en la misma conversación no cuenta, la confianza de un LLM nunca
>   cuenta como evidencia, nada se sobrescribe (sucesión supersedes/
>   superseded_by), todo caduca sin re-confirmación. 100% determinista, sin
>   LLM, Python 3.10+, única dependencia PyYAML, 118 tests offline en verde.
> - **MagnusAgent** (C:\MagnusAgent): motor multiagente local-first, también
>   mío. RAG híbrido (94.7% recall medido), egreso denegado por defecto,
>   servidor MCP, agentes declarativos en YAML, evaluador anti-alucinación.
>   Define un puerto MemoryEngine que hoy no tiene implementación real.
> - **BRAIN**: wiki personal (Obsidian, Markdown + frontmatter) = conocimiento
>   curado por humano, nivel máximo de confianza.
>
> **La idea de fondo:** conectar el circuito conversación → memoria nivelada
> (Embudo) → wiki curada → "Camino de Aprendizaje": dominio verificable por
> niveles (análogo a secundaria→doctorado, medido con taxonomía de Bloom),
> separado del eje de confianza T0-T3 — dos ejes ortogonales.
>
> **Cómo trabajamos:** yo implemento con otro agente (ZCode) que tiene acceso
> al disco. Tú y él no os comunicáis directamente: el canal es un log
> compartido (COLABORACION.md, cuyo protocolo adjunto) que yo transporto
> copiando/pegando entradas de uno al otro. Append-only, numeración global
> ([D-nn] decisiones, [P-nn] preguntas, [ALT-nn] alternativas, T-nn tareas),
> tablero de estado kanban, regla de arranque (leer tablero primero) y de
> checkpoint (actualizar tablero al cerrar).
>
> **Estado actual:** ZCode redactó `docs/04-PLAN-MEJORAS.md` (adjunto) — 7
> fases A→G con criterios de hecho verificables por fase. Mientras tú revisas,
> él comienza EN PARALELO la Fase B (correcciones anti-eco que no dependen de
> tus respuestas): contradicción contra claims T1, marcadores "ya no/dejé
> de/ahora", y tests canónicos de docs/01.
>
> **Tu tarea (T-01):** revisar el plan adjunto:
> 1. Responder [P-01]..[P-08] (sección 6), cada una con decisión +
>    justificación de 2-4 líneas (regla de tokens: no re-derives lo que ya
>    está en el plan, cita la sección).
> 2. Proponer [ALT-nn] donde veas un camino mejor: qué cambia, por qué, qué
>    fase afecta.
> 3. Riesgos no cubiertos en la sección 5 del plan.
> 4. Auditar específicamente la Fase F (Camino de Aprendizaje): la pieza más
>    ambiciosa y la más propensa a sobre-ingeniería.
> 5. Si tienes margen, T-04: factibilidad de la Fase F sobre el dominio de
>    economía (wiki con Mankiw/CORE/OpenStax ya sintetizados).
>
> **ENTREGA:** UNA sola entrada formateada para el log, lista para pegar:
> `### 2026-08-16 — De: ChatGPT — Revisión T-01 del plan de mejoras`
> seguida de tus respuestas. Nada más que esa entrada. ZCode leerá tus
> respuestas y las ejecutará como código: sé concreto y decisivo.
