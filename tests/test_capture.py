"""Captura de conversación cruda (T0) — criterio de hecho de la Fase 1
(`docs/03-ROADMAP.md`): una conversación se guarda con proveniencia completa
(quién, cuándo, con qué agente) y nada se guarda sin consentimiento
explícito.
"""
from __future__ import annotations

import os
import stat
from datetime import datetime, timezone

import pytest

from memory.capture import (
    Consent, ConsentRequired, ConversationRecord, JsonlConversationStore,
    Turn, record_conversation,
)


def _consent(*, granted: bool = True, scope: str = "raw_conversation") -> Consent:
    return Consent(granted=granted, scope=scope, granted_by="user-1",
                   granted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))


def _turns() -> list[Turn]:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return [Turn("user", "no como carne los martes", ts),
            Turn("assistant", "anotado", ts)]


# -- consentimiento -----------------------------------------------------------------
def test_sin_consentimiento_no_se_guarda_nada(tmp_path):
    store = JsonlConversationStore(tmp_path)

    with pytest.raises(ConsentRequired):
        record_conversation(store, agent_id="a1", user_id="user-1",
                            turns=_turns(), consent=_consent(granted=False))

    assert list(tmp_path.glob("conversations-*.jsonl")) == [], \
        "ConsentRequired debe lanzarse ANTES de escribir a disco"


def test_con_consentimiento_se_guarda_la_conversacion(tmp_path):
    store = JsonlConversationStore(tmp_path)

    record = record_conversation(store, agent_id="a1", user_id="user-1",
                                 turns=_turns(), consent=_consent())

    assert isinstance(record, ConversationRecord)
    [archivo] = list(tmp_path.glob("conversations-*.jsonl"))
    assert archivo.exists()


# -- proveniencia completa ------------------------------------------------------------
def test_el_registro_tiene_proveniencia_completa(tmp_path):
    store = JsonlConversationStore(tmp_path)

    record = record_conversation(store, agent_id="agente-x", user_id="user-1",
                                 turns=_turns(), consent=_consent())

    assert record.agent_id == "agente-x"           # con qué agente
    assert record.user_id == "user-1"                # quién
    assert record.started_at                          # cuándo
    assert record.id                                    # id opaco, no derivado del texto
    assert record.consent.granted is True
    assert record.consent.scope == "raw_conversation"


def test_el_texto_de_los_turnos_se_conserva_integro(tmp_path):
    store = JsonlConversationStore(tmp_path)
    turns = _turns()

    record = record_conversation(store, agent_id="a1", user_id="user-1",
                                 turns=turns, consent=_consent())

    assert [t.content for t in record.turns] == [t.content for t in turns]


# -- persistencia y relectura ---------------------------------------------------------
def test_read_all_recupera_lo_guardado_con_proveniencia_intacta(tmp_path):
    store = JsonlConversationStore(tmp_path)
    record_conversation(store, agent_id="a1", user_id="user-1",
                        turns=_turns(), consent=_consent())
    record_conversation(store, agent_id="a2", user_id="user-2",
                        turns=_turns(), consent=_consent())

    leidos = store.read_all()

    assert len(leidos) == 2
    assert {r.agent_id for r in leidos} == {"a1", "a2"}
    assert all(r.consent.granted for r in leidos)


def test_cada_conversacion_tiene_un_id_distinto(tmp_path):
    store = JsonlConversationStore(tmp_path)
    r1 = record_conversation(store, agent_id="a1", user_id="user-1",
                             turns=_turns(), consent=_consent())
    r2 = record_conversation(store, agent_id="a1", user_id="user-1",
                             turns=_turns(), consent=_consent())
    assert r1.id != r2.id


# -- egreso / almacenamiento local ------------------------------------------------------
@pytest.mark.skipif(os.name != "posix", reason="permisos 0600/0700 solo aplican en POSIX")
def test_archivo_y_directorio_quedan_con_permisos_restrictivos(tmp_path):
    store = JsonlConversationStore(tmp_path)
    record_conversation(store, agent_id="a1", user_id="user-1",
                        turns=_turns(), consent=_consent())

    [archivo] = list(tmp_path.glob("conversations-*.jsonl"))
    assert stat.S_IMODE(tmp_path.stat().st_mode) == stat.S_IRWXU
    assert stat.S_IMODE(archivo.stat().st_mode) == (stat.S_IRUSR | stat.S_IWUSR)


def test_rotacion_purga_los_archivos_mas_antiguos_bajo_limite(tmp_path):
    store = JsonlConversationStore(tmp_path, max_total_mb=0.001)
    viejo = tmp_path / "conversations-2020-01-01.jsonl"
    viejo.write_text("x" * 2000, encoding="utf-8")

    record_conversation(store, agent_id="a1", user_id="user-1",
                        turns=_turns(), consent=_consent())

    assert not viejo.exists(), "el archivo más antiguo debe purgarse al exceder el límite"
    assert list(tmp_path.glob("conversations-*.jsonl")), "el archivo del día actual nunca se purga"
