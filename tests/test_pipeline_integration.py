"""Integración end-to-end del pipeline de memoria nivelada: T0 → T1 → T2 → T3
→ recuperación. No repite los casos límite de cada fase (ya cubiertos en su
propio archivo de test) — verifica que las piezas realmente encajan cuando
se usan juntas, como las usaría un llamante real.
"""
from __future__ import annotations

from datetime import datetime, timezone

from memory.capture import Consent, ConversationRecord, JsonlConversationStore, Turn, record_conversation
from memory.claims import Tier
from memory.extraction import extract_candidates
from memory.promotion import promote_to_t3
from memory.reinforcement import reinforce_or_create
from memory.retrieval import build_tiered_context
from memory.store import InMemoryClaimStore

_TS = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _consent() -> Consent:
    return Consent(True, "raw_conversation", "user-1", _TS)


def test_una_declaracion_repetida_en_tres_conversaciones_llega_a_t3_y_se_recupera(tmp_path):
    t0_store = JsonlConversationStore(tmp_path)
    claim_store = InMemoryClaimStore()

    # tres conversaciones distintas, la misma declaración en primera persona
    for i in range(3):
        turns = [Turn("user", "soy alergico a la penicilina", _TS)]
        record = record_conversation(
            t0_store, agent_id="a1", user_id="user-1", turns=turns, consent=_consent())

        for candidato in extract_candidates(record):
            reinforce_or_create(candidato, claim_store)

    activos_t2 = claim_store.active(agent_id="a1", tier=Tier.T2)
    assert len(activos_t2) == 1
    claim = activos_t2[0]
    assert claim.reinforcement_count == 3

    resultado = promote_to_t3(claim, claim_store)
    assert resultado.approved
    assert claim.tier == Tier.T3

    # la conversación cruda sigue disponible con proveniencia completa
    conversaciones = t0_store.read_all()
    assert len(conversaciones) == 3
    assert all(isinstance(c, ConversationRecord) for c in conversaciones)
    assert {c.agent_id for c in conversaciones} == {"a1"}

    # y el claim T3 se recupera con la etiqueta de autoridad plena
    ctx = build_tiered_context(claim_store, "alergico a la penicilina", "a1")
    assert ctx.t3 and not ctx.t2
    assert ctx.t3[0].confidence_label == "autoridad_plena"
    assert "penicilina" in ctx.t3[0].chunk.text


def test_una_contradiccion_posterior_sucede_al_claim_promovido_sin_borrarlo(tmp_path):
    """Mismo ejemplo que usa `docs/01-MEMORIA-NIVELADA.md` para contradicción
    explícita: 'como carne todos los días' vs 'ya no como carne'. La
    negación conserva el mismo subject ('carne') porque el resto de la frase
    no cambia — es justo el caso que el extractor determinista sabe
    reconocer sin inferencia semántica."""
    t0_store = JsonlConversationStore(tmp_path)
    claim_store = InMemoryClaimStore()

    for i in range(3):
        turns = [Turn("user", "como carne todos los dias", _TS)]
        record = record_conversation(
            t0_store, agent_id="a1", user_id="user-1", turns=turns, consent=_consent())
        for candidato in extract_candidates(record):
            reinforce_or_create(candidato, claim_store)

    [claim_t2] = claim_store.active(agent_id="a1", tier=Tier.T2)
    promote_to_t3(claim_t2, claim_store)
    assert claim_t2.tier == Tier.T3

    # el usuario cambia de hábito — declaración contradictoria en una conversación nueva
    turns = [Turn("user", "no como carne todos los dias", _TS)]
    record = record_conversation(
        t0_store, agent_id="a1", user_id="user-1", turns=turns, consent=_consent())
    [contradiccion] = extract_candidates(record)
    resultado = reinforce_or_create(contradiccion, claim_store)

    assert resultado.text == "no como carne todos los dias"
    assert claim_t2.status.value == "superseded"
    assert claim_t2.superseded_by == resultado.id
    assert claim_store.get(claim_t2.id) is claim_t2, "el reemplazado sigue consultable"

    # sin consentimiento no se hubiera podido registrar nada de esto
    conversaciones = t0_store.read_all()
    assert all(c.consent.granted for c in conversaciones)


def test_ejemplo_canonico_de_docs01_ya_no_como_carne_end_to_end(tmp_path):
    """El ejemplo LITERAL de `docs/01-MEMORIA-NIVELADA.md` ('ya no como
    carne' tras 'como carne todos los días'), con el claim original aún en
    T1 — antes de la Fase B este circuito no existía: 'ya no como carne' ni
    siquiera producía candidato, y una negación de un T1 reforzaba a su
    opuesto. Ahora: extracción → contradicción → sucesión sin borrado."""
    t0_store = JsonlConversationStore(tmp_path)
    claim_store = InMemoryClaimStore()

    turns = [Turn("user", "como carne todos los dias", _TS)]
    record = record_conversation(
        t0_store, agent_id="a1", user_id="user-1", turns=turns, consent=_consent())
    for candidato in extract_candidates(record):
        reinforce_or_create(candidato, claim_store)

    [original] = claim_store.active(agent_id="a1")
    assert original.tier == Tier.T1

    turns = [Turn("user", "ya no como carne", _TS)]
    record = record_conversation(
        t0_store, agent_id="a1", user_id="user-1", turns=turns, consent=_consent())
    [cambio] = extract_candidates(record)
    resultado = reinforce_or_create(cambio, claim_store)

    assert original.status.value == "superseded"
    assert original.superseded_by == resultado.id
    assert resultado.supersedes == original.id
    assert resultado.tier == Tier.T1, "la sucesión no hereda autoridad"
    assert claim_store.get(original.id) is original, "el reemplazado conserva proveniencia"
