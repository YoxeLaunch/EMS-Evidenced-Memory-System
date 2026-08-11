"""`InMemoryVectorStore` — contrato `DenseRetriever` sobre documentos genéricos."""
from __future__ import annotations

from rag.vector_store import InMemoryVectorStore

_DOCS = [
    {"chunk_id": "c1", "namespace": "01-Finanzas", "source": "nota1.md",
     "heading": "Inflación", "hash": "h1",
     "text": "la inflación en República Dominicana subió este trimestre"},
    {"chunk_id": "c2", "namespace": "01-Finanzas", "source": "nota1.md",
     "heading": "Tasas", "hash": "h2",
     "text": "el banco central ajustó la tasa de política monetaria"},
    {"chunk_id": "c3", "namespace": "02-Sueno", "source": "nota2.md",
     "heading": "Higiene del sueño", "hash": "h3",
     "text": "dormir bien mejora la memoria y el ánimo"},
]


def _store() -> InMemoryVectorStore:
    vs = InMemoryVectorStore()
    vs.index(_DOCS, knowledge_version="test-v1")
    return vs


def test_indexa_todos_los_documentos():
    vs = _store()
    assert len(vs) == 3


def test_respeta_el_namespace_del_llamante():
    vs = _store()

    dentro = vs.retrieve("inflación República Dominicana", ["01-Finanzas"], 5)
    assert dentro and all(c.namespace == "01-Finanzas" for c in dentro)

    fuera = vs.retrieve("inflación República Dominicana", ["02-Sueno"], 5)
    assert all(c.namespace == "02-Sueno" for c in fuera), "la parcela es un límite duro"
    assert not any("nota1" in c.provenance.source for c in fuera)


def test_sin_namespaces_no_filtra():
    vs = _store()
    resultados = vs.retrieve("inflación", [], 5)
    assert resultados  # sin restricción, puede devolver de cualquier namespace


def test_arrastra_hash_y_knowledge_version():
    vs = _store()
    c = vs.retrieve("inflación República Dominicana", ["01-Finanzas"], 1)[0]
    assert c.provenance.hash == "h1"
    assert c.provenance.knowledge_version == "test-v1"


def test_un_store_vacio_no_recupera_nada():
    vs = InMemoryVectorStore()
    assert vs.retrieve("cualquier cosa", [], 5) == []
