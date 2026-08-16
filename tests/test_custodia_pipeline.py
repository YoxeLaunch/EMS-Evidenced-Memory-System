"""T-06 / A4 — el pipeline emite su cadena de custodia SOLO.

Requisito del humano (2026-08-16): probar el flujo real sin que el llamante
pase `event_type` manualmente, para extracción, refuerzo, sucesión,
promoción y expiración — y con payload canónico suficiente para reconstruir
cada transición (estado/tier/contador/procedencia/sucesión/motivo).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from memory.capture import Consent, ConversationRecord, Turn
from memory.claims import Tier
from memory.decay import expire_stale_claims
from memory.extraction import extract_candidates
from memory.promotion import promote_to_t3
from memory.reinforcement import reinforce_or_create
from memory.sqlite_store import SqliteClaimStore

_TS = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conversacion(texto: str, *, conv_id: str) -> ConversationRecord:
    return ConversationRecord(
        id=conv_id, agent_id="a1", user_id="user-1", started_at=_TS,
        turns=(Turn("user", texto, _TS),),
        consent=Consent(True, "raw_conversation", "user-1", _TS))


def _procesar(store, texto: str, *, conv_id: str):
    """El bucle que usaría un llamante real: extraer y reforzar. Nada de
    eventos manuales — si aparecen, los emitió el pipeline."""
    record = _conversacion(texto, conv_id=conv_id)
    store.record_conversation_source(
        conv_id, agent_id="a1", user_id="user-1", started_at=_TS)
    resultado = None
    for candidato in extract_candidates(record):
        resultado = reinforce_or_create(candidato, store)
    return resultado


def test_ciclo_de_vida_completo_emite_su_cadena_sin_intervencion(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")

    for i in range(1, 4):
        resultado = _procesar(store, "soy alergico a la penicilina", conv_id=f"conv-{i}")

    eventos = store.events(claim_id=resultado.id)
    assert [e.tipo for e in eventos] == ["extraction", "reinforcement", "reinforcement"]

    # payload canónico: la transición se reconstruye sin ejecutarla
    ext, ref1, ref2 = eventos
    assert ext.payload["estado_anterior"] is None, "extracción = creación"
    assert ext.payload["tier_nuevo"] == "T1"
    assert ext.payload["conversacion_disparadora"] == "conv-1"
    assert ref1.payload["contador_anterior"] == 1 and ref1.payload["contador_nuevo"] == 2
    assert ref2.payload["contador_nuevo"] == 3
    assert ref2.payload["tier_anterior"] == "T1" and ref2.payload["tier_nuevo"] == "T2", \
        "el ascenso a T2 queda documentado en el refuerzo que lo cruza"
    assert ref2.payload["conversaciones_origen"] == ["conv-1", "conv-2", "conv-3"]

    # promoción — también automática
    promocion = promote_to_t3(resultado, store)
    assert promocion.approved
    [evento_promocion] = store.events(claim_id=resultado.id, tipo="promotion")
    assert evento_promocion.payload["tier_anterior"] == "T2"
    assert evento_promocion.payload["tier_nuevo"] == "T3"
    assert "penicilina" not in str(evento_promocion.payload), "custodia sin contenido del claim"
    assert evento_promocion.payload["evaluador"] == "StructuralPromotionEvaluator"
    assert evento_promocion.payload["motivo"]

    # expiración — confidence decae con el tiempo
    claim = store.get(resultado.id)
    claim.last_reinforced_at = (datetime.now(timezone.utc)
                                - timedelta(days=claim.decay_half_life_days * 10)
                                ).isoformat(timespec="seconds")
    store.add(claim)  # setup del test: envejecer sin evento
    [expirado] = expire_stale_claims(store)

    [evento_expiracion] = store.events(claim_id=resultado.id, tipo="expiration")
    assert evento_expiracion.payload["estado_anterior"] == "active"
    assert evento_expiracion.payload["estado_nuevo"] == "expired"
    assert evento_expiracion.payload["confianza_efectiva"] < evento_expiracion.payload["umbral"]

    # la cadena completa del claim, en orden, explica cada transición
    assert [e.tipo for e in store.events(claim_id=resultado.id)] == [
        "extraction", "reinforcement", "reinforcement", "promotion", "expiration"]
    store.close()


def test_sucesion_canonica_emite_dos_eventos_y_documenta_el_reemplazo(tmp_path):
    """El ejemplo de docs/01: 'ya no como carne' tras 'como carne todos los
    días'. El reemplazado queda con su evento supersession; el nuevo con su
    extracción — y la relación vive en el payload, no hay que inferirla."""
    store = SqliteClaimStore(tmp_path / "embudo.db")
    original = _procesar(store, "como carne todos los dias", conv_id="conv-1")
    nuevo = _procesar(store, "ya no como carne", conv_id="conv-2")

    assert [e.tipo for e in store.events(claim_id=original.id)] == [
        "extraction", "supersession"]
    [sucesion] = store.events(claim_id=original.id, tipo="supersession")
    assert sucesion.payload["estado_anterior"] == "active"
    assert sucesion.payload["estado_nuevo"] == "superseded"
    assert sucesion.payload["sucesion"] == {
        "reemplaza_a": None, "reemplazado_por": nuevo.id}

    [extraccion_nuevo] = store.events(claim_id=nuevo.id, tipo="extraction")
    assert extraccion_nuevo.payload["sucesion"]["reemplaza_a"] == original.id
    store.close()


def test_repeticion_en_la_misma_conversacion_no_genera_evento(tmp_path):
    """Sin señal independiente no hay transición — y sin transición no hay
    evento: la cadena no se ruido."""
    store = SqliteClaimStore(tmp_path / "embudo.db")
    _procesar(store, "me gusta el cafe negro", conv_id="conv-1")
    _procesar(store, "me gusta el cafe negro", conv_id="conv-1")

    [claim] = store.active(agent_id="a1")
    assert [e.tipo for e in store.events(claim_id=claim.id)] == ["extraction"]
    store.close()


def test_revival_desde_expirado_documenta_el_estado_anterior(tmp_path):
    store = SqliteClaimStore(tmp_path / "embudo.db")
    claim = _procesar(store, "me gusta el cafe negro", conv_id="conv-1")

    claim = store.get(claim.id)
    claim.last_reinforced_at = "2024-01-01T00:00:00+00:00"
    store.add(claim)  # setup: envejecer
    [expirado] = expire_stale_claims(store)
    assert expirado.status.value == "expired"

    revivido = _procesar(store, "me gusta el cafe negro", conv_id="conv-9")

    [revival] = store.events(claim_id=revivido.id, tipo="reinforcement")
    assert revival.payload["estado_anterior"] == "expired"
    assert revival.payload["estado_nuevo"] == "active"
    store.close()


def test_promocion_rechazada_no_genera_evento(tmp_path):
    """Un intento fallido no cambia estado; sin transición no hay evento.
    La decisión y su motivo viven en el PromotionResult del llamante."""
    store = SqliteClaimStore(tmp_path / "embudo.db")
    claim = _procesar(store, "me gusta el cafe negro", conv_id="conv-1")

    resultado = promote_to_t3(store.get(claim.id), store)  # T1: rechazado

    assert not resultado.approved
    assert [e.tipo for e in store.events(claim_id=claim.id)] == ["extraction"]
    store.close()


def test_con_inmemory_no_hay_eventos_pero_el_pipeline_funciona(tmp_path):
    """El detector por capacidad: un store sin custodia corre el mismo
    pipeline sin emitir nada ni fallar (compatibilidad hacia atrás)."""
    from memory.store import InMemoryClaimStore

    store = InMemoryClaimStore()
    record = _conversacion("me gusta el cafe negro", conv_id="conv-1")
    for candidato in extract_candidates(record):
        resultado = reinforce_or_create(candidato, store)

    assert resultado.tier == Tier.T1
    assert store.active(agent_id="a1")
