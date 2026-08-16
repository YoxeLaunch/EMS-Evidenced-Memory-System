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
    T4["<b>T4: Human Curated</b><br/>Hand-curated knowledge<br/><i>Highest operational precedence</i>"] -.->|Benchmark & Anchor| T3

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
| **T2** | **Reinforced Evidence** | Candidate validated across multiple distinct sessions. | ⚠️ **With Uncertainty** | Injected with explicit uncertainty tags (`[EVIDENCIA T2]`). |
| **T3** | **Promoted Knowledge** | Passed strict multi-session promotion evaluator or human approval. | ✅ **Yes** | Injected with full authority and origin hash. |
| **T4** | **Human Curated Source** | Verified enterprise documentation or human-edited truth. | ✅ **Highest Authority** | Always takes precedence in case of conflict. |

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

    Note over User, DB: Phase 1: Original Fact
    User->>EMS: "I live in Berlin"
    EMS->>DB: Save Claim #101 (Subject: residence, Value: Berlin, Tier: T2, Status: active)

    Note over User, DB: Phase 2: Subsequent Contradiction
    User->>EMS: "I moved to Tokyo last week"
    EMS->>EMS: Detect contradiction on subject 'residence'
    EMS->>DB: Create Claim #205 (Subject: residence, Value: Tokyo, Tier: T2, supersedes: #101)
    EMS->>DB: Update Claim #101 (Status: superseded, superseded_by: #205)

    Note over User, DB: Phase 3: Retrieval
    User->>EMS: Recall "Where do I live?"
    EMS->>DB: Query active claims only
    DB-->>EMS: Returns Claim #205 (Tokyo) [#101 excluded from active recall]
    EMS-->>User: "You live in Tokyo (superseded past residence in Berlin)"
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
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 2. Register conversation turn with explicit user consent
    consent = Consent(
        granted=True,
        scope="profile_and_preferences",
        user_id="user_123",
        timestamp=now_iso
    )
    
    record, claims = memory.register_conversation(
        turns=[
            Turn(speaker="user", text="I am severely allergic to penicillin.", timestamp=now_iso)
        ],
        agent_id="medical_agent",
        user_id="user_123",
        consent=consent
    )
    
    print(f"Captured record ID: {record.id}")
    for c in claims:
        print(f"Claim [{c.tier.value}]: {c.subject} -> {c.text}")

    # 3. Retrieve tiered context for LLM prompt
    context = memory.recall("penicillin allergy", agent_id="medical_agent")
    
    # Inject into prompt
    print("\n--- Tiered Prompt Block ---")
    print(context.as_prompt_block())
```

### CLI Inspection

```bash
# View memory database statistics and custody metrics
embudo stats memory.db
```

Output:
```text
Embudo v0.2.0 — memory.db
esquema: v2
claims activos: 14 (T1: 4, T2: 8, T3: 2)
estados: active: 14, superseded: 3, expired: 1
eventos de custodia: created: 18, reinforced: 9, superseded: 3, promoted: 2
conversaciones T0: 12
construcciones de índice: 4
```

---

## 🧱 Data Model (`MemoryClaim`)

```python
@dataclass(frozen=True)
class MemoryClaim:
    id: str                        # Deterministic hash of (agent_id, subject, normalized_text)
    agent_id: str                  # Isolated namespace / agent identifier
    subject: str                   # Normalized topic or entity (for indexing and deduplication)
    text: str                      # Stored claim in normalized canonical form
    tier: Tier                     # T0 | T1 | T2 | T3
    confidence: float              # Tier-specific internal score (0.0 to 1.0)
    source_conversation_ids: list  # Full provenance tracking back to T0 logs
    first_seen_at: str             # ISO timestamp of first capture
    last_reinforced_at: str        # ISO timestamp of latest reinforcement
    reinforcement_count: int       # Number of independent session confirmations
    supersedes: str | None         # ID of past claim invalidated by this one
    superseded_by: str | None      # ID of successor claim if invalidated
    decay_half_life_days: int      # Half-life duration before confidence decay
    status: ClaimStatus            # active | superseded | expired | rejected
```

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
