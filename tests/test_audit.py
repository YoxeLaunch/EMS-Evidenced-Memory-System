"""`TraceStore` — auditoría opt-in, JSONL en append, sin contenido sensible."""
from __future__ import annotations

import json
import os
import stat

import pytest

from orchestration.audit import (
    JsonlTraceStore, NullTraceStore, build_entry, trace_store_from_env,
)


def test_null_trace_store_no_escribe_nada(tmp_path):
    store = NullTraceStore()
    store.record({"evento": "extraction"})
    assert list(tmp_path.iterdir()) == []


def test_jsonl_trace_store_escribe_una_linea_por_entrada(tmp_path):
    store = JsonlTraceStore(tmp_path)
    store.record(build_entry(agent_id="a1", event="extraction", details={"claim_id": "x"}))
    store.record(build_entry(agent_id="a1", event="reinforcement", details={"claim_id": "x"}))

    [archivo] = list(tmp_path.glob("ems-*.jsonl"))
    lineas = archivo.read_text(encoding="utf-8").strip().splitlines()
    assert len(lineas) == 2
    assert json.loads(lineas[0])["event"] == "extraction"
    assert json.loads(lineas[1])["event"] == "reinforcement"


def test_build_entry_no_incluye_texto_de_conversacion(tmp_path):
    entry = build_entry(agent_id="a1", event="promotion", details={"claim_id": "x", "source_conversation_ids": ["conv-1"]})
    assert entry["details"]["source_conversation_ids"] == ["conv-1"]
    assert "text" not in entry
    assert set(entry) == {"timestamp", "agent_id", "event", "details"}


@pytest.mark.skipif(os.name != "posix", reason="permisos 0600/0700 solo aplican en POSIX")
def test_archivo_y_directorio_quedan_con_permisos_restrictivos(tmp_path):
    store = JsonlTraceStore(tmp_path)
    store.record({"event": "extraction"})

    [archivo] = list(tmp_path.glob("ems-*.jsonl"))
    assert stat.S_IMODE(tmp_path.stat().st_mode) == stat.S_IRWXU
    assert stat.S_IMODE(archivo.stat().st_mode) == (stat.S_IRUSR | stat.S_IWUSR)


def test_rotacion_purga_los_archivos_mas_antiguos_bajo_limite(tmp_path):
    store = JsonlTraceStore(tmp_path, max_total_mb=0.001)  # ~1 KB, fuerza purga rápido
    viejo = tmp_path / "ems-2020-01-01.jsonl"
    viejo.write_text("x" * 2000, encoding="utf-8")

    store.record({"event": "extraction"})

    assert not viejo.exists(), "el archivo más antiguo debe purgarse al exceder el límite"
    assert list(tmp_path.glob("ems-*.jsonl")), "el archivo del día actual nunca se purga"


def test_trace_store_from_env_sin_variable_es_null(monkeypatch):
    monkeypatch.delenv("EMS_TRACE_DIR", raising=False)
    monkeypatch.delenv("EMBUDO_TRACE_DIR", raising=False)
    assert isinstance(trace_store_from_env(), NullTraceStore)


def test_trace_store_from_env_con_variable_usa_jsonl(monkeypatch, tmp_path):
    monkeypatch.setenv("EMS_TRACE_DIR", str(tmp_path / "traces"))
    store = trace_store_from_env()
    assert isinstance(store, JsonlTraceStore)
