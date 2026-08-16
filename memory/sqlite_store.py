"""Store SQLite de `MemoryClaim` — Fase A1 de `docs/04-PLAN-MEJORAS.md`.

Contrato idéntico a `memory/store.py` (la suite `tests/test_store_contract.py`
certifica ambos contra las mismas pruebas) más la capa de custodia que la RAM
no puede dar:

  - Tabla `claims`: el estado vigente de cada claim (upsert por id).
  - Tabla `events`: log append-only transaccional — la cadena de custodia.
    Se escribe EN LA MISMA TRANSACCIÓN que el cambio de claim que documenta
    ([D-07]): o persisten ambos, o ninguno. Los claims son estado derivable;
    los events no — el backup prioriza events.
  - Tabla `conversation_sources` [ALT-02]: metadatos mínimos de cada T0
    (conversación) con hash opcional según política — la relación
    claim↔conversación vive en `source_conversation_ids` (JSON) y en cada
    evento, pero sin esta tabla la purga (G2) y la auditoría DB (A4)
    prometerían lo que el JSONL T0 solo no sostiene.

Concurrency ([D-06]): WAL + single-writer como contrato explícito. Un solo
proceso escribe; si otro intenta tomar el lock de escritura, falla rápido con
`StoreLockedError` (mensaje claro) — no se cuelga ni se pierde la escritura
en silencio. Lectores concurrentes sí (WAL). Sin queue hasta que el piloto
muestre necesidad.

Esquema versionado: `PRAGMA user_version` + `_MIGRACIONES`. Una DB vieja se
abre y migra al día dentro de una transacción por versión; una DB "del
futuro" (versión mayor que el código que la abre) se rechaza con
`StoreVersionError` en vez de corromperse silenciosamente.

Tiempo: todo timestamp interno se escribe en UTC ISO-8601
(`datetime.now(timezone.utc)`); el orden autoritativo de los eventos es
`seq` (AUTOINCREMENT), no el reloj — un reloj alterado no reordena la
cadena de custodia.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from memory.claims import MemoryClaim, Status, Tier, normalize_text

#: Versión de esquema que maneja ESTE código. Migrar = añadir un paso nuevo
#: aquí y subirla; abrir una DB con user_version mayor es un error.
SCHEMA_VERSION = 1

#: Tipos de evento válidos — los mismos que `orchestration/audit.py:120-128`
#: documenta para la fase de memoria, más `wiki_sync` (Fase D del plan).
#: Cerrado a propósito: un evento con el nombre mal escrito rompería la
#: cadena de custodia en silencio.
TIPOS_EVENTO = frozenset({
    "extraction", "reinforcement", "promotion", "supersession",
    "expiration", "wiki_sync",
})

#: Migraciones por versión. Cada tupla corre dentro de UNA transacción y
#: termina fijando `user_version` — si algo falla a mitad, la DB queda en la
#: versión anterior, nunca a medias.
_MIGRACIONES: dict[int, tuple[str, ...]] = {
    1: (
        """
        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            subject_norm TEXT NOT NULL,
            text TEXT NOT NULL,
            tier TEXT NOT NULL,
            confidence REAL NOT NULL,
            source_conversation_ids TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_reinforced_at TEXT NOT NULL,
            reinforcement_count INTEGER NOT NULL,
            supersedes TEXT,
            superseded_by TEXT,
            decay_half_life_days INTEGER NOT NULL,
            status TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_claims_subject ON claims (agent_id, subject_norm)",
        "CREATE INDEX IF NOT EXISTS idx_claims_status ON claims (status)",
        """
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            tipo TEXT NOT NULL,
            claim_id TEXT,
            conversation_id TEXT,
            payload TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_events_claim ON events (claim_id)",
        """
        CREATE TABLE IF NOT EXISTS conversation_sources (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            sha256 TEXT
        )
        """,
    ),
}


class StoreLockedError(RuntimeError):
    """Otro writer posee el store ([D-06]: single-writer explícito)."""


class StoreVersionError(RuntimeError):
    """La DB fue escrita por una versión de esquema que este código no conoce."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class ClaimEvent:
    seq: int
    ts: str
    tipo: str
    claim_id: str | None
    conversation_id: str | None
    payload: dict | None


@dataclass(frozen=True)
class ConversationSource:
    id: str
    agent_id: str
    user_id: str
    started_at: str
    recorded_at: str
    sha256: str | None


class SqliteClaimStore:
    """Backend persistente de claims + cadena de custodia transaccional."""

    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 250):
        self.path = str(path)
        self.busy_timeout_ms = busy_timeout_ms
        es_memoria = self.path == ":memory:"
        if not es_memoria:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
        self._conn.execute("PRAGMA foreign_keys = ON")
        if not es_memoria:
            # WAL: lectores concurrentes sin bloquear al writer ([D-06]).
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._migrar()

    # -- esquema -------------------------------------------------------------------
    def _migrar(self) -> None:
        actual = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if actual > SCHEMA_VERSION:
            raise StoreVersionError(
                f"la DB en {self.path!r} tiene esquema v{actual} pero este código "
                f"solo conoce hasta v{SCHEMA_VERSION}; actualiza Embudo antes de abrirla"
            )
        for version in range(actual + 1, SCHEMA_VERSION + 1):
            sentencias = _MIGRACIONES[version]
            with self._write():
                for sentencia in sentencias:
                    self._conn.execute(sentencia)
                self._conn.execute(f"PRAGMA user_version = {version}")

    @property
    def schema_version(self) -> int:
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    @contextmanager
    def _write(self):
        """Transacción de escritura única (BEGIN IMMEDIATE): toma el lock de
        writer ANTES de leer, falla claro si lo tiene otro ([D-06]), y
        deshace todo si el cuerpo revienta."""
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc) or "busy" in str(exc):
                raise StoreLockedError(
                    f"otro writer posee el store {self.path!r}; Embudo es "
                    "single-writer por diseño ([D-06]) — cierra el otro proceso "
                    "o reintenta"
                ) from exc
            raise
        try:
            yield self._conn
        except BaseException:
            self._conn.rollback()
            raise
        self._conn.commit()

    # -- claims (contrato de tests/test_store_contract.py) --------------------------
    def add(self, claim: MemoryClaim, *, event_type: str | None = None,
            conversation_id: str | None = None,
            event_payload: dict | None = None) -> None:
        """Upsert del claim y, en la MISMA transacción, su evento ([D-07]).

        El payload se serializa ANTES de abrir la transacción: si no es
        serializable, no se escribe ni el claim ni el evento — atomicidad
        también ante errores del llamante, no solo de SQLite.
        """
        if event_type is not None and event_type not in TIPOS_EVENTO:
            raise ValueError(
                f"tipo de evento {event_type!r} no está en {sorted(TIPOS_EVENTO)}; "
                "un evento mal nombrado rompe la cadena de custodia"
            )
        payload_json = (
            json.dumps(event_payload, ensure_ascii=False)
            if event_payload is not None else None
        )
        with self._write():
            self._conn.execute(
                """
                INSERT INTO claims (id, agent_id, subject, subject_norm, text, tier,
                                    confidence, source_conversation_ids, first_seen_at,
                                    last_reinforced_at, reinforcement_count, supersedes,
                                    superseded_by, decay_half_life_days, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    tier = excluded.tier,
                    confidence = excluded.confidence,
                    source_conversation_ids = excluded.source_conversation_ids,
                    last_reinforced_at = excluded.last_reinforced_at,
                    reinforcement_count = excluded.reinforcement_count,
                    supersedes = excluded.supersedes,
                    superseded_by = excluded.superseded_by,
                    status = excluded.status
                """,
                (claim.id, claim.agent_id, claim.subject,
                 normalize_text(claim.subject), claim.text, claim.tier.value,
                 claim.confidence, json.dumps(claim.source_conversation_ids,
                                              ensure_ascii=False),
                 claim.first_seen_at, claim.last_reinforced_at,
                 claim.reinforcement_count, claim.supersedes, claim.superseded_by,
                 claim.decay_half_life_days, claim.status.value),
            )
            if event_type is not None:
                self._conn.execute(
                    "INSERT INTO events (ts, tipo, claim_id, conversation_id, payload)"
                    " VALUES (?,?,?,?,?)",
                    (_utcnow(), event_type, claim.id, conversation_id, payload_json),
                )

    def get(self, claim_id: str) -> MemoryClaim | None:
        fila = self._conn.execute(
            "SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        return self._claim_de_fila(fila) if fila is not None else None

    def all(self) -> list[MemoryClaim]:
        filas = self._conn.execute("SELECT * FROM claims ORDER BY rowid")
        return [self._claim_de_fila(f) for f in filas]

    def active(self, *, agent_id: str | None = None,
               tier: Tier | None = None) -> list[MemoryClaim]:
        sql, params = "SELECT * FROM claims WHERE status = ?", [Status.ACTIVE.value]
        if agent_id is not None:
            sql += " AND agent_id = ?"
            params.append(agent_id)
        if tier is not None:
            sql += " AND tier = ?"
            params.append(tier.value)
        return [self._claim_de_fila(f)
                for f in self._conn.execute(sql + " ORDER BY rowid", params)]

    def by_subject(self, agent_id: str, subject: str, *,
                   include_expired: bool = False) -> list[MemoryClaim]:
        """Misma semántica que `InMemoryClaimStore.by_subject`: solo vigentes
        por defecto (ACTIVE, y EXPIRED además si se pide) — la detección de
        contradicción y el match no consideran lo que ya no es evidencia."""
        estados = [Status.ACTIVE.value]
        if include_expired:
            estados.append(Status.EXPIRED.value)
        marcas = ",".join("?" * len(estados))
        filas = self._conn.execute(
            f"SELECT * FROM claims WHERE agent_id = ? AND subject_norm = ?"
            f" AND status IN ({marcas}) ORDER BY rowid",
            [agent_id, normalize_text(subject), *estados])
        return [self._claim_de_fila(f) for f in filas]

    @staticmethod
    def _claim_de_fila(fila: sqlite3.Row) -> MemoryClaim:
        return MemoryClaim(
            id=fila["id"], agent_id=fila["agent_id"], subject=fila["subject"],
            text=fila["text"], tier=Tier(fila["tier"]),
            confidence=fila["confidence"],
            source_conversation_ids=json.loads(fila["source_conversation_ids"]),
            first_seen_at=fila["first_seen_at"],
            last_reinforced_at=fila["last_reinforced_at"],
            reinforcement_count=fila["reinforcement_count"],
            supersedes=fila["supersedes"], superseded_by=fila["superseded_by"],
            decay_half_life_days=fila["decay_half_life_days"],
            status=Status(fila["status"]),
        )

    # -- events (cadena de custodia) --------------------------------------------------
    def append_event(self, tipo: str, *, claim_id: str | None = None,
                     conversation_id: str | None = None,
                     payload: dict | None = None) -> int:
        """Evento suelto (p. ej. `expiration` desde `decay`, que no toca
        claims vía `add`). Devuelve el `seq` asignado."""
        if tipo not in TIPOS_EVENTO:
            raise ValueError(
                f"tipo de evento {tipo!r} no está en {sorted(TIPOS_EVENTO)}"
            )
        payload_json = (json.dumps(payload, ensure_ascii=False)
                        if payload is not None else None)
        with self._write():
            cursor = self._conn.execute(
                "INSERT INTO events (ts, tipo, claim_id, conversation_id, payload)"
                " VALUES (?,?,?,?,?)",
                (_utcnow(), tipo, claim_id, conversation_id, payload_json))
            return cursor.lastrowid

    def events(self, *, claim_id: str | None = None,
               tipo: str | None = None) -> list[ClaimEvent]:
        sql, params = "SELECT * FROM events", []
        if claim_id is not None:
            sql += " WHERE claim_id = ?"
            params.append(claim_id)
        if tipo is not None:
            sql += (" AND" if "WHERE" in sql else " WHERE") + " tipo = ?"
            params.append(tipo)
        return [ClaimEvent(seq=f["seq"], ts=f["ts"], tipo=f["tipo"],
                           claim_id=f["claim_id"],
                           conversation_id=f["conversation_id"],
                           payload=json.loads(f["payload"]) if f["payload"] else None)
                for f in self._conn.execute(sql + " ORDER BY seq", params)]

    # -- T0: fuentes de conversación [ALT-02] -----------------------------------------
    def record_conversation_source(self, conversation_id: str, *, agent_id: str,
                                   user_id: str, started_at: str,
                                   sha256: str | None = None) -> None:
        """Registra (idempotente) los metadatos de una conversación T0.
        `sha256` es opcional y según política: hash del contenido crudo si la
        política de privacidad lo permite, NULL si no."""
        with self._write():
            self._conn.execute(
                """
                INSERT INTO conversation_sources
                    (id, agent_id, user_id, started_at, recorded_at, sha256)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    sha256 = COALESCE(excluded.sha256, conversation_sources.sha256)
                """,
                (conversation_id, agent_id, user_id, started_at,
                 _utcnow(), sha256))

    def conversation_source(self, conversation_id: str) -> ConversationSource | None:
        fila = self._conn.execute(
            "SELECT * FROM conversation_sources WHERE id = ?",
            (conversation_id,)).fetchone()
        if fila is None:
            return None
        return ConversationSource(
            id=fila["id"], agent_id=fila["agent_id"], user_id=fila["user_id"],
            started_at=fila["started_at"], recorded_at=fila["recorded_at"],
            sha256=fila["sha256"])

    def conversation_sources(self) -> list[ConversationSource]:
        filas = self._conn.execute(
            "SELECT * FROM conversation_sources ORDER BY id")
        return [ConversationSource(
            id=f["id"], agent_id=f["agent_id"], user_id=f["user_id"],
            started_at=f["started_at"], recorded_at=f["recorded_at"],
            sha256=f["sha256"]) for f in filas]

    # -- ciclo de vida ------------------------------------------------------------------
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SqliteClaimStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
