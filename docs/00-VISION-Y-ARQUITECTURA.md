# Visión y arquitectura — EMS (Evidenced Memory System)

## El problema que resuelve

Un modelo de lenguaje grande contiene, en la práctica, una cantidad de
conocimiento que ningún ser humano puede sostener a la vez. Eso es potencia,
no utilidad — la utilidad aparece cuando ese conocimiento se filtra hasta el
tamaño y la forma de una vida concreta: la tuya, hoy, con tus datos, tu
contexto, tus contradicciones resueltas o sin resolver.

En [MagnusAgent](../../MagnusAgent) ese filtro existe, pero depende de una
pieza que un humano tiene que escribir a mano: la `LLM-Wiki`. El evaluador de
citas solo deja pasar una respuesta si está anclada en una nota que alguien
redactó y versionó. Es una garantía fuerte — y también un cuello de botella:
no escala a dominios que nadie se ha sentado a documentar, y no aprende de la
conversación misma.

**EMS pregunta: ¿se puede mantener esa misma garantía —que el sistema
nunca hable con la autoridad de un hecho verificado sobre algo que no lo
es— sin exigir que un humano escriba la fuente de antemano?**

La respuesta no es "dejar que el modelo recuerde lo que quiera". Es
construir un pipeline donde lo que una conversación produce entra como
**candidato**, no como hecho, y solo asciende a autoridad plena después de
pasar por refuerzo, contradicción resuelta y —en los dominios que lo
requieran— confirmación explícita. Ese pipeline nivelado es el núcleo técnico
de este proyecto y se documenta en
[01-MEMORIA-NIVELADA.md](01-MEMORIA-NIVELADA.md).

## Principios de diseño (reglas propias del proyecto)

Estas reglas son más estrictas que las de Magnus en el punto donde EMS es
estructuralmente más arriesgado (memoria que se escribe sola), y heredan de
Magnus donde ya se demostraron necesarias.

1. **Ninguna memoria autoescrita tiene la autoridad de un hecho verificado
   hasta que se promueve explícitamente.** Un evaluador que cite memoria de
   nivel candidato con la misma confianza que memoria promovida rompe la
   garantía entera del sistema — es el error central a evitar, documentado en
   detalle en `01-MEMORIA-NIVELADA.md`.
2. **Nada se sobrescribe en silencio.** Un hecho nuevo que contradice uno
   viejo genera una relación de sucesión (`supersedes`/`superseded_by`) con
   fecha y motivo, nunca un `UPDATE` que borra el rastro. Heredado del patrón
   de `snapshot_id` de `FileWikiStore` en Magnus.
3. **El refuerzo exige repetición o confirmación, nunca una sola mención.**
   Una preferencia dicha una vez en una conversación no compite en igualdad
   con algo dicho y sostenido en tres. Ver criterios exactos en
   `01-MEMORIA-NIVELADA.md`.
4. **Todo conocimiento caduca.** Sin renovación, un hecho pierde peso con el
   tiempo — el sistema no puede tratar por igual algo aprendido hoy y algo
   aprendido hace dos años sin volver a confirmarse.
5. **Denegación de egreso por defecto.** Ningún namespace ni claim sale del
   dispositivo salvo que una política lo autorice explícitamente. Heredado
   sin cambios de `configs/privacy.yaml` + `orchestration/privacy.py` de
   Magnus — ese diseño ya es correcto para este problema.
6. **No hay sandboxing real todavía en Magnus para herramientas
   `python`/`terminal` — EMS no activa ejecución de herramientas
   arbitrarias hasta que exista un sandbox de verdad (contenedor + límites de
   recursos + red bloqueada), auditado como tal.** Es una lección directa del
   análisis de seguridad de Magnus: no repetir la promesa de aislamiento sin
   el mecanismo detrás.
7. **Todo es auditable y explicable por nivel.** Una respuesta debe poder
   decir, para cada afirmación que hace, de qué nivel de memoria vino, cuándo
   se reforzó por última vez y si superó algo anterior. Sin eso, "aprende y
   mejora" es indistinguible de "olvida por qué creía lo que creía".

## Relación con MagnusAgent

EMS no es un fork de Magnus ni depende de él en tiempo de ejecución. Es un
proyecto separado, con su propio `pyproject.toml`, sus propias reglas de
seguridad (más estrictas donde hace falta) y su propio ciclo de vida. Donde
Magnus ya resolvió un problema general —enrutado por capacidades,
recuperación híbrida, resiliencia de proveedores, permisos por intersección,
egreso denegado por defecto— EMS **porta el patrón, no necesariamente el
código tal cual**, evaluando en cada caso si conviene vendorizar el módulo o
reimplementarlo con el modelo de datos propio. El detalle componente por
componente está en
[02-COMPONENTES-REUTILIZABLES.md](02-COMPONENTES-REUTILIZABLES.md).

## Qué NO es EMS

- No es un sustituto de la wiki curada — para dominios de alto riesgo
  (médico, financiero, legal), una fuente verificada por humano seguirá
  siendo preferible y EMS debería poder consumirla como una fuente de
  nivel máximo desde el primer día, no solo aprender de cero.
- No es un oráculo de verdad absoluta ni pretende resolver qué es
  objetivamente cierto — resuelve **qué puede el sistema afirmar con qué
  nivel de confianza y por qué**, que es un problema distinto y más
  tratable.
- No incluye, en esta primera versión, ejecución de herramientas ni acceso a
  sistemas externos más allá de los proveedores de modelos — ver principio 6.
