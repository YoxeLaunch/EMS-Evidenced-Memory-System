"""Paquete público de Embudo — la fachada estable ([D-08]).

`memory/`, `rag/` y `orchestration/` son internos: modelos y primitivas que
pueden refactorizarse. Consumidores externos (la CLI, un futuro bridge de
MagnusAgent, cualquier agente) importan SOLO `embudo`. Así el árbol interno
puede reorganizarse sin romper a quien dependa del sistema.
"""
from embudo.api import Embudo

__all__ = ["Embudo"]
__version__ = "0.2.0"
