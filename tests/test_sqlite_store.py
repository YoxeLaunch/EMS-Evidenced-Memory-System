"""Fase A1 — `SqliteClaimStore`: persistencia, cadena de custodia y
contrato de concurrencia ([D-06], [D-07], [ALT-02]).

El criterio de hecho de la fase (`docs/04-PLAN-MEJORAS.md`): matar el
proceso, reabrir, y los claims persisten con su historial completo; una
promoción ejecutada en una sesión anterior es trazable evento a evento.
"""
from __future__ import annotations

import sqlite3

import pytest

from memory.claims import MemoryClaim, Tier
from memory.sqlite_store import (
    SCHEMA_VERSION, SqliteClaimStore, StoreLockedError, StoreVersionError,
)


def _claim(source: str = "conv-1") -> MemoryClaim:
    return MemoryClaim.new_candidate(
        agent_id="a1", subject="cafe", text="me gusta el cafe negro",
        source_conversation_id=source, confidence=0.5)


# -- persistencia y cadena de custodia ------------------------------------------------
def test_reinicio_preserva_claims_eventos_y_fuentes(tmp_path):
    db = tmp_path / "embudo.db"
    store = SqliteClaimStore(db)
    store.record_conversation_source(
        "conv-1", agent_id="a1", user_id="user-1",
        started_at="2026-08-16T10:00:00+00:00", sha256="ab12")
    claim = _claim()
    store.add(claim, event_type="extraction", conversation_id="conv-1",
              event_payload={"subject": "cafe"})
    claim.reinforcement_count = 3
    claim.source_conversation_ids.append("conv-2")
    store.add(claim, event_type="reinforcement", conversation_id="conv-2")
    claim.tier = Tier.T2
    store.add(claim, event_type="promotion", event_payload={"evaluador": "structural"})
    store.close()

    # "matar el proceso": una instancia nueva sobre el mismo archivo
    reopened = SqliteClaimStore(db)
    leido = reopened.get(claim.id)
    assert leido.tier == Tier.T2
    assert leido.reinforcement_count == 3
    assert leido.source_conversation_ids == ["conv-1", "conv-2"]

    # la cadena de custodia reconstruye T0 → extracción → refuerzo → promoción
    [evento for evento in reopened.events(claim_id=claim.id)]
    assert [e.tipo for e in reopened.events(claim_id=claim.id)] == [
        "extraction", "reinforcement", "promotion"]
    assert reopened.events(claim_id=claim.id)[0].conversation_id == "conv-1"

    fuente = reopened.conversation_source("conv-1")
    assert fuente is not None and fuente.sha256 == "ab12" and fuente.user_id == "user-1"
    reopened.close()


def test_los_eventos_no_se_borran_ni_reescriben(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")
    claim = _claim()
    store.add(claim, event_type="extraction")
    store.add(claim, event_type="extraction")  # re-add del mismo claim

    seqs = [e.seq for e in store.events()]
    assert len(seqs) == 2 and len(set(seqs)) == 2, "append-only: dos escrituras, dos eventos"


# -- atomicidad [D-07] -----------------------------------------------------------------
def test_claim_y_evento_se_escriben_juntos_o_no_se_escribe_nada(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")
    claim = _claim()

    # un payload no serializable revienta ANTES de tocar disco
    with pytest.raises(TypeError):
        store.add(claim, event_type="extraction", event_payload={"no": {1, 2}})

    assert store.get(claim.id) is None, "atomicidad: sin evento válido no hay claim"
    assert store.events() == []


def test_tipo_de_evento_invalido_se_rechaza(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")
    with pytest.raises(ValueError, match="promocion"):
        store.add(_claim(), event_type="promocion")  # sin tilde: typo que
        # rompería la cadena de custodia en silencio si pasara
    assert store.events() == []


# -- single-writer [D-06] ----------------------------------------------------------------
def test_un_segundo_writer_falla_con_error_claro_no_colgandose(tmp_path):
    db = tmp_path / "embudo.db"
    store = SqliteClaimStore(db, busy_timeout_ms=0)

    otro = sqlite3.connect(str(db), isolation_level=None)
    otro.execute("BEGIN IMMEDIATE")  # otro proceso toma el lock de escritura

    try:
        with pytest.raises(StoreLockedError, match="single-writer"):
            store.add(_claim())
    finally:
        otro.rollback()
        otro.close()

    # liberado el lock, el mismo store funciona sin reabrir
    store.add(_claim())
    assert store.get(_claim().id) is not None
    store.close()


# -- esquema versionado y migraciones ------------------------------------------------
def test_db_recien_creada_queda_en_la_version_actual(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")
    assert store.schema_version == SCHEMA_VERSION
    store.close()


def test_una_db_del_futuro_se_rechaza_en_vez_de_corromperse(tmp_path):
    db = tmp_path / "embudo.db"
    store = SqliteClaimStore(db)
    store.close()

    conn = sqlite3.connect(str(db))
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()

    with pytest.raises(StoreVersionError, match="esquema"):
        SqliteClaimStore(db)


def test_migracion_desde_version_anterior(tmp_path):
    """Simula una DB v0 (esquema actual pero user_version=0, como una DB
    pre-versionado): al abrirla migra dentro de transacciones y queda
    operativa."""
    db = tmp_path / "embudo.db"
    store = SqliteClaimStore(db)
    store.add(_claim(), event_type="extraction")
    store.close()

    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA user_version = 0")
    conn.close()

    reopened = SqliteClaimStore(db)
    assert reopened.schema_version == SCHEMA_VERSION
    assert reopened.get(_claim().id) is not None, "migrar no pierde datos"
    assert len(reopened.events()) == 1
    reopened.close()


# -- detalles del contrato ----------------------------------------------------------------
def test_los_timestamps_de_eventos_son_utc(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")
    store.add(_claim(), event_type="extraction")
    ts = store.events()[0].ts
    assert ts.endswith("+00:00"), f"UTC explícito, no hora local: {ts}"
    store.close()


def test_events_filtra_por_tipo_y_claim(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")
    a = _claim("conv-1")
    b = MemoryClaim.new_candidate(
        agent_id="a1", subject="te", text="me gusta el te",
        source_conversation_id="conv-1", confidence=0.5)
    store.add(a, event_type="extraction")
    store.add(b, event_type="extraction")
    store.append_event("expiration", claim_id=b.id)

    assert [e.tipo for e in store.events(claim_id=a.id)] == ["extraction"]
    assert len(store.events(tipo="extraction")) == 2
    assert len(store.events(tipo="expiration")) == 1
    store.close()


def test_conversation_source_es_idempotente_y_completa_el_hash_despues(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")
    store.record_conversation_source(
        "conv-1", agent_id="a1", user_id="user-1", started_at="2026-08-16T10:00:00+00:00")
    store.record_conversation_source(
        "conv-1", agent_id="a1", user_id="user-1",
        started_at="2026-08-16T10:00:00+00:00", sha256="cd34")

    fuentes = store.conversation_sources()
    assert len(fuentes) == 1
    assert fuentes[0].sha256 == "cd34", "re-registrar completa el hash, no duplica"
    assert store.conversation_source("conv-x") is None
    store.close()
