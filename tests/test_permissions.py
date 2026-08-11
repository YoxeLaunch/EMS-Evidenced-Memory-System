"""`PermissionEngine` — permiso efectivo = intersección de tres fuentes,
denegación por defecto, `deny` gana siempre sobre `allow`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from orchestration.permissions import PermissionDenied, PermissionEngine


@dataclass
class _Agente:
    id: str
    permissions_policy_ref: str
    knowledge_sources: list[str] = field(default_factory=list)
    tools_allow: list[str] = field(default_factory=list)
    tools_deny: list[str] = field(default_factory=list)


_PERMISSIONS_YAML = """
policies:
  fina_readonly:
    knowledge:
      read: ["01-Finanzas"]
    tools:
      allow: ["buscar_web"]
      deny: []
  fina_estricto:
    knowledge:
      read: ["01-Finanzas/personal"]
roles:
  operator:
    can: ["query"]
  admin:
    can: ["*"]
"""


def _engine(tmp_path) -> PermissionEngine:
    p = tmp_path / "permissions.yaml"
    p.write_text(_PERMISSIONS_YAML, encoding="utf-8")
    return PermissionEngine.from_yaml(p)


# -- conocimiento -----------------------------------------------------------------
def test_la_parcela_efectiva_es_la_interseccion(tmp_path):
    engine = _engine(tmp_path)
    fina = _Agente("fina", "fina_readonly", knowledge_sources=["01-Finanzas"])

    assert engine.allowed_namespaces(fina) == ["01-Finanzas"]
    assert engine.can_read(fina, "01-Finanzas").allowed is True


def test_un_namespace_fuera_de_knowledge_sources_se_deniega(tmp_path):
    engine = _engine(tmp_path)
    fina = _Agente("fina", "fina_readonly", knowledge_sources=["01-Finanzas"])

    decision = engine.can_read(fina, "02-Sueno")   # la política no lo declara tampoco

    assert not decision
    assert "no está en knowledge.sources" in decision.reason


def test_politica_mas_especifica_que_namespace_ancho_acota_a_la_subcarpeta(tmp_path):
    engine = _engine(tmp_path)
    agente_ancho = _Agente("fina_ancho", "fina_estricto", knowledge_sources=["01-Finanzas"])

    assert engine.allowed_namespaces(agente_ancho) == ["01-Finanzas/personal"]


def test_una_politica_inexistente_no_concede_nada(tmp_path):
    engine = _engine(tmp_path)
    agente_falso = _Agente("fantasma", "politica_que_no_existe", knowledge_sources=["01-Finanzas"])

    assert engine.allowed_namespaces(agente_falso) == []
    assert not engine.can_read(agente_falso, "01-Finanzas")


# -- herramientas -------------------------------------------------------------------
def test_deny_gana_sobre_allow_en_cualquier_nivel(tmp_path):
    engine = _engine(tmp_path)
    agente = _Agente("fina", "fina_readonly", knowledge_sources=["01-Finanzas"],
                     tools_allow=["buscar_web"], tools_deny=["buscar_web"])

    decision = engine.check_tool(agente, "buscar_web", rol="admin")

    assert not decision
    assert "deny gana sobre allow" in decision.reason


def test_una_herramienta_no_declarada_por_el_agente_se_deniega(tmp_path):
    engine = _engine(tmp_path)
    agente = _Agente("fina", "fina_readonly", knowledge_sources=["01-Finanzas"])

    assert not engine.check_tool(agente, "buscar_web", rol="admin")


def test_el_rol_sin_tools_use_no_puede_usar_herramientas(tmp_path):
    engine = _engine(tmp_path)
    agente = _Agente("fina", "fina_readonly", knowledge_sources=["01-Finanzas"],
                     tools_allow=["buscar_web"])

    decision = engine.check_tool(agente, "buscar_web", rol="operator")

    assert not decision
    assert "no está autorizado a usar herramientas" in decision.reason


def test_require_tool_lanza_permission_denied(tmp_path):
    engine = _engine(tmp_path)
    agente = _Agente("fina", "fina_readonly", knowledge_sources=["01-Finanzas"])

    with pytest.raises(PermissionDenied):
        engine.require_tool(agente, "buscar_web", rol="admin")


def test_effective_tools_es_la_interseccion(tmp_path):
    engine = _engine(tmp_path)
    agente = _Agente("fina", "fina_readonly", knowledge_sources=["01-Finanzas"],
                     tools_allow=["buscar_web", "no_concedida_por_politica"])

    assert engine.effective_tools(agente) == {"buscar_web"}
