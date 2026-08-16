"""Fase A3 — fachada `EMS` y CLI: el bucle completo como lo usaría un
llamante real, con la cadena de custodia encendida ([D-08]).

El hallazgo de la auditoría era que el orquestador del bucle solo existía
dentro del test de integración. Estos tests fijan que la fachada lo
ejecuta de punta a punta sobre persistencia real.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ems import EMS, Embudo
from ems.cli import main
from memory.capture import Consent, Turn
from memory.claims import Tier
from memory.sqlite_store import SqliteClaimStore

_TS = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _consent() -> Consent:
    return Consent(True, "raw_conversation", "user-1", _TS)


def _turno(texto: str) -> Turn:
    return Turn("user", texto, _TS)


def test_el_bucle_completo_sobre_persistencia_real(tmp_path):
    db = tmp_path / "memoria.db"
    with EMS.open(db) as ems_inst:
        for i in range(3):
            record, resultados = ems_inst.register_conversation(
                [_turno("soy alergico a la penicilina")],
                agent_id="dr_soma", user_id="user-1", consent=_consent())
            assert record.id  # proveniencia T0 con id propio

        [t2] = ems_inst.claims(agent_id="dr_soma", tier=Tier.T2)
        assert t2.reinforcement_count == 3

        resultado = ems_inst.promote(t2.id)  # por id: lo que haría una UI
        assert resultado.approved

        ctx = ems_inst.recall("alergico a la penicilina", agent_id="dr_soma")
        assert ctx.t3 and not ctx.t2
        assert ctx.t3[0].confidence_label == "autoridad_plena"
        assert "confianza_media" not in ctx.as_prompt_block()

        stats = ems_inst.stats()
        assert stats["claims_activos"] == 1
        assert stats["por_tier"]["T3"] == 1
        assert stats["eventos"]["extraction"] == 1, "la 1ª conversación extrae"
        assert stats["eventos"]["reinforcement"] == 2, "las otras dos refuerzan"
        assert stats["eventos"]["promotion"] == 1
        assert stats["conversaciones_t0"] == 3
        assert stats["esquema"] == 2

    # "matar el proceso": una instancia nueva sobre la misma DB
    with EMS.open(db) as reabierto:
        [t3] = reabierto.claims(agent_id="dr_soma", tier=Tier.T3)
        assert t3.text == "soy alergico a la penicilina"
        assert reabierto.stats()["eventos"]["promotion"] == 1, \
            "la cadena de custodia sobrevive el reinicio"


def test_sin_consentimiento_no_se_escribe_nada(tmp_path):
    with EMS.open(tmp_path / "memoria.db") as ems_inst:
        with pytest.raises(PermissionError):  # ConsentRequired
            ems_inst.register_conversation(
                [_turno("soy alergico a la penicilina")],
                agent_id="dr_soma", user_id="user-1",
                consent=Consent(False, "raw_conversation", "user-1", _TS))
        assert ems_inst.claims() == []
        assert ems_inst.stats()["conversaciones_t0"] == 0


def test_la_cli_reporta_la_memoria(tmp_path, capsys):
    db = tmp_path / "memoria.db"
    with EMS.open(db) as ems_inst:
        for _ in range(3):
            ems_inst.register_conversation(
                [_turno("soy alergico a la penicilina")],
                agent_id="dr_soma", user_id="user-1", consent=_consent())

    assert main(["stats", str(db)]) == 0
    salida = capsys.readouterr().out
    assert "T2" in salida and "extraction" in salida
    assert "conversaciones T0: 3" in salida


def test_la_cli_sobre_una_memoria_vacia_no_falla(tmp_path, capsys):
    db = tmp_path / "nueva.db"
    assert main(["stats", str(db)]) == 0
    salida = capsys.readouterr().out
    assert "claims activos: 0" in salida


def test_la_fachada_funciona_con_store_en_ram_sin_custodia():
    """La fachada no exige SQLite: con RAM corre igual, degradando stats y
    metadatos de conversación sin romperse ([D-08]: fachada estable)."""
    from memory.store import InMemoryClaimStore

    ems_inst = EMS(claim_store=InMemoryClaimStore())
    _, [claim] = ems_inst.register_conversation(
        [_turno("me gusta el cafe negro")],
        agent_id="a1", user_id="user-1", consent=_consent())

    assert claim.tier == Tier.T1
    stats = ems_inst.stats()
    assert stats["eventos"] is None, "sin custodia no hay eventos — y no explota"


def test_retrocompatibilidad_alias_embudo(tmp_path):
    assert Embudo is EMS
