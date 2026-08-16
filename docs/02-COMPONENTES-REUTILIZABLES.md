# Componentes reutilizables de MagnusAgent

Ninguno de estos módulos se importa en tiempo de ejecución — EMS es un
proyecto independiente. Esta tabla dice, para cada pieza de Magnus, si el
plan es **portar** (copiar y adaptar el código), **vendorizar** (empaquetar
tal cual como dependencia interna) o solo **reusar el patrón** (reescribir
desde cero siguiendo el mismo diseño porque el modelo de datos es distinto).

| Componente Magnus | Ruta | Qué hace en Magnus | Plan en EMS |
|---|---|---|---|
| `RAGPipeline` + protocolos `DenseRetriever`/`LexicalRetriever`/`Reranker` | [`kernel/rag/pipeline.py`](../../MagnusAgent/kernel/rag/pipeline.py) | Orquesta recuperación híbrida con fusión por rango (RRF) y umbral por score original. | **Vendorizar tal cual.** El contrato ya es exactamente lo que necesita `MemoryClaim` como documento indexable — no hay razón para reescribirlo. |
| `HashingEmbedder` (random indexing + TF-IDF) | [`kernel/rag/embedder.py`](../../MagnusAgent/kernel/rag/embedder.py) | Implementación del puerto `Embedder` sin dependencias pesadas (sin torch). | **Portar.** Sirve igual para detectar similitud entre candidatos nuevos y claims existentes (paso de deduplicación del pipeline). Mismo límite documentado: no captura sinónimos sin forma compartida — aceptable como punto de partida, mismo trade-off que en Magnus. |
| `InMemoryVectorStore` | [`kernel/rag/vector_store.py`](../../MagnusAgent/kernel/rag/vector_store.py) | Implementación de `DenseRetriever` sobre los chunks del store léxico. | **Portar**, adaptado para indexar `MemoryClaim` en vez de chunks de wiki. |
| Patrón de `snapshot_id` + hash por chunk | [`kernel/rag/file_store.py`](../../MagnusAgent/kernel/rag/file_store.py) | Permite reproducir una cita: si la nota cambió, se sabe. | **Reusar el patrón, no el código** — en EMS el equivalente es el hash de `MemoryClaim.id` + la cadena `supersedes`/`superseded_by`, que ya cumple el mismo rol pero con un modelo de versionado distinto (sucesión, no snapshot global). |
| `citation_evaluator.py` (evaluador estructural, determinista) | [`orchestration/evaluation/citation_evaluator.py`](../../MagnusAgent/orchestration/evaluation/citation_evaluator.py) | Rechaza respuestas sin cita o con cita fabricada; exige múltiples fuentes si `rigor >= 8`. | **Reusar el patrón.** El evaluador de promoción de T2→T3 (`01-MEMORIA-NIVELADA.md`) es, en espíritu, el mismo tipo de verificación estructural aplicada a consistencia entre conversaciones en vez de anclaje a una nota. Empezar determinista antes de escalar a LLM-as-judge, exactamente como hizo Magnus. |
| `Evaluator` como `Protocol` | [`orchestration/evaluation/`](../../MagnusAgent/orchestration/evaluation/) | Permite enchufar un LLM-as-judge sin tocar el motor. | **Portar el patrón de puerto.** Útil desde el día uno para no acoplar el gate de promoción a una sola implementación. |
| `PermissionEngine` (intersección de tres fuentes, deny gana) | [`orchestration/permissions.py`](../../MagnusAgent/orchestration/permissions.py) | Permiso efectivo = agente ∩ política ∩ rol del llamante. | **Portar tal cual el modelo de decisión.** Aplica igual a "quién puede leer un claim T3 de otro agente" o "quién puede confirmar una promoción manual". |
| `configs/privacy.yaml` + `orchestration/privacy.py` (egreso denegado por defecto) | [`configs/privacy.yaml`](../../MagnusAgent/configs/privacy.yaml), [`orchestration/privacy.py`](../../MagnusAgent/orchestration/privacy.py) | Un namespace no sale del dispositivo a un proveedor remoto salvo autorización explícita. | **Portar sin cambios de diseño.** Es el principio 5 de `00-VISION-Y-ARQUITECTURA.md`. Adaptar solo la granularidad: en EMS la unidad protegida es el claim/subject, no el namespace de una wiki de carpetas. |
| `orchestration/audit.py` (JSONL, opt-in, sin contenido sensible) | [`orchestration/audit.py`](../../MagnusAgent/orchestration/audit.py) | Registra decisión de evaluación, hashes, guardrails aplicados. | **Portar el patrón**, extendiéndolo para registrar eventos propios de EMS: extracción, refuerzo, promoción, sucesión, expiración. Corregir en el port el hallazgo de seguridad de Magnus: fijar permisos de archivo restrictivos (`0600`) desde el diseño, no como parche posterior. |
| `ProviderRegistry` (perfil → provider + fallback, `only_local`) | [`providers/registry.py`](../../MagnusAgent/providers/registry.py) | Resiliencia de proveedores: reintentos acotados, fallback por política, poda de proveedores remotos si `only_local=True`. | **Vendorizar tal cual.** No hay nada específico de EMS en la resiliencia de llamadas a modelos — es infraestructura genérica ya resuelta. Añadir el circuit breaker señalado como deuda en el análisis de Magnus (`MagnusAgent/docs/06-ANALISIS-MEJORAS-SEGURIDAD.md`, punto 3) directamente en esta capa vendorizada, no reinventarlo. |
| `orchestration/capability/matcher.py` (`HybridCapabilityMatcher`) | [`orchestration/capability/matcher.py`](../../MagnusAgent/orchestration/capability/matcher.py) | Enruta una consulta a una capacidad por léxico + sinónimo exacto + coseno como refuerzo, nunca coseno puro decidiendo solo. | **Reusar el patrón** para enrutar una conversación al agente/dominio de memoria correcto. La lección medida en Magnus (coseno puro es más débil que léxico, solo debe reforzar) aplica igual aquí — no repetir el experimento, partir directamente del diseño híbrido. |
| `orchestration/memory/memory_engine.py` y `sqlite_memory_engine.py` | [`orchestration/memory/`](../../MagnusAgent/orchestration/memory/) | Esqueleto de memoria, nunca conectado al motor; `recall` usa `LIKE '%query%'`. | **No portar la implementación.** Sirve como referencia de la interfaz que Magnus previó, pero el modelo de datos de `MemoryClaim` (niveles, refuerzo, sucesión, caducidad) es sustancialmente más rico. Construir desde cero en EMS con esa interfaz en mente para que, si algún día Magnus quiere adoptar memoria real, el puerto ya calce. |
| `mcp_server/http_guard.py` (auth por token, CORS restringido, rate limit, límite de tamaño) | [`mcp_server/http_guard.py`](../../MagnusAgent/mcp_server/http_guard.py) | Guarda de transporte HTTP, separado del protocolo para poder testearse sin socket. | **Portar el patrón, corrigiendo los dos hallazgos ya identificados en Magnus** (`MagnusAgent/docs/06-ANALISIS-MEJORAS-SEGURIDAD.md`, puntos 1 y 2): exigir token siempre en vez de solo fuera de `127.0.0.1`, y poner cota/expiración al diccionario de rate limiting desde el diseño inicial. |
| Herramientas `python`/`terminal` declaradas como "sandbox" | [`tools/mcp_catalog.yaml`](../../MagnusAgent/tools/mcp_catalog.yaml), [`configs/permissions.yaml`](../../MagnusAgent/configs/permissions.yaml) | Declaradas en YAML sin ningún mecanismo de aislamiento real detrás. | **No portar tal cual — es el ejemplo a no repetir.** Si EMS necesita ejecución de herramientas en el futuro, el sandbox real (contenedor, límites de recursos, red bloqueada) se construye e integra ANTES de declarar la herramienta disponible, no al revés. Ver principio 6 de `00-VISION-Y-ARQUITECTURA.md`. |

## Qué se descarta sin portar

- **`FileWikiStore` como fuente única.** EMS puede seguir aceptando una
  fuente curada opcional (nivel T3 desde el día uno, sin pasar por refuerzo),
  pero el store en sí asume una wiki en disco versionada por carpetas — el
  modelo de `MemoryClaim` reemplaza esa función.
- **`sdk/cli.py cmd_agent_test`** — en Magnus es un placeholder que no prueba
  nada funcionalmente (cuenta bloques de texto en `examples.md`). No hay
  patrón útil que portar de ahí.

## Orden sugerido de vendorización

Para minimizar trabajo repetido, portar en este orden (cada uno depende del
anterior estando ya en su lugar):

1. `ProviderRegistry` + adaptadores de proveedor — infraestructura pura, sin
   acoplamiento a memoria.
2. `RAGPipeline` + `HashingEmbedder` + `InMemoryVectorStore` — recuperación,
   reutilizable con cualquier tipo de documento.
3. `PermissionEngine` + política de privacidad — necesario antes de que
   exista cualquier dato de usuario real que proteger.
4. `orchestration/audit.py` adaptado — para que desde el primer claim
   guardado ya quede trazado.
5. El pipeline de memoria nivelada en sí (`01-MEMORIA-NIVELADA.md`), que es
   el único componente sin equivalente directo en Magnus.
