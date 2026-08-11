"""Recuperación integrada — Fase 5 del roadmap.

`RAGPipeline` (vendorizado en `rag/pipeline.py`) consumiendo `MemoryClaim`
T2/T3 activos como documentos indexables — `docs/01-MEMORIA-NIVELADA.md`:
"los `MemoryClaim` de T2/T3 activos son, funcionalmente, el mismo tipo de
documento indexable que un chunk de wiki." La diferencia real está en el
evaluador que consume el resultado: debe aplicar el umbral de confianza
propio de cada nivel y la respuesta debe distinguir T2 (confianza media) de
T3 (autoridad plena) — nunca presentarlos con la misma seguridad.
"""
from __future__ import annotations

from dataclasses import dataclass

from memory.claims import MemoryClaim, Tier, normalize_text
from memory.store import InMemoryClaimStore
from rag.embedder import HashingEmbedder
from rag.pipeline import Provenance, RAGPipeline, RAGRequest, ScoredChunk
from rag.vector_store import InMemoryVectorStore

#: T2 es "confianza media": sin la autoridad de una fuente verificada, así
#: que se exige un score de recuperación más alto para aceptarlo como
#: evidencia relevante — compensa la menor autoridad epistémica con más
#: certeza de que sí es lo que se está buscando. T3 ya pasó el evaluador de
#: promoción (`memory/promotion.py`), así que un match algo más débil sigue
#: siendo evidencia aceptable.
DEFAULT_T2_MIN_SCORE = 0.45
DEFAULT_T3_MIN_SCORE = 0.30

CONFIDENCE_LABELS = {Tier.T2: "confianza_media", Tier.T3: "autoridad_plena"}


def _claim_to_document(claim: MemoryClaim) -> dict:
    return {"chunk_id": claim.id, "namespace": claim.agent_id, "text": claim.text,
            "source": f"claim:{claim.id}", "heading": claim.subject, "hash": claim.id}


class ClaimLexicalRetriever:
    """Retriever léxico sobre `MemoryClaim.text`: solape de tokens
    normalizados. Determinista y sin dependencias — mismo espíritu que el
    store léxico de Magnus, adaptado a claims en vez de chunks de wiki.
    """

    def __init__(self, documents: list[dict]):
        self._docs = documents

    def retrieve(self, query: str, namespaces: list[str], k: int) -> list[ScoredChunk]:
        qtoks = set(normalize_text(query).split())
        out = []
        for d in self._docs:
            if namespaces and d["namespace"] not in namespaces:
                continue
            dtoks = set(normalize_text(d["text"]).split())
            hits = len(qtoks & dtoks)
            if hits == 0:
                continue
            score = min(1.0, hits / max(1, len(dtoks)) ** 0.5)
            out.append(ScoredChunk(
                chunk_id=d["chunk_id"], text=d["text"], score=round(score, 3),
                namespace=d["namespace"],
                provenance=Provenance(source=d["source"], hash=d["hash"])))
        out.sort(key=lambda c: c.score, reverse=True)
        return out[:k]


@dataclass(frozen=True)
class TieredEvidence:
    chunk: ScoredChunk
    tier: Tier

    @property
    def confidence_label(self) -> str:
        return CONFIDENCE_LABELS[self.tier]


@dataclass(frozen=True)
class TieredRAGContext:
    """Contexto de recuperación que distingue explícitamente T2 de T3 — el
    evaluador de respuesta nunca debe tratarlos con la misma seguridad."""
    query: str
    evidence: list[TieredEvidence]

    @property
    def t2(self) -> list[TieredEvidence]:
        return [e for e in self.evidence if e.tier == Tier.T2]

    @property
    def t3(self) -> list[TieredEvidence]:
        return [e for e in self.evidence if e.tier == Tier.T3]

    def as_prompt_block(self) -> str:
        """Evidencia numerada, con la etiqueta de nivel visible en cada
        línea — nunca un T2 citado como si fuera T3."""
        partes = [f"[{i}] ({e.confidence_label}, {e.chunk.provenance.source}) {e.chunk.text}"
                  for i, e in enumerate(self.evidence, 1)]
        return "\n\n".join(partes)


def build_tiered_context(
    store: InMemoryClaimStore, query: str, agent_id: str, *, top_k: int = 8,
    t2_min_score: float = DEFAULT_T2_MIN_SCORE, t3_min_score: float = DEFAULT_T3_MIN_SCORE,
    embedder: HashingEmbedder | None = None,
) -> TieredRAGContext:
    """Recupera evidencia de los claims T2/T3 activos de `agent_id`,
    aplicando el umbral propio de cada nivel.

    El índice es compartido entre T2 y T3 (misma parcela de conocimiento),
    pero se consulta dos veces — una por umbral — y cada pasada descarta lo
    que no sea de su propio nivel. Es el precio de aplicar un umbral
    distinto por tier con la misma `RAGPipeline` sin bifurcar su contrato.
    """
    claims_t2 = store.active(agent_id=agent_id, tier=Tier.T2)
    claims_t3 = store.active(agent_id=agent_id, tier=Tier.T3)
    por_id = {c.id: c for c in claims_t2 + claims_t3}

    if not por_id:
        return TieredRAGContext(query, [])

    documentos = [_claim_to_document(c) for c in claims_t2 + claims_t3]
    dense = InMemoryVectorStore(embedder or HashingEmbedder())
    dense.index(documentos)
    lexical = ClaimLexicalRetriever(documentos)
    pipeline = RAGPipeline(dense, lexical)

    evidencia: list[TieredEvidence] = []
    for tier, umbral in ((Tier.T2, t2_min_score), (Tier.T3, t3_min_score)):
        ctx = pipeline.build_context(RAGRequest(
            query=query, namespaces=[agent_id], top_k=top_k, min_score=umbral,
            require_citations=False))
        for chunk in ctx.chunks:
            claim = por_id.get(chunk.chunk_id)
            if claim is not None and claim.tier == tier:
                evidencia.append(TieredEvidence(chunk, tier))

    return TieredRAGContext(query, evidencia)
