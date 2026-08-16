"""Paquete público de EMS (Evidenced Memory System) — la fachada estable ([D-08]).

`memory/`, `rag/` y `orchestration/` son internos: modelos y primitivas que
pueden refactorizarse. Consumidores externos (la CLI, un bridge de agentes,
cualquier sistema) importan SOLO `ems`. Así el árbol interno puede
reorganizarse sin romper a quien dependa del sistema.
"""
from ems.api import EMS, Embudo

__all__ = ["EMS", "Embudo"]
__version__ = "0.2.0"
