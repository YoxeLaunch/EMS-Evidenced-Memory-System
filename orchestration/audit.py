"""Registro trazable de eventos — auditoría opt-in, sin contenido sensible.

Portado de MagnusAgent (`orchestration/audit.py`) — ver
`docs/02-COMPONENTES-REUTILIZABLES.md`. La fase de memoria nivelada
(`docs/01-MEMORIA-NIVELADA.md`) extenderá `build_entry` para registrar sus
propios eventos (extracción, refuerzo, promoción, sucesión, expiración); esta
capa de almacenamiento (`TraceStore` / `JsonlTraceStore`) no depende de eso y
queda lista desde ya.

Corrección aplicada en el port (hallazgo de seguridad de Magnus, no repetido
aquí): el directorio de trazas se crea con permisos `0700` y cada archivo
JSONL con `0600` desde el primer `record()`, no como parche posterior — un
registro de auditoría que contiene consultas y proveniencia de datos
personales no debe quedar legible por otros usuarios del sistema.

Privacidad — decisión deliberada
--------------------------------
  - El registro está **desactivado por defecto** (`NullTraceStore`). Se activa
    explícitamente (`EMBUDO_TRACE_DIR=...`). Nada se escribe a disco si nadie
    lo pidió.
  - Se guardan referencias (id, hash), nunca el texto de los pasajes ni la
    respuesta generada.
  - El directorio por defecto (`traces/`) está en `.gitignore`.
"""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class TraceStore(Protocol):
    def record(self, entry: dict) -> None: ...


@dataclass
class NullTraceStore:
    """No escribe nada. Es el comportamiento por defecto."""

    def record(self, entry: dict) -> None:  # noqa: D102
        return None


class JsonlTraceStore:
    """Un archivo JSONL por día, en append. Sin dependencias externas.

    Permisos restrictivos desde el diseño
    --------------------------------------
    El directorio se crea `0700` (solo el dueño puede entrar) y cada archivo
    de traza se fuerza a `0600` (solo el dueño puede leer/escribir) tras cada
    escritura — en POSIX. En Windows `chmod` no aplica ACLs equivalentes; ahí
    la restricción de acceso depende de los permisos NTFS del directorio
    padre, y se documenta como limitación conocida en vez de fingir paridad.

    Rotación por tamaño (opt-in vía ``max_total_mb``)
    ---------------------------------------------------
    Las trazas se acumulan indefinidamente por defecto. Si se fija
    ``max_total_mb`` (o `EMBUDO_TRACE_MAX_MB` vía :func:`trace_store_from_env`),
    cada `record()` revisa el tamaño total del directorio *después* de
    escribir y, si excede el límite, borra los archivos `embudo-*.jsonl` más
    antiguos (por nombre, que ya ordena por fecha `YYYY-MM-DD`) hasta volver a
    estar dentro del límite. El archivo del día actual nunca se borra, aunque
    él solo exceda el límite — la purga es perezosa (un chequeo por
    escritura, no un daemon) y deliberadamente no trunca un archivo a medio
    escribir.
    """

    def __init__(self, directory: str | Path, *, max_total_mb: float | None = None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._asegurar_permisos_directorio()
        self.max_total_mb = max_total_mb

    def _asegurar_permisos_directorio(self) -> None:
        if os.name == "posix":
            os.chmod(self.directory, stat.S_IRWXU)  # 0700

    def _path(self) -> Path:
        dia = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.directory / f"embudo-{dia}.jsonl"

    def record(self, entry: dict) -> None:
        ruta_actual = self._path()
        existia = ruta_actual.exists()
        linea = json.dumps(entry, ensure_ascii=False)
        with open(ruta_actual, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
        if not existia and os.name == "posix":
            os.chmod(ruta_actual, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        if self.max_total_mb is not None:
            self._purgar_si_excede(ruta_actual)

    def _purgar_si_excede(self, ruta_actual: Path) -> None:
        limite_bytes = self.max_total_mb * 1024 * 1024
        archivos = sorted(self.directory.glob("embudo-*.jsonl"))
        total = sum(a.stat().st_size for a in archivos)
        for archivo in archivos:
            if total <= limite_bytes or archivo == ruta_actual:
                continue
            total -= archivo.stat().st_size
            archivo.unlink()


def trace_store_from_env(
    var: str = "EMBUDO_TRACE_DIR", max_mb_var: str = "EMBUDO_TRACE_MAX_MB"
) -> TraceStore:
    """`JsonlTraceStore` si la variable está puesta; si no, no registra nada."""
    directorio = os.environ.get(var, "").strip()
    if not directorio:
        return NullTraceStore()
    max_mb_raw = os.environ.get(max_mb_var, "").strip()
    max_mb = float(max_mb_raw) if max_mb_raw else None
    return JsonlTraceStore(directorio, max_total_mb=max_mb)


def build_entry(*, agent_id: str, event: str, details: dict,
                source_conversation_ids: list[str] | None = None) -> dict:
    """Entrada de auditoría genérica.

    Punto de extensión para la fase de memoria nivelada: `event` será
    `"extraction"`, `"reinforcement"`, `"promotion"`, `"supersession"`,
    `"expiration"`, y `details` llevará los ids/hashes de `MemoryClaim`
    involucrados — nunca el texto del claim ni de la conversación.
    """
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agente": agent_id,
        "evento": event,
        "detalles": details,
        "conversaciones_origen": source_conversation_ids or [],
    }
