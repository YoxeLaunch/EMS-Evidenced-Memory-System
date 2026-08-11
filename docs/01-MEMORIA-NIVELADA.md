# Memoria nivelada — núcleo técnico

## Los cuatro niveles

| Nivel | Nombre | Qué es | Quién la citó puede... |
|---|---|---|---|
| T0 | Registro crudo | La conversación tal cual, sin procesar. | Nada — no es evidencia, es la materia prima. |
| T1 | Candidato | Una afirmación extraída de una conversación, con proveniencia a T0. | Nada por sí sola — no se puede citar como hecho. |
| T2 | Reforzado | Un candidato que se repitió en conversaciones distintas o fue confirmado explícitamente por el usuario. | Citarse con una marca visible de confianza media ("esto es algo que hemos hablado, no un hecho verificado"). |
| T3 | Promovido | Conocimiento con la misma autoridad que una fuente verificada — pasó por el evaluador de promoción o confirmación humana explícita. | Citarse igual que una fuente curada, con su propio hash y proveniencia. |

Esta tabla es la regla central del proyecto: **el evaluador de respuestas
nunca puede tratar T1 como T3.** Cada nivel tiene su propio umbral de
confianza en el evaluador (patrón heredado de `min_score` por agente en
Magnus, pero aquí también por nivel de memoria).

## Modelo de datos — `MemoryClaim`

```
MemoryClaim {
  id: str                        # hash del contenido normalizado + agente
  agent_id: str                  # a qué agente/dominio pertenece
  subject: str                   # entidad o tema (para dedup e indexado)
  text: str                      # la afirmación en sí, en forma normalizada
  tier: T0 | T1 | T2 | T3
  confidence: float              # score interno, específico del nivel
  source_conversation_ids: [str] # proveniencia — nunca se pierde
  first_seen_at: datetime
  last_reinforced_at: datetime
  reinforcement_count: int
  supersedes: id | null          # a qué claim reemplaza (si aplica)
  superseded_by: id | null       # inverso — se rellena cuando ya no es vigente
  decay_half_life_days: int      # ver "Caducidad" más abajo
  status: active | superseded | expired | rejected
}
```

`id` se deriva por hash del `(agent_id, subject, text_normalizado)`, siguiendo
el mismo patrón que el hash de chunk en `FileWikiStore` de Magnus — permite
detectar que dos conversaciones distintas produjeron el mismo candidato sin
comparar texto libre cada vez.

## El pipeline

```
Conversación (T0)
      │
      ▼
Extracción de candidatos ──────────► MemoryClaim tier=T1
      │  (determinista al inicio,                │
      │   ver "Extractor" abajo)                 │
      ▼                                            │
Deduplicación / match                              │
  contra claims existentes                         │
  (mismo subject, embedding similar) ◄─────────────┘
      │
      ├── No hay match previo ──► queda en T1, cuenta = 1
      │
      ├── Coincide con un T1/T2 existente ──► reinforcement_count += 1
      │        │
      │        └── cuenta ≥ umbral de refuerzo ──► asciende a T2
      │
      └── Contradice un claim T2/T3 existente ──► no se sobrescribe:
               se crea un nuevo claim, se marca `supersedes`,
               el viejo pasa a status=superseded (nunca se borra)

T2 candidato a promoción
      │
      ▼
Evaluador de promoción (gate)
      │
      ├── Automático: estructura similar a `citation_evaluator.py` de Magnus,
      │   pero verificando consistencia entre múltiples conversaciones
      │   en vez de anclaje a una nota fija.
      │
      └── Manual (dominios de alto riesgo): confirmación explícita del
          usuario ("sí, esto es correcto, recuérdalo así").
      │
      ▼
T3 — conocimiento citable con autoridad plena
```

### Extracción de candidatos (T0 → T1)

Empezar **determinista y estructural**, no con un extractor basado en LLM
desde el día uno — mismo criterio que llevó a Magnus a empezar con un
evaluador de citas estructural antes de considerar LLM-as-judge. Un extractor
demasiado libre desde el principio introduce el mismo riesgo que se está
tratando de evitar: alucinar candidatos que no se dijeron.

Primera versión razonable: extraer solo afirmaciones con marcadores
explícitos de la conversación (correcciones directas del usuario,
confirmaciones, datos declarados en primera persona), no inferencias del
modelo sobre lo que "probablemente" es cierto. Escalar a extracción asistida
por LLM es una fase posterior, con su propio umbral de confianza más bajo que
el marcador explícito.

### Refuerzo (T1 → T2)

Umbral configurable, no fijo en el diseño (mismo espíritu que
`routing_min_score` configurable en Magnus). Señales válidas:

- Repetición: el mismo claim (o uno semánticamente equivalente) aparece en
  ≥ N conversaciones distintas, separadas en el tiempo.
- Confirmación explícita: el usuario responde afirmativamente a un resumen
  del claim.

Señales que **no** cuentan como refuerzo: repetición dentro de la misma
conversación (es la misma fuente, no una señal independiente), ni la
confianza del modelo al generarlo (el modelo no es evidencia de sí mismo).

### Promoción (T2 → T3)

Este es el punto de mayor riesgo del sistema y el que necesita el gate más
estricto. Dos rutas, no mutuamente excluyentes:

1. **Evaluador de promoción automático** — verifica consistencia: el claim
   no contradice otro T3 activo del mismo agente, tiene refuerzo suficiente,
   y su procedencia (`source_conversation_ids`) es diversa (no todas las
   confirmaciones vinieron de una sesión de veinte minutos hablando de lo
   mismo).
2. **Confirmación humana explícita**, obligatoria para dominios de alto
   riesgo (salud, finanzas, legal) — mismo criterio que los guardrails por
   dominio de Magnus (`configs/guardrails.yaml`), aplicado aquí a la
   promoción de memoria en vez de a la respuesta.

### Contradicción y sucesión

Cuando un candidato nuevo contradice un T2/T3 activo, **nunca se resuelve
por sobrescritura**. Se crea un claim nuevo con `supersedes` apuntando al
viejo; el viejo pasa a `status=superseded` pero permanece en la base con su
proveniencia intacta. Una respuesta que use el claim vigente puede, si hace
falta, explicar que reemplazó a una creencia anterior y por qué —
trazabilidad que la sobrescritura silenciosa destruye para siempre.

Detectar la contradicción en sí (que dos afirmaciones sobre el mismo
`subject` sean incompatibles, no solo distintas) es el problema abierto más
difícil del diseño — empezar con contradicciones explícitas
("ya no como carne" tras "como carne todos los días") antes de intentar
detectar contradicciones implícitas o inferidas.

### Caducidad

Cada claim tiene `decay_half_life_days`, dependiente del tipo de hecho: una
preferencia declarada ("no me gusta el cilantro") puede tener una vida media
larga o indefinida; un dato situacional ("estoy buscando trabajo") debe
decaer en semanas o meses si no se refuerza. La confianza efectiva de un
claim en el momento de recuperarlo es una función decreciente del tiempo
desde `last_reinforced_at`, no un valor fijo — mismo principio que llevó a
Magnus a versionar la wiki por snapshot en vez de tratarla como
permanentemente válida.

Un claim cuya confianza efectiva cae bajo el umbral de su nivel no se borra
— pasa a `status=expired` y deja de ser recuperable como evidencia activa,
pero conserva proveniencia por si se reactiva (refuerzo nuevo lo revive).

## Recuperación

La recuperación reutiliza el mismo contrato `DenseRetriever` /
`LexicalRetriever` que `RAGPipeline` ya define en Magnus
(`kernel/rag/pipeline.py`) — los `MemoryClaim` de T2/T3 activos son,
funcionalmente, el mismo tipo de documento indexable que un chunk de wiki.
La diferencia real está en el evaluador que consume el resultado: debe
recibir el `tier` de cada claim recuperado y aplicar el umbral de confianza
correspondiente, y la respuesta debe marcar visiblemente cuándo se apoyó en
T2 (confianza media) frente a T3 (autoridad plena) — igual que Magnus ya
distingue una respuesta rechazada por falta de citas de una aceptada.

## Riesgo central a vigilar

Si el extractor, el detector de refuerzo o el evaluador de promoción tienen
un sesgo sistemático (por ejemplo, el modelo tiende a "recordar" con más
confianza lo que dijo él mismo en un turno anterior que lo que dijo el
usuario), el pipeline entero hereda ese sesgo silenciosamente. La auditoría
de cada promoción (qué conversaciones, qué evaluador, qué score) no es
opcional — es la única forma de detectar ese sesgo después de que ocurra.
