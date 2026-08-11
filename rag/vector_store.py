"""Vector store en memoria que implementa `DenseRetriever`.

Portado de MagnusAgent (`kernel/rag/vector_store.py`) — ver
`docs/02-COMPONENTES-REUTILIZABLES.md`. Adaptado para indexar documentos
genéricos en vez de chunks de una wiki en disco: Magnus construye este store
desde `FileWikiStore` (`from_wiki_store`), pero ese store asume una wiki
versionada por carpetas y `docs/02-COMPONENTES-REUTILIZABLES.md` señala
explícitamente que NO se porta ("el modelo de `MemoryClaim` reemplaza esa
función"). Aquí se indexa directamente una lista de documentos — hoy dicts
genéricos, más adelante `MemoryClaim` T2/T3 (fase de memoria nivelada).

Con el embedder por defecto ([`HashingEmbedder`](embedder.py)) los vectores
son **random indexing con pesos TF-IDF, no embeddings neuronales**: el store
es agnóstico y funcionaría igual con un embedder neuronal, pero hoy no hay
ninguno en el repositorio y conviene no dar a entender lo contrario.

Filtra por namespace ANTES de puntuar — la parcela de conocimiento es un
límite duro, no un criterio de ordenación.
"""
from __future__ import annotations

from rag.embedder import HashingEmbedder, coseno
from rag.pipeline import Provenance, ScoredChunk


def _ns_match(doc_ns: str, wanted: str) -> bool:
    """El documento pertenece a `wanted` si su namespace es ese exacto o está
    anidado bajo él — contención de un solo sentido, igual que `_coincide` en
    `orchestration/permissions.py`.
    """
    ns = doc_ns.rstrip("/")
    w = wanted.rstrip("/")
    return ns == w or ns.startswith(w + "/")


class InMemoryVectorStore:
    """Espera documentos con las claves: `chunk_id`, `text`, `namespace`,
    `source`, `heading`, `hash` (los dos últimos solo para provenance)."""

    def __init__(self, embedder: HashingEmbedder | None = None):
        self.embedder = embedder or HashingEmbedder()
        self._docs: list[dict] = []
        self._vectores: list[list[float]] = []
        self._knowledge_version: str = "desconocida"

    # -- construcción --------------------------------------------------------
    def index(self, documents: list[dict], *, knowledge_version: str = "desconocida") -> dict:
        """Indexa los documentos ya troceados por el llamante."""
        self._docs = list(documents)
        self._knowledge_version = knowledge_version
        textos = [f"{d.get('heading', '')} {d['text']}" for d in self._docs]
        if not self.embedder.ajustado:
            self.embedder.fit(textos)
        self._vectores = self.embedder.embed(textos)
        return {"chunks": len(self._docs), "dim": self.embedder.dim,
                "embedder": self.embedder.name}

    # -- contrato DenseRetriever ---------------------------------------------
    def retrieve(self, query: str, namespaces: list[str], k: int) -> list[ScoredChunk]:
        if not self._docs:
            return []
        q = self.embedder.embed([query])[0]
        if not any(q):
            return []

        out: list[ScoredChunk] = []
        for doc, vec in zip(self._docs, self._vectores):
            if namespaces and not any(_ns_match(doc["namespace"], ns) for ns in namespaces):
                continue
            score = coseno(q, vec)
            if score <= 0.0:
                continue
            fuente = doc.get("source", doc["chunk_id"])
            heading = doc.get("heading")
            out.append(ScoredChunk(
                chunk_id=doc["chunk_id"], text=doc["text"], score=round(score, 3),
                namespace=doc["namespace"],
                provenance=Provenance(
                    source=f"{fuente} · «{heading}»" if heading else fuente,
                    hash=doc.get("hash"),
                    knowledge_version=self._knowledge_version)))
        out.sort(key=lambda c: c.score, reverse=True)
        return out[:k]

    def __len__(self) -> int:
        return len(self._docs)
