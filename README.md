<div align="center">

# 🛡️ EMS — Evidenced Memory System

### Capa de gobernanza de memoria y procedencia verificable para agentes de IA (Anti-Eco & Local-First)

[![Python 3.10+](https://img.shields.io/badge/PYTHON-3.10%2B-0288D1?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License Apache 2.0](https://img.shields.io/badge/LICENSE-APACHE%202.0-D32F2F?style=for-the-badge)](LICENSE)
[![Tests Passed](https://img.shields.io/badge/TESTS-177%2F177%20PASSED-00C853?style=for-the-badge&logo=pytest&logoColor=white)]()
[![Privacy Local-First](https://img.shields.io/badge/PRIVACY-LOCAL--FIRST-FF6D00?style=for-the-badge)]()
[![Storage SQLite + JSONL](https://img.shields.io/badge/STORAGE-SQLITE%20%2B%20JSONL-546E7A?style=for-the-badge&logo=sqlite&logoColor=white)]()

<br/>

[ **Español** ] • [ **English Version** ](README.en.md)

</div>

---

> **La mayoría de sistemas de memoria guardan lo que se dijo.**  
> **EMS guarda lo que un agente puede usar responsablemente.**

```text
Conversación (T0) ➔ Candidata Extraída (T1) ➔ Evidencia Reforzada (T2) ➔ Conocimiento Promovido (T3)
```

---

## 📑 Tabla de Contenidos

- [El Problema que Resuelve](#-el-problema-que-resuelve)
- [Garantías Centrales y Principios](#-garantías-centrales-y-principios)
- [Niveles de Confianza (T0 – T4)](#-niveles-de-confianza-t0--t4)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Motor Anti-Eco y Sucesión Temporal](#-motor-anti-eco-y-sucesión-temporal)
- [Guía de Inicio Rápido](#-guía-de-inicio-rápido)
  - [Instalación](#instalación)
  - [Uso con la Fachada Python](#uso-con-la-fachada-python)
  - [Inspección con CLI](#inspección-con-cli)
- [Modelo de Datos (`MemoryClaim`)](#-modelo-de-datos-memoryclaim)
- [Estado del Proyecto](#-estado-del-proyecto)
- [Documentación Técnica](#-documentación-técnica)
- [Posicionamiento](#-posicionamiento)

---

## 🔍 El Problema que Resuelve

Las memorias conversacionales convencionales sufren del **bucle de eco**:
1. Una afirmación no verificada surge durante un diálogo.
2. El agente la almacena directamente en un vector store como verdad absoluta.
3. En turnos posteriores, el agente recupera su propia salida pasada y la asume como hecho externo irrefutable.
4. Con el tiempo, el error se amplifica y el conocimiento del agente se corrompe.

**EMS previene este bucle.** Lo conversado es tratado estrictamente como materia prima no citable. Para que una afirmación adquiera autoridad, debe ascender por un pipeline epistémico de refuerzo en múltiples sesiones independientes, resolución de contradicciones, evaluación de consistencia y caducidad temporal.

---

## 🛡️ Garantías Centrales y Principios

- 🏷️ **Confianza Nivelada (T0–T4)**: Separación estricta entre el log crudo, hipótesis extraídas, evidencia empírica reforzada y conocimiento promovido.
- 🔗 **Procedencia Inmutable**: Cada afirmación preserva su cadena de custodia e IDs de las conversaciones de origen.
- 🔀 **Sucesión Explícita (Append-Only)**: Nada se sobreescribe en silencio. Las contradicciones generan relaciones `supersedes` / `superseded_by`.
- ⏳ **Caducidad Temporal**: El conocimiento no reconfirmado pierde peso según vidas medias configurables.
- 🔒 **Consentimiento Obligatorio**: Denegación de salida de datos por defecto. Ningún turno se procesa sin autorización previa.
- ⚡ **Local-First y Resiliente**: SQLite en modo WAL, almacenamiento plano JSONL para T0, y caché de recuperación invalidada por snapshot de base de datos.

---

## 📊 Niveles de Confianza (T0 – T4)

```mermaid
graph LR
    T0["<b>T0: Registro Crudo</b><br/>Diálogo sin procesar<br/><i>Consentimiento previo</i>"] -->|Extracción Determinista| T1["<b>T1: Candidata</b><br/>Hipótesis aislada<br/><i>No citable</i>"]
    T1 -->|Refuerzo multi-sesión| T2["<b>T2: Evidencia Reforzada</b><br/>Evidencia recurrente<br/><i>Citable con incertidumbre visible</i>"]
    T2 -->|Evaluador de Promoción / Humano| T3["<b>T3: Conocimiento Promovido</b><br/>Autoridad plena<br/><i>Citable con procedencia</i>"]
    T4["<b>T4: Fuente Curada</b><br/>Verificada por humano<br/><i>⏳ Decidido — pendiente (Fase D)</i>"] -.->|Ancla de verdad| T3

    classDef t0 fill:#eceff1,stroke:#607d8b,stroke-width:2px,color:#263238;
    classDef t1 fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,color:#f57f17;
    classDef t2 fill:#ffe0b2,stroke:#fb8c00,stroke-width:2px,color:#e65100;
    classDef t3 fill:#c8e6c9,stroke:#43a047,stroke-width:2px,color:#1b5e20;
    classDef t4 fill:#bbdefb,stroke:#1e88e5,stroke-width:2px,color:#0d47a1;

    class T0 t0;
    class T1 t1;
    class T2 t2;
    class T3 t3;
    class T4 t4;
```

| Nivel | Nombre | Naturaleza | ¿Se puede citar como hecho? | Integración en Prompt |
|:---:|:---|:---|:---:|:---|
| **T0** | **Registro Crudo** | Diálogo crudo persistido con consentimiento explícito. | ❌ **No** | Excluido de la recuperación RAG. |
| **T1** | **Candidata Extraída** | Afirmación detectada en una sola sesión. | ❌ **No** | En observación interna. Nunca citada al usuario. |
| **T2** | **Evidencia Reforzada** | Afirmación validada en múltiples conversaciones distintas. | ⚠️ **Con Incertidumbre** | Inyectada con etiqueta visible `confianza_media`. |
| **T3** | **Conocimiento Promovido** | Superó el evaluador de consistencia o validación humana. | ✅ **Sí** | Inyectada con `autoridad_plena` y hash de procedencia. |
| **T4** | **Fuente Curada** ⏳ | Documentación o verdad ingresada por humano. **Decidido ([D-11] del log), pendiente de implementar (Fase D).** | ✅ (al implementarse) | Máxima precedencia operativa ante conflictos. |

---

## 🏛️ Arquitectura del Sistema

```mermaid
flowchart TB
    subgraph Ingestion ["1. Ingestión & Consentimiento"]
        Turn["Turno Usuario / Agente"] --> ConsentGate{"¿Consentimiento Concedido?"}
        ConsentGate -- No --> ConsentError["Error: ConsentRequired"]
        ConsentGate -- Sí --> T0Store[("Store T0: JSONL")]
    end

    subgraph Extraction ["2. Extracción & Deduplicación"]
        T0Store --> Extractor["Extractor Estructural"]
        Extractor --> CandidateClaim["Candidata T1"]
    end

    subgraph CoreEngine ["3. Motor Epistémico Anti-Eco"]
        CandidateClaim --> Matcher{"¿Coincide con claims existentes?"}
        Matcher -- "Nuevo Sujeto" --> SaveT1["Guardar T1 (cuenta = 1)"]
        Matcher -- "Coincidencia Semántica" --> IncReinforce["reinforcement_count + 1"]
        IncReinforce --> CheckThresh{"¿cuenta >= umbral?"}
        CheckThresh -- Sí --> UpgradeT2["Ascender a T2 (Evidencia)"]
        CheckThresh -- No --> KeepT1["Mantener en T1"]
        Matcher -- "Contradicción Detectada" --> HandleSupersede["Crear nuevo Claim<br/>marcar 'supersedes'<br/>anterior pasa a 'superseded'"]
    end

    subgraph Storage ["4. Persistencia & Auditoría"]
        SaveT1 --> Sqlite[("SQLite ClaimStore + Log de Custodia")]
        UpgradeT2 --> Sqlite
        KeepT1 --> Sqlite
        HandleSupersede --> Sqlite
    end

    subgraph Promotion ["5. Puerta de Promoción"]
        Sqlite --> PromoGate{"Evaluador de Promoción"}
        PromoGate -- "Consistencia Multi-Conversación O Humano" --> UpgradeT3["Promover a T3 (Promovido)"]
        UpgradeT3 --> Sqlite
    end

    subgraph Retrieval ["6. Recuperación & Contexto"]
        Sqlite --> Retriever["Cached Tiered Retriever (Invalida por Snapshot)"]
        Retriever --> RAGContext["Constructor de Contexto RAG"]
        RAGContext --> PromptBlock["Prompt del Agente (Etiquetado T2 / T3)"]
    end

    classDef db fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef logic fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1.5px;
    classDef gate fill:#fff3e0,stroke:#e65100,stroke-width:1.5px;

    class T0Store,Sqlite db;
    class Extractor,IncReinforce,HandleSupersede,Retriever,RAGContext logic;
    class ConsentGate,Matcher,CheckThresh,PromoGate gate;
```

---

## 🔄 Motor Anti-Eco y Sucesión Temporal

Cuando la información del mundo real cambia, EMS aplica **Sucesión Explícita** en lugar de sobreescritura destructiva:

```mermaid
sequenceDiagram
    autonumber
    actor Usuario
    participant EMS as Fachada Embudo
    participant DB as SQLite ClaimStore

    Note over Usuario, DB: Fase 1: Declaración (entra como T1)
    Usuario->>EMS: "Como carne todos los días"
    EMS->>DB: Guarda Claim #101 (Sujeto: carne, Tier: T1, Estado: active)

    Note over Usuario, DB: Fase 2: Cambio de estado declarado
    Usuario->>EMS: "Ya no como carne"
    EMS->>EMS: Negación explícita detectada ANTES del match semántico
    EMS->>DB: Crea Claim #205 (Tier: T1 — no hereda autoridad, supersedes: #101)
    EMS->>DB: Marca #101 (Estado: superseded, superseded_by: #205) + evento de custodia

    Note over Usuario, DB: Fase 3: Recuperación
    Usuario->>EMS: "¿Qué como?"
    EMS->>DB: Recupera únicamente claims activos T2/T3
    DB-->>EMS: #205 sigue en T1 → aún no citable como hecho
    EMS-->>Usuario: Sin evidencia citable todavía (necesita refuerzo multi-sesión)

    Note over Usuario, DB: La detección es EXPLÍCITA (negación literal con<br/>prefijos "ya no/dejé de"); la contradicción implícita o semántica<br/>("me mudé a otra ciudad") es problema abierto, no prometido.
```

---

## 🚀 Guía de Inicio Rápido

### Instalación

```bash
git clone https://github.com/YoxeLaunch/EMS-Evidenced-Memory-System.git
cd EMS-Evidenced-Memory-System
pip install -e .
```

### Uso con la Fachada Python

```python
from datetime import datetime, timezone

from ems import EMS
from memory.capture import Consent, Turn

# 1. Abrir la base de datos de memoria persistente
with EMS.open("memoria.db") as memoria:
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 2. Registrar turno con consentimiento explícito del usuario
    #    (sin Consent concedido no se escribe NADA — ConsentRequired)
    consentimiento = Consent(
        granted=True,
        scope="raw_conversation",
        granted_by="usuario-1",
        granted_at=ahora,
    )

    record, claims = memoria.register_conversation(
        [Turn("user", "Soy alérgico a la penicilina.", ahora)],
        agent_id="dr_soma",
        user_id="usuario-1",
        consent=consentimiento,
    )

    print(f"ID conversación registrada: {record.id}")
    for c in claims:
        print(f"Claim [{c.tier.value}]: {c.subject} -> {c.text}")

    # 3. Recuperar contexto clasificado para el LLM (solo T2/T3 activos)
    contexto = memoria.recall("alergico a la penicilina", agent_id="dr_soma")
    print("\n--- Bloque RAG Nivelado ---")
    print(contexto.as_prompt_block())
```

### Inspección con CLI

```bash
# Ver métricas de salud, claims activos y eventos de custodia
ems stats memoria.db
```

Salida (ejemplo real):
```text
EMS v0.2.0 — memoria.db
esquema: v2
claims activos: 14 (T1 4, T2 8, T3 2)
estados: active 14, expired 1, superseded 3
eventos de custodia: extraction 18, expiration 1, promotion 2, reinforcement 9, supersession 3
conversaciones T0: 12
construcciones de índice: 4
```

---

## 🧱 Modelo de Datos (`MemoryClaim`)

```python
@dataclass
class MemoryClaim:
    id: str                        # Hash determinista de (agent_id, subject, texto_normalizado)
    agent_id: str                  # Espacio de nombres / identificador del agente
    subject: str                   # Entidad o tema normalizado (para indexado y deduplicación)
    text: str                      # La afirmación tal cual se dijo
    tier: Tier                     # T1 | T2 | T3 (T0 es la conversación, no un claim)
    confidence: float              # Confianza base según el marcador de extracción (fija)
    source_conversation_ids: list  # Trazabilidad completa hacia los registros T0 originales
    first_seen_at: str             # Marca de tiempo UTC de primera captura
    last_reinforced_at: str        # Marca de tiempo UTC del último refuerzo
    reinforcement_count: int       # Confirmaciones en conversaciones independientes
    supersedes: str | None         # ID de la afirmación anterior reemplazada por esta
    superseded_by: str | None      # ID de la afirmación sucesora si fue invalidada
    decay_half_life_days: int      # Vida media en días (<= 0: sin caducidad)
    status: Status                 # active | superseded | expired | rejected
```

---

## 📈 Estado del Proyecto

**Todo lo listado abajo está implementado y verificado por la suite (177 tests, offline, 100% determinista, sin LLM ni credenciales).**

| Componente | Estado |
|---|---|
| Pipeline T0→T3 completo (captura, extracción, refuerzo, promoción, caducidad, revival) | ✅ |
| Anti-eco: contradicción antes que match, refuerzo multi-sesión, sucesión no destructiva | ✅ |
| `SqliteClaimStore` + cadena de custodia transaccional (events con payload canónico, FK, migraciones versionadas) | ✅ |
| Fachada pública `embudo` + CLI `embudo stats` | ✅ |
| Índice de recuperación con invalidación por snapshot | ✅ |
| Confianza acumulativa derivada (telemetría, no gate) | ✅ |

**Pendiente (decidido en el log de colaboración, sin implementar):** T4 — wiki como fuente curada y exportador T3→nota (Fase D); bridge con MagnusAgent vía su puerto `MemoryEngine` (Fase C, vive en Magnus como dependencia opcional); extractor asistido por LLM y LLM-as-judge de promoción (Fase E); Camino de Aprendizaje por dominios (Fase F); CI y derecho al olvido (Fase G); piloto real de Fase 7 — el sustrato técnico ya está completo.

> Regla del proyecto: la documentación no se adelanta al código. Si algo de arriba dice ✅, hay un test que lo demuestra; si dice pendiente, aún no existe.

---

## 📚 Documentación Técnica

- 📖 [**00 - Visión y Arquitectura**](docs/00-VISION-Y-ARQUITECTURA.md): Motivación, filosofía epistémica y principios de diseño anti-eco.
- ⚙️ [**01 - Memoria Nivelada**](docs/01-MEMORIA-NIVELADA.md): Núcleo técnico: captura, extracción, refuerzo, promoción y caducidad.
- 🧩 [**02 - Componentes Reutilizables**](docs/02-COMPONENTES-REUTILIZABLES.md): Arquitectura modular, RAG, almacenamiento y proveedores.
- 🗺️ [**03 - Roadmap del Proyecto**](docs/03-ROADMAP.md): Fases del desarrollo y criterios de validación.
- 🤝 [**Bitácora de Colaboración**](COLABORACION.md): Registro de decisiones técnicas y puntos de control.

---

## 💡 Posicionamiento

> **"La confianza de un LLM nunca es evidencia."**  
> **"Las contradicciones crean sucesión, no sobrescrituras silenciosas."**

EMS no es una simple función de memoria para chatbots. Es un **sistema de gobernanza de memoria para agentes de IA**: una capa reutilizable entre la conversación, la recuperación semántica, el conocimiento curado por humanos y el aprendizaje a largo plazo.

---

<div align="center">
  <sub>Construido para agentes que aprenden de la experiencia sin confundir repetición con verdad.</sub>
</div>
