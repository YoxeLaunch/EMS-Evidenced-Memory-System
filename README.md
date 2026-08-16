# EMS — Evidenced Memory System  
# EMS — Sistema de Memoria Basada en Evidencia

**A provenance-first memory layer for AI agents.**  
**Una capa de memoria con procedencia verificable para agentes de IA.**

Most agent memory systems store what was said.  
EMS stores what can be responsibly used.

La mayoría de sistemas de memoria guardan lo que se dijo.  
EMS guarda lo que un agente puede usar responsablemente.

```text
Conversation → candidate → reinforced evidence → promoted knowledge
Conversación → candidata → evidencia reforzada → conocimiento promovido
```

---

## Why EMS? / ¿Por qué EMS?

Agent memory can create an echo loop: a statement is remembered, repeated, and eventually treated as true.

EMS prevents that feedback loop.

La memoria de un agente puede crear un bucle de eco: una afirmación se recuerda, se repite y termina tratándose como verdadera.

EMS evita ese bucle.

- **Tiered trust / Confianza por niveles** — memory progresses from raw conversation to candidate, reinforced evidence, and promoted knowledge.
- **Provenance by default / Procedencia por defecto** — every claim is traceable to its source conversations and custody events.
- **Anti-echo design / Diseño anti-eco** — contradiction is checked before semantic similarity; repetition in one conversation is not evidence.
- **Append-only history / Historial append-only** — claims are superseded, never silently overwritten.
- **Temporal validity / Validez temporal** — knowledge decays without reconfirmation.
- **Local-first / Local-first** — deterministic core, SQLite persistence, no required cloud dependency.
- **Agent-ready / Listo para agentes** — retrieval preserves confidence labels, so weak claims are never presented as verified facts.

---

## Trust tiers / Niveles de confianza

| Tier | Meaning / Significado | Can it be cited as fact? / ¿Se puede citar como hecho? |
|---|---|---|
| **T0** | Raw conversation / Registro crudo | No |
| **T1** | Extracted candidate / Candidata extraída | No |
| **T2** | Reinforced evidence / Evidencia reforzada | Only with visible uncertainty / Solo con incertidumbre visible |
| **T3** | Promoted knowledge / Conocimiento promovido | Yes, with provenance / Sí, con procedencia |
| **T4** | Human-curated source / Fuente curada por humano | Yes, highest operational precedence / Sí, máxima precedencia operativa |

---

## The core guarantee / La garantía central

> **An LLM’s confidence is never evidence.**  
> *La confianza de un LLM nunca es evidencia.*

> **Contradictions create succession, not silent overwrites.**  
> *Las contradicciones crean sucesión, no sobrescrituras silenciosas.*

---

## Positioning / Posicionamiento

EMS is not a chatbot memory feature. It is a **memory governance system for AI agents**: a reusable layer between conversation, retrieval, human-curated knowledge, and long-term learning.

EMS no es una función de “memoria para chatbots”. Es un **sistema de gobernanza de memoria para agentes de IA**: una capa reutilizable entre conversación, recuperación, conocimiento curado por humanos y aprendizaje de largo plazo.

---

## Documentation / Documentación

- [docs/00-VISION-Y-ARQUITECTURA.md](docs/00-VISION-Y-ARQUITECTURA.md) — Visión, motivación y principios de diseño anti-eco.
- [docs/01-MEMORIA-NIVELADA.md](docs/01-MEMORIA-NIVELADA.md) — Núcleo técnico: pipeline de captura → extracción → refuerzo → promoción → caducidad.
- [docs/02-COMPONENTES-REUTILIZABLES.md](docs/02-COMPONENTES-REUTILIZABLES.md) — Arquitectura modular y componentes de soporte.
- [docs/03-ROADMAP.md](docs/03-ROADMAP.md) — Fases de desarrollo y criterios de validación.

---

*Built for agents that should learn from experience without mistaking repetition for truth.*  
*Construido para agentes que aprendan de la experiencia sin confundir repetición con verdad.*
