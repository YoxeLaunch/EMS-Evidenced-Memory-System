"""Configuración común de la suite.

Dos garantías que la suite entera debe cumplir (criterio de hecho de la
Fase 0, `docs/03-ROADMAP.md`): corre en un checkout limpio, y corre sin red
ni credenciales. La segunda se hace explícita aquí borrando del entorno
cualquier clave que la máquina del desarrollador pudiera tener puesta — si
algún test intentara usar un proveedor real, fallará por credencial ausente
en vez de gastar dinero o salir a internet en silencio.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # permite `pytest` sin `pip install -e .`
    sys.path.insert(0, str(ROOT))

_CLAVES_DE_PROVEEDOR = [
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "MISTRAL_API_KEY", "OPENROUTER_API_KEY", "EMS_PROVIDER", "EMBUDO_PROVIDER",
]


@pytest.fixture(autouse=True)
def sin_credenciales(monkeypatch):
    for clave in _CLAVES_DE_PROVEEDOR:
        monkeypatch.delenv(clave, raising=False)


@pytest.fixture
def repo_root() -> Path:
    return ROOT
