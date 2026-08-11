# Embudo

Infraestructura de memoria niveada para agentes que aprenden de sus propias
conversaciones — sin depender de una wiki curada a mano.

Proyecto hermano de [MagnusAgent](../MagnusAgent), pero con reglas propias:
aquí la fuente de verdad no la escribe un humano de antemano, la construye el
propio sistema a partir del diálogo, con las salvaguardas necesarias para que
eso no degenere en un eco que se autoconfirma.

## Por qué existe

En Magnus, un agente solo puede afirmar algo si está anclado en una nota que
un humano escribió y versionó por hash (`LLM-Wiki`). Eso es seguro pero no
escala: cada dominio nuevo necesita que alguien lo redacte a mano.

Embudo generaliza esa garantía sin la wiki: la conversación misma se
convierte en la fuente, pero pasa por un pipeline de niveles de confianza
antes de que algo aprendido se pueda citar con la misma autoridad que un
hecho verificado. Ver [docs/00-VISION-Y-ARQUITECTURA.md](docs/00-VISION-Y-ARQUITECTURA.md)
para la motivación completa y la analogía de origen.

## Documentación

- [docs/00-VISION-Y-ARQUITECTURA.md](docs/00-VISION-Y-ARQUITECTURA.md) — por qué, principios de diseño, reglas propias del proyecto.
- [docs/01-MEMORIA-NIVELADA.md](docs/01-MEMORIA-NIVELADA.md) — el núcleo técnico: niveles de confianza, modelo de datos, pipeline de captura → extracción → refuerzo → promoción → caducidad.
- [docs/02-COMPONENTES-REUTILIZABLES.md](docs/02-COMPONENTES-REUTILIZABLES.md) — qué se porta de MagnusAgent tal cual, qué se adapta, qué se descarta.
- [docs/03-ROADMAP.md](docs/03-ROADMAP.md) — plan de construcción por fases, con criterio de hecho por fase.

## Estado

Fases 0-6 de `docs/03-ROADMAP.md` implementadas y en verde (`pytest`):
empaquetado, infraestructura vendorizada de MagnusAgent (`providers/`,
`rag/`, `orchestration/`), y el pipeline de memoria nivelada completo
(`memory/`) — captura T0, extracción T1, refuerzo/sucesión T2, evaluador de
promoción T3, recuperación integrada por nivel, y caducidad/revival.

Pendiente: Fase 7 (piloto acotado) — por diseño no es algo que se complete
escribiendo código; necesita un agente real, un dominio de riesgo medio-bajo
y conversaciones genuinas de uso durante un periodo de prueba.
