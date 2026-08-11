"""Proveedor fake que implementa el puerto `LLMProvider` de verdad.

Portado de MagnusAgent (`tests/magnus_fixtures/fake_provider.py`). Cumple la
firma real `complete(req, resolved)` y se registra en un `ProviderRegistry`
como cualquier adaptador de producción, para que los tests verifiquen el
circuito real (perfil → registry → adaptador) en vez de una maqueta paralela.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterator

from providers.base import (
    Capability, LLMChunk, LLMProvider, LLMRequest, LLMResponse, ProviderError,
    ResolvedModel, Usage,
)


@dataclass
class RecordedCall:
    request: LLMRequest
    resolved: ResolvedModel


class FakeProvider(LLMProvider):
    """Devuelve texto predecible y registra cada llamada.

    `fail_with` permite forzar un `ProviderError` concreto (para probar la
    política de fallback): se lanza en las primeras `fail_times` llamadas y
    después el proveedor se comporta normalmente.
    """

    def __init__(self, name: str = "fake", *, text: str | Callable[[LLMRequest], str] | None = None,
                 fail_with: ProviderError | None = None, fail_times: int = 10**9,
                 delay_s: float = 0.0):
        self.name = name
        self._text = text
        self._fail_with = fail_with
        self._fail_times = fail_times
        self._delay_s = delay_s
        self.calls: list[RecordedCall] = []
        self._lock = threading.Lock()
        self.call_windows: list[tuple[float, float]] = []

    def supports(self, cap: Capability) -> bool:
        return cap in {Capability.STREAMING}

    def complete(self, req: LLMRequest, resolved: ResolvedModel) -> LLMResponse:
        inicio = time.monotonic()
        with self._lock:
            self.calls.append(RecordedCall(req, resolved))
        if self._delay_s:
            time.sleep(self._delay_s)
        with self._lock:
            self.call_windows.append((inicio, time.monotonic()))
        if self._fail_with is not None and len(self.calls) <= self._fail_times:
            raise self._fail_with
        if callable(self._text):
            text = self._text(req)
        elif self._text is not None:
            text = self._text
        else:
            text = f"respuesta de {self.name} con {resolved.model}"
        return LLMResponse(text=text, model=resolved.model,
                           usage=Usage(input_tokens=10, output_tokens=5))

    def stream(self, req: LLMRequest, resolved: ResolvedModel) -> Iterator[LLMChunk]:
        yield LLMChunk(delta=self.complete(req, resolved).text)

    # -- ayudas de aserción ---------------------------------------------------
    @property
    def last(self) -> RecordedCall:
        if not self.calls:
            raise AssertionError(f"el proveedor '{self.name}' no recibió ninguna llamada")
        return self.calls[-1]

    @property
    def models_used(self) -> list[str]:
        return [c.resolved.model for c in self.calls]
