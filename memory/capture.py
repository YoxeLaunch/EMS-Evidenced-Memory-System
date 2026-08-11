"""Captura de conversación cruda (T0) — `docs/01-MEMORIA-NIVELADA.md`.

Primer componente sin equivalente directo en MagnusAgent
(`docs/02-COMPONENTES-REUTILIZABLES.md` lo marca explícitamente así): Magnus
nunca guarda la conversación misma como fuente, solo consulta contra una
wiki ya escrita. Aquí la conversación ES la materia prima de todo el
pipeline — sin un T0 con proveniencia completa no hay nada de qué extraer
candidatos en la Fase 2.

Consentimiento explícito
-------------------------
`record_conversation()` exige un `Consent` con `granted=True` pasado
explícitamente por el llamante en cada invocación. No existe ningún default
persistente ("ya consintió una vez, se asume para siempre") — eso
convertiría el consentimiento en un trámite de una sola vez en vez de una
autorización real por conversación. Sin consentimiento concedido, no se
escribe nada a disco: `ConsentRequired` se lanza ANTES de tocar el store.

Egreso denegado por defecto (principio 5 de `docs/00-VISION-Y-ARQUITECTURA.md`)
---------------------------------------------------------------------------------
Este módulo no tiene ningún camino de red: `JsonlConversationStore` escribe
exclusivamente a disco local, con los mismos permisos restrictivos que
`orchestration/audit.py` (0700 el directorio, 0600 cada archivo en POSIX).
El principio se cumple aquí por construcción, no por una comprobación en
tiempo de ejecución — no hay ninguna función en este archivo capaz de hacer
una petición HTTP.

Por qué NO se reutiliza `orchestration/audit.py`
--------------------------------------------------
`JsonlTraceStore` guarda deliberadamente NUNCA el texto de los pasajes ni de
la respuesta (ver su docstring) — es una traza de auditoría, no la fuente.
El propósito de este módulo es exactamente lo contrario: guardar el texto
completo de la conversación, porque es la materia prima T0. Comparten el
patrón de almacenamiento (JSONL en append, permisos restrictivos, rotación
por tamaño) pero no el contrato — de ahí el store separado en vez de
extender el de auditoría con una bandera "esta vez sí guarda el texto".
"""
from __future__ import annotations

import json
import os
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Turn:
    role: str          # "user" | "assistant"
    content: str
    ts: str             # ISO-8601, UTC

    def as_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "ts": self.ts}

    @classmethod
    def from_dict(cls, d: dict) -> "Turn":
        return cls(role=d["role"], content=d["content"], ts=d["ts"])


@dataclass(frozen=True)
class Consent:
    """Autorización explícita de qué se guarda, por quién y cuándo.

    `scope` describe QUÉ se consintió guardar (p.ej. "raw_conversation") —
    deja espacio para consentimientos más finos en el futuro (p.ej. "solo
    metadatos, no el texto") sin cambiar la forma del dato.
    """
    granted: bool
    scope: str
    granted_by: str     # normalmente el user_id de quien consiente
    granted_at: str      # ISO-8601, UTC

    def as_dict(self) -> dict:
        return {"concedido": self.granted, "alcance": self.scope,
                "concedido_por": self.granted_by, "concedido_en": self.granted_at}

    @classmethod
    def from_dict(cls, d: dict) -> "Consent":
        return cls(granted=d["concedido"], scope=d["alcance"],
                   granted_by=d["concedido_por"], granted_at=d["concedido_en"])


class ConsentRequired(PermissionError):
    """No se guarda nada sin consentimiento explícito y concedido."""


@dataclass(frozen=True)
class ConversationRecord:
    """Un registro T0 — la conversación tal cual, con proveniencia completa.

    `id` es opaco (uuid4): a diferencia de `MemoryClaim.id` (hash de
    contenido normalizado, para deduplicar candidatos en la Fase 2), un T0
    no se deduplica por contenido — dos conversaciones pueden decir lo mismo
    y siguen siendo dos eventos distintos con su propia proveniencia.
    """
    id: str
    agent_id: str
    user_id: str
    started_at: str      # ISO-8601, UTC — el "cuándo" de la proveniencia
    turns: tuple[Turn, ...]
    consent: Consent

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "agente": self.agent_id,
            "usuario": self.user_id,
            "iniciada_en": self.started_at,
            "turnos": [t.as_dict() for t in self.turns],
            "consentimiento": self.consent.as_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationRecord":
        return cls(
            id=d["id"], agent_id=d["agente"], user_id=d["usuario"],
            started_at=d["iniciada_en"],
            turns=tuple(Turn.from_dict(t) for t in d["turnos"]),
            consent=Consent.from_dict(d["consentimiento"]),
        )


class JsonlConversationStore:
    """Un archivo JSONL por día, en append. Sin dependencias externas.

    Mismo patrón de endurecimiento que `orchestration.audit.JsonlTraceStore`
    (permisos restrictivos desde el primer `append()`, rotación perezosa por
    tamaño) pero como store independiente — ver el docstring del módulo para
    por qué no se comparte la clase.
    """

    def __init__(self, directory: str | Path, *, max_total_mb: float | None = None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(self.directory, stat.S_IRWXU)  # 0700
        self.max_total_mb = max_total_mb

    def _path(self) -> Path:
        dia = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.directory / f"conversations-{dia}.jsonl"

    def append(self, record: ConversationRecord) -> None:
        ruta = self._path()
        existia = ruta.exists()
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")
        if not existia and os.name == "posix":
            os.chmod(ruta, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        if self.max_total_mb is not None:
            self._purgar_si_excede(ruta)

    def _purgar_si_excede(self, ruta_actual: Path) -> None:
        limite_bytes = self.max_total_mb * 1024 * 1024
        archivos = sorted(self.directory.glob("conversations-*.jsonl"))
        total = sum(a.stat().st_size for a in archivos)
        for archivo in archivos:
            if total <= limite_bytes or archivo == ruta_actual:
                continue
            total -= archivo.stat().st_size
            archivo.unlink()

    def read_all(self) -> list[ConversationRecord]:
        """Lee todos los registros de todos los días, en orden de escritura.

        Punto de entrada que usará el extractor de candidatos (Fase 2) para
        recorrer el T0 acumulado.
        """
        registros = []
        for archivo in sorted(self.directory.glob("conversations-*.jsonl")):
            for linea in archivo.read_text(encoding="utf-8").splitlines():
                if linea.strip():
                    registros.append(ConversationRecord.from_dict(json.loads(linea)))
        return registros


def record_conversation(
    store: JsonlConversationStore, *, agent_id: str, user_id: str,
    turns: list[Turn], consent: Consent,
) -> ConversationRecord:
    """Guarda una conversación como T0, con proveniencia completa.

    Lanza `ConsentRequired` ANTES de tocar el store si `consent.granted` es
    falso — sin eso no hay materia prima que guardar, por diseño (ver
    docstring del módulo).
    """
    if not consent.granted:
        raise ConsentRequired(
            f"'{user_id}' no concedió consentimiento explícito para guardar "
            f"esta conversación con el agente '{agent_id}' (alcance solicitado: "
            f"'{consent.scope}')")

    record = ConversationRecord(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        user_id=user_id,
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        turns=tuple(turns),
        consent=consent,
    )
    store.append(record)
    return record
