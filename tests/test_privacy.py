"""`EgressPolicy` — denegación de egreso remoto por defecto."""
from __future__ import annotations

from orchestration.privacy import EgressPolicy, LOCAL_ONLY, REMOTE_ALLOWED

_PRIVACY_YAML = """
egreso:
  por_defecto: local_only
  proveedores_locales:
    - ollama
  namespaces:
    06-Tecnologia-e-IA: remote_allowed
    02-Salud-Corporal: local_only
    01-Finanzas/personal: remote_allowed
"""


def _policy(tmp_path) -> EgressPolicy:
    p = tmp_path / "privacy.yaml"
    p.write_text(_PRIVACY_YAML, encoding="utf-8")
    return EgressPolicy.from_yaml(p)


def test_un_namespace_no_declarado_usa_el_defecto_local_only(tmp_path):
    policy = _policy(tmp_path)
    assert policy.politica_de("03-namespace-nuevo-sin-declarar") == LOCAL_ONLY


def test_un_namespace_declarado_remote_allowed_puede_salir(tmp_path):
    policy = _policy(tmp_path)
    assert policy.politica_de("06-Tecnologia-e-IA") == REMOTE_ALLOWED


def test_un_namespace_declarado_local_only_no_sale(tmp_path):
    policy = _policy(tmp_path)
    assert policy.politica_de("02-Salud-Corporal") == LOCAL_ONLY


def test_una_subcarpeta_hereda_la_politica_del_ancestro_mas_especifico(tmp_path):
    policy = _policy(tmp_path)
    assert policy.politica_de("01-Finanzas/personal/2026") == REMOTE_ALLOWED


def test_check_bloquea_si_uno_solo_de_los_namespaces_lo_prohibe(tmp_path):
    policy = _policy(tmp_path)
    decision = policy.check(["06-Tecnologia-e-IA", "02-Salud-Corporal"])

    assert decision.remote_allowed is False
    assert decision.blocking_namespaces == ("02-Salud-Corporal",)


def test_check_permite_si_todos_autorizan_egreso_remoto(tmp_path):
    policy = _policy(tmp_path)
    decision = policy.check(["06-Tecnologia-e-IA", "01-Finanzas/personal"])
    assert decision.remote_allowed is True


def test_sin_archivo_la_postura_por_defecto_es_restrictiva(tmp_path):
    policy = EgressPolicy.from_yaml(tmp_path / "no_existe.yaml")
    assert policy.activa is False
    assert policy.politica_de("cualquier_namespace") == LOCAL_ONLY


def test_es_local_distingue_proveedores(tmp_path):
    policy = _policy(tmp_path)
    assert policy.es_local("ollama") is True
    assert policy.es_local("anthropic") is False
