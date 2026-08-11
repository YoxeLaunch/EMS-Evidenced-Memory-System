"""`RAGPipeline` — fusión híbrida, umbral y política de citas."""
from __future__ import annotations

from rag.pipeline import (
    Provenance, RAGPipeline, RAGRequest, ScoredChunk,
)
from rag.vector_store import InMemoryVectorStore

_DOCS = [
    {"chunk_id": "c1", "namespace": "01-Finanzas", "source": "nota1.md",
     "heading": "Inflación", "hash": "h1",
     "text": "la inflación en República Dominicana subió este trimestre"},
    {"chunk_id": "c2", "namespace": "01-Finanzas", "source": "nota1.md",
     "heading": "Tasas", "hash": "h2",
     "text": "el banco central ajustó la tasa de política monetaria"},
]


class _LexicoFijo:
    """Retriever léxico simplificado: coincide por solape exacto de palabras."""

    def __init__(self, docs):
        self._docs = docs

    def retrieve(self, query, namespaces, k):
        qtoks = set(query.lower().split())
        out = []
        for d in self._docs:
            if namespaces and d["namespace"] not in namespaces:
                continue
            hits = len(qtoks & set(d["text"].lower().split()))
            if hits == 0:
                continue
            out.append(ScoredChunk(
                chunk_id=d["chunk_id"], text=d["text"], score=min(1.0, hits / 3),
                namespace=d["namespace"],
                provenance=Provenance(source=d["source"], hash=d["hash"])))
        out.sort(key=lambda c: c.score, reverse=True)
        return out[:k]


def _pipeline():
    vs = InMemoryVectorStore()
    vs.index(_DOCS)
    return RAGPipeline(vs, _LexicoFijo(_DOCS))


def test_el_pipeline_deduplica_entre_denso_y_lexico():
    pipeline = _pipeline()
    ctx = pipeline.build_context(RAGRequest(
        query="inflación república dominicana", namespaces=["01-Finanzas"],
        top_k=5, min_score=0.0, require_citations=True))
    ids = [c.chunk_id for c in ctx.chunks]
    assert len(ids) == len(set(ids))


def test_la_recuperacion_respeta_el_namespace():
    pipeline = _pipeline()
    ctx = pipeline.build_context(RAGRequest(
        query="inflación república dominicana", namespaces=["02-Sueno"],
        min_score=0.0))
    assert ctx.chunks == []


class _RetrieverVacio:
    def retrieve(self, query, namespaces, k):
        return []


class _RetrieverFijo:
    def __init__(self, chunks): self._chunks = chunks
    def retrieve(self, query, namespaces, k): return self._chunks[:k]


def test_sin_evidencia_y_con_citas_obligatorias_el_contexto_queda_vacio():
    pipeline = RAGPipeline(_RetrieverVacio(), _RetrieverVacio())
    ctx = pipeline.build_context(RAGRequest(
        query="lo que sea", namespaces=["01-Finanzas"], require_citations=True))
    assert ctx.chunks == []
    assert ctx.citations == []


def test_el_umbral_filtra_los_chunks_debiles():
    debil = ScoredChunk("c1", "texto irrelevante", 0.05, "01-Finanzas",
                        Provenance(source="nota.md"))
    fuerte = ScoredChunk("c2", "texto pertinente", 0.80, "01-Finanzas",
                         Provenance(source="nota.md"))
    pipeline = RAGPipeline(_RetrieverFijo([debil, fuerte]), _RetrieverVacio())
    ctx = pipeline.build_context(RAGRequest(
        query="q", namespaces=["01-Finanzas"], min_score=0.30))
    assert [c.chunk_id for c in ctx.chunks] == ["c2"]


def test_as_prompt_block_numera_y_cita():
    chunk = ScoredChunk("c1", "texto de evidencia", 0.9, "01-Finanzas",
                        Provenance(source="nota1.md"))
    pipeline = RAGPipeline(_RetrieverFijo([chunk]), _RetrieverVacio())
    ctx = pipeline.build_context(RAGRequest(query="q", namespaces=["01-Finanzas"], min_score=0.0))

    bloque = ctx.as_prompt_block()
    assert "[1] (nota1.md) texto de evidencia" == bloque
