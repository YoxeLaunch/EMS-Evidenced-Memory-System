"""`HashingEmbedder` — random indexing con pesos TF-IDF."""
from __future__ import annotations

from rag.embedder import HashingEmbedder, coseno


def test_produce_vectores_densos_normalizados():
    emb = HashingEmbedder(dim=64).fit(["la inflación subió", "dormir bien importa"])
    [v] = emb.embed(["la inflación subió"])

    assert len(v) == 64
    assert abs(sum(x * x for x in v) - 1.0) < 1e-9, "debe estar normalizado a norma 1"


def test_es_determinista():
    a = HashingEmbedder(dim=64).fit(["texto de corpus"]).embed(["consulta"])
    b = HashingEmbedder(dim=64).fit(["texto de corpus"]).embed(["consulta"])
    assert a == b


def test_un_texto_se_parece_mas_a_si_mismo_que_a_otro():
    corpus = ["la inflación y las tasas del banco central",
              "higiene del sueño y horarios para dormir"]
    emb = HashingEmbedder(dim=128).fit(corpus)
    v_inf, v_sueno = emb.embed(corpus)
    [q] = emb.embed(["qué pasa con la inflación"])

    assert coseno(q, v_inf) > coseno(q, v_sueno)


def test_los_prefijos_acercan_variantes_morfologicas():
    """En español esto importa: 'inflación' / 'inflacionario'."""
    corpus = ["proceso inflacionario sostenido en el tiempo",
              "rutina de ejercicio y descanso semanal"]
    emb = HashingEmbedder(dim=128).fit(corpus)
    v_inflacion, v_ejercicio = emb.embed(corpus)
    [q] = emb.embed(["inflación"])

    assert coseno(q, v_inflacion) > coseno(q, v_ejercicio)


def test_el_idf_baja_el_peso_de_lo_que_esta_en_todas_partes():
    comun = ["banco importante uno", "banco importante dos", "banco importante tres"]
    emb = HashingEmbedder(dim=128).fit(comun + ["glinfatico sistema cerebral"])

    assert emb._idf["banco"] < emb._idf["glinfatico"]


def test_una_consulta_vacia_no_recupera_nada():
    from rag.vector_store import InMemoryVectorStore

    vs = InMemoryVectorStore()
    vs.index([{"chunk_id": "c1", "text": "algo de contenido", "namespace": "ns"}])

    assert vs.retrieve("de la y el", [], 5) == []
