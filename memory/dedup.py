"""Deduplicación de candidatos contra claims existentes — Fase 2 del roadmap.

Usa `rag.embedder.HashingEmbedder` (portado de MagnusAgent) para detectar que
un candidato nuevo ya se dijo antes, sin comparar texto libre. Sigue el
criterio de `docs/01-MEMORIA-NIVELADA.md`: el match exige **mismo subject Y
embedding similar** — mismo subject solo no basta (dos afirmaciones
distintas pueden compartir tema) y embedding similar solo no basta (el
`HashingEmbedder` no distingue sinónimos sin forma compartida, así que dos
temas distintos con palabras parecidas podrían acercarse por ruido).
"""
from __future__ import annotations

from rag.embedder import HashingEmbedder, coseno
from memory.claims import MemoryClaim
from memory.store import InMemoryClaimStore

#: Umbral de similitud coseno para considerar dos textos "el mismo
#: candidato". Con el embedder por defecto (random indexing + TF-IDF, sin
#: sinónimos) un umbral alto evita falsos positivos: dos afirmaciones sobre
#: el mismo subject que comparten poco vocabulario no deben fusionarse.
DEFAULT_THRESHOLD = 0.55


def find_match(
    candidate: MemoryClaim, store: InMemoryClaimStore, *,
    embedder: HashingEmbedder | None = None, threshold: float = DEFAULT_THRESHOLD,
) -> MemoryClaim | None:
    """El claim activo existente que el candidato refuerza, o `None` si es nuevo.

    El embedder se ajusta (`fit`) sobre el corpus de candidatos comparados en
    cada llamada — es barato porque el conjunto de claims por subject suele
    ser pequeño, y evita depender de un `fit` global compartido entre
    llamadas que Fase 2 no necesita todavía.
    """
    mismos_subject = store.by_subject(candidate.agent_id, candidate.subject)
    if not mismos_subject:
        return None
    if candidate.id in {c.id for c in mismos_subject}:
        # ya está literalmente el mismo claim (mismo hash) — no es un "match",
        # es el mismo candidato re-extraído.
        return next(c for c in mismos_subject if c.id == candidate.id)

    emb = embedder or HashingEmbedder()
    corpus = [c.text for c in mismos_subject] + [candidate.text]
    emb.fit(corpus)
    vectores = emb.embed(corpus)
    v_candidato = vectores[-1]

    mejor: tuple[MemoryClaim, float] | None = None
    for claim, vector in zip(mismos_subject, vectores[:-1]):
        score = coseno(v_candidato, vector)
        if score >= threshold and (mejor is None or score > mejor[1]):
            mejor = (claim, score)

    return mejor[0] if mejor is not None else None
