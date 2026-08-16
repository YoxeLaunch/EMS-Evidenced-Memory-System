<div align="center">

# 🛡️ EMS — Evidenced Memory System

### A provenance-first memory governance layer for AI agents (Anti-Echo & Local-First)

[![Python 3.10+](https://img.shields.io/badge/PYTHON-3.10%2B-0288D1?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License Apache 2.0](https://img.shields.io/badge/LICENSE-APACHE%202.0-D32F2F?style=for-the-badge)](LICENSE)
[![Tests Passed](https://img.shields.io/badge/TESTS-177%2F177%20PASSED-00C853?style=for-the-badge&logo=pytest&logoColor=white)]()
[![Privacy Local-First](https://img.shields.io/badge/PRIVACY-LOCAL--FIRST-FF6D00?style=for-the-badge)]()
[![Storage SQLite + JSONL](https://img.shields.io/badge/STORAGE-SQLITE%20%2B%20JSONL-546E7A?style=for-the-badge&logo=sqlite&logoColor=white)]()

<br/>

[ **Español** ](README.md) • [ **English Version** ]

</div>

---

> **Most agent memory systems store what was said.**  
> **EMS stores what can be responsibly used.**

```text
Conversation (T0) ➔ Extracted Candidate (T1) ➔ Reinforced Evidence (T2) ➔ Promoted Knowledge (T3)
```

---

## 📑 Table of Contents

- [The Core Problem](#-the-core-problem)
- [Key Features & Guarantees](#-key-features--guarantees)
- [Trust Tiers (T0 – T4)](#-trust-tiers-t0--t4)
- [System Architecture](#-system-architecture)
- [Anti-Echo & Succession Engine](#-anti-echo--succession-engine)
- [Quick Start](#-quick-start)
  - [Installation](#installation)
  - [Python Facade Usage](#python-facade-usage)
  - [CLI Inspection](#cli-inspection)
- [Data Model (`MemoryClaim`)](#-data-model-memoryclaim)
- [Project Status](#-project-status)
- [Technical Documentation](#-technical-documentation)
- [Positioning](#-positioning)

---

## 🔍 The Core Problem

Standard agent architectures suffer from **conversational echo loops**:
1. An unverified claim or hallucination is uttered during a dialogue.
2. The agent commits it directly to a vector store as an absolute truth.
3. In subsequent turns, the agent retrieves its own past output and treats it as external fact.
4. Over time, error amplifies, and knowledge corrupts.

**EMS breaks this loop.** In EMS, conversational input is treated strictly as raw, non-citable material. For a claim to gain epistemic authority, it must advance through a tiered pipeline of multi-session reinforcement, contradiction resolution, consistency evaluation, and temporal decay.

---

## 🛡️ Key Features & Guarantees

- 🏷️ **Tiered Trust (T0–T4)**: Strict separation between raw chat, extracted hypotheses, reinforced empirical evidence, and promoted knowledge.
- 🔗 **Immutable Provenance**: Every claim preserves its custody chain and source conversation IDs.
- 🔀 **Explicit Succession (Append-Only)**: Nothing is silently overwritten. Contradictions generate explicit `supersedes` / `superseded_by` links.
- ⏳ **Temporal Decay**: Knowledge not reconfirmed loses weight over configurable half-lives.
- 🔒 **Consent-First**: Zero egress by default. Processing conversation logs strictly requires user authorization before touching disk.
- ⚡ **Local-First & Resilient**: SQLite in WAL mode, JSONL source storage, and snapshot-invalidated cache retrievers.

---

## 📊 Trust Tiers (T0 – T4)

```mermaid
graph LR
    T0["<b>T0: Raw Record</b><br/>Unprocessed dialogue<br/><i>Consent gated</i>"] -->|Deterministic Extraction| T1["<b>T1: Candidate</b><br/>Isolated hypothesis<br/><i>Not citable</i>"]
    T1 -->|Multi-session reinforcement| T2["<b>T2: Reinforced Evidence</b><br/>Recurrent evidence<br/><i>Citable with visible uncertainty</i>"]
    T2 -->|Promotion Evaluator / Human gate| T3["<b>T3: Promoted Knowledge</b><br/>Full authority memory<br/><i>Citable with provenance</i>"]
    T4["<b>T4: Human Curated</b><br/>Hand-curated knowledge<br/><i>⏳ Decided — pending (Phase D)</i>"] -.->|Benchmark & Anchor| T3

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

| Tier | Name | Nature | Can it be cited as fact? | Integration in Prompt |
|:---:|:---|:---|:---:|:---|
| **T0** | **Raw Conversation** | Unprocessed dialogue stream with explicit consent. | ❌ **No** | Excluded from RAG retrieval context. |
| **T1** | **Extracted Candidate** | Explicit statement extracted structurally from a single session. | ❌ **No** | Under observation. Never cited to the agent. |
| **T2** | **Reinforced Evidence** | Candidate validated across multiple distinct sessions. | ⚠️ **With Uncertainty** | Injected with a visible `confianza_media` label. |
| **T3** | **Promoted Knowledge** | Passed strict multi-session promotion evaluator or human approval. | ✅ **Yes** | Injected with full authority and origin hash. |
| **T4** | **Human Curated Source** ⏳ | Verified documentation or human-edited truth. **Decided ([D-11] in the log), pending implementation (Phase D).** | ✅ (once implemented) | Highest operational precedence on conflict. |

---

## 🏛️ System Architecture

```mermaid
flowchart TB
    subgraph Ingestion ["1. Ingestion & Consent Gate"]
        Turn["User / Agent Conversation Turn"] --> ConsentGate{"Consent Granted?"}
        ConsentGate -- No --> ConsentError["Error: ConsentRequired"]
        ConsentGate -- Yes --> T0Store[("T0 Store: JSONL")]
    end

    subgraph Extraction ["2. Extraction & Deduplication"]
        T0Store --> Extractor["Structural Extractor"]
        Extractor --> CandidateClaim["Candidate Claim (T1)"]
    end

    subgraph CoreEngine ["3. Epistemic Core (Anti-Echo)"]
        CandidateClaim --> Matcher{"Match existing claims?"}
        Matcher -- "New Subject" --> SaveT1["Store T1 (count = 1)"]
        Matcher -- "Semantic Match" --> IncReinforce["reinforcement_count + 1"]
        IncReinforce --> CheckThresh{"count >= threshold?"}
        CheckThresh -- Yes --> UpgradeT2["Promote to T2 (Evidence)"]
        CheckThresh -- No --> KeepT1["Stay in T1"]
        Matcher -- "Contradiction Detected" --> HandleSupersede["Create new Claim<br/>mark 'supersedes'<br/>old becomes 'superseded'"]
    end

    subgraph Storage ["4. Persistence & Audit"]
        SaveT1 --> Sqlite[("SQLite ClaimStore + Custody Log")]
        UpgradeT2 --> Sqlite
        KeepT1 --> Sqlite
        HandleSupersede --> Sqlite
    end

    subgraph Promotion ["5. Promotion Gate"]
        Sqlite --> PromoGate{"Promotion Evaluator"}
        PromoGate -- "Multi-conversation consistency OR Human gate" --> UpgradeT3["Promote to T3 (Promoted)"]
        UpgradeT3 --> Sqlite
    end

    subgraph Retrieval ["6. Retrieval & Prompt Integration"]
        Sqlite --> Retriever["Cached Tiered Retriever (Snapshot-Aware)"]
        Retriever --> RAGContext["Tiered RAG Context Builder"]
        RAGContext --> PromptBlock["Agent Prompt (Labeled T2 / T3)"]
    end

    classDef db fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef logic fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1.5px;
    classDef gate fill:#fff3e0,stroke:#e65100,stroke-width:1.5px;

    class T0Store,Sqlite db;
    class Extractor,IncReinforce,HandleSupersede,Retriever,RAGContext logic;
    class ConsentGate,Matcher,CheckThresh,PromoGate gate;
```

---

## 🔄 Anti-Echo & Succession Engine

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant EMS as Embudo Facade
    participant DB as SQLite ClaimStore

    Note over User, DB: Phase 1: Statement (enters as T1)
    User->>EMS: "I eat meat every day"
    EMS->>DB: Save Claim #101 (Subject: meat, Tier: T1, Status: active)

    Note over User, DB: Phase 2: Declared change of state
    User->>EMS: "I no longer eat meat"
    EMS->>EMS: Explicit negation detected BEFORE semantic match
    EMS->>DB: Create Claim #205 (Tier: T1 — inherits no authority, supersedes: #101)
    EMS->>DB: Mark #101 (Status: superseded, superseded_by: #205) + custody event

    Note over User, DB: Phase 3: Retrieval
    User->>EMS: Recall "what do I eat?"
    EMS->>DB: Query active T2/T3 claims only
    DB-->>EMS: #205 is still T1 → not citable as fact yet
    EMS-->>User: No citable evidence yet (needs multi-session reinforcement)

    Note over User, DB: Detection is EXPLICIT (literal negation with<br/>"ya no / dejé de" prefixes); implicit or semantic contradiction<br/>("I moved to another city") is an open problem, not a promise.
```

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/YoxeLaunch/EMS-Evidenced-Memory-System.git
cd EMS-Evidenced-Memory-System
pip install -e .
```

### Python Facade Usage

```python
from datetime import datetime, timezone
from embudo import Embudo
from memory.capture import Turn, Consent

# 1. Open persistent local memory store
with Embudo.open("memory.db") as memory:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 2. Register conversation turn with explicit user consent
    #    (nothing is written without granted consent — ConsentRequired)
    consent = Consent(
        granted=True,
        scope="raw_conversation",
        granted_by="user_123",
        granted_at=now_iso,
    )

    record, claims = memory.register_conversation(
        [Turn("user", "I am severely allergic to penicillin.", now_iso)],
        agent_id="medical_agent",
        user_id="user_123",
        consent=consent,
    )

    print(f"Captured record ID: {record.id}")
    for c in claims:
        print(f"Claim [{c.tier.value}]: {c.subject} -> {c.text}")

    # 3. Retrieve tiered context for the LLM prompt (active T2/T3 only)
    context = memory.recall("penicillin allergy", agent_id="medical_agent")
    print("\n--- Tiered Prompt Block ---")
    print(context.as_prompt_block())
```

### CLI Inspection

```bash
# View memory database statistics and custody metrics
embudo stats memory.db
```

Output (real example):
```text
Embudo v0.2.0 — memory.db
esquema: v2
claims activos: 14 (T1 4, T2 8, T3 2)
estados: active 14, expired 1, superseded 3
eventos de custodia: extraction 18, expiration 1, promotion 2, reinforcement 9, supersession 3
conversaciones T0: 12
construcciones de índice: 4
```

---

## 🧱 Data Model (`MemoryClaim`)

```python
@dataclass
class MemoryClaim:
    id: str                        # Deterministic hash of (agent_id, subject, normalized_text)
    agent_id: str                  # Isolated namespace / agent identifier
    subject: str                   # Normalized topic or entity (for indexing and deduplication)
    text: str                      # The claim as it was said
    tier: Tier                     # T1 | T2 | T3 (T0 is the conversation, not a claim)
    confidence: float              # Base confidence from the extraction marker (fixed)
    source_conversation_ids: list  # Full provenance tracking back to T0 logs
    first_seen_at: str             # UTC ISO timestamp of first capture
    last_reinforced_at: str        # UTC ISO timestamp of latest reinforcement
    reinforcement_count: int       # Confirmations across independent sessions
    supersedes: str | None         # ID of past claim replaced by this one
    superseded_by: str | None      # ID of successor claim if invalidated
    decay_half_life_days: int      # Half-life in days (<= 0: never decays)
    status: Status                 # active | superseded | expired | rejected
```

---

## 📈 Project Status

**Everything listed below is implemented and verified by the test suite (177 tests, offline, 100% deterministic, no LLM, no credentials).**

| Component | Status |
|---|---|
| Full T0→T3 pipeline (capture, extraction, reinforcement, promotion, decay, revival) | ✅ |
| Anti-echo: contradiction before match, multi-session reinforcement, non-destructive succession | ✅ |
| `SqliteClaimStore` + transactional custody chain (canonical event payloads, FK, versioned migrations) | ✅ |
| Public `embudo` facade + `embudo stats` CLI | ✅ |
| Snapshot-invalidated retrieval index cache | ✅ |
| Derived accumulated confidence (telemetry, not a gate) | ✅ |

**Pending (decided in the collaboration log, not yet implemented):** T4 — wiki as curated source and T3→note exporter (Phase D); MagnusAgent bridge via its `MemoryEngine` port (Phase C, lives in Magnus as an optional dependency); LLM-assisted extraction and promotion LLM-judge (Phase E); Learning Path by domains (Phase F); CI and right-to-be-forgotten (Phase G); the real Phase 7 pilot — the technical substrate is complete.

> Project rule: documentation never runs ahead of the code. If a row above says ✅, a test proves it; if it says pending, it does not exist yet.

---

## 📚 Technical Documentation

- 📖 [**00 - Vision and Architecture**](docs/00-VISION-Y-ARQUITECTURA.md): Epistemic design principles, anti-echo guarantees, and comparison with static wiki systems.
- ⚙️ [**01 - Tiered Memory Technical Core**](docs/01-MEMORIA-NIVELADA.md): Mathematical formulations for reinforcement, decay half-life, and promotion criteria.
- 🧩 [**02 - Modular Components**](docs/02-COMPONENTES-REUTILIZABLES.md): In-depth breakdown of RAG, providers, and storage layers.
- 🗺️ [**03 - Project Roadmap**](docs/03-ROADMAP.md): Development milestones and production validation criteria.
- 🤝 [**Collaboration Log**](COLABORACION.md): Architectural decisions log, invariant checkpoints, and design rationale.

---

## 💡 Positioning

> **"An LLM's confidence is never evidence."**  
> **"Contradictions create succession, not silent overwrites."**

EMS is not a chatbot memory feature. It is a **Memory Governance System for AI Agents**: a reusable layer between conversation, semantic retrieval, human-curated knowledge, and long-term learning.

---

<div align="center">
  <sub>Built for agents that learn from experience without mistaking repetition for truth.</sub>
</div>
