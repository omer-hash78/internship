from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROLE_VALUES = ("admin", "operator", "viewer")
DOCUMENT_STATUS_VALUES = ("REGISTERED", "IN_REVIEW", "APPROVED", "ARCHIVED")
AUDIT_HASH_VERSION_LEGACY = 1
AUDIT_HASH_VERSION_CURRENT = 2


class DatabaseError(Exception):
    pass


class DatabaseUnavailableError(DatabaseError):
    pass


class DatabaseLockError(DatabaseError):
    pass


class IntegrityConstraintError(DatabaseError):
    pass


@dataclass(frozen=True)
class AuditVerificationResult:
    ok: bool
    checked_rows: int
    broken_history_id: int | None = None
    message: str = ""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_text() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def serialize_state(state: dict[str, Any] | None) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":")) if state else ""


def compute_history_record_hash(
    *,
    previous_record_hash: str,
    document_id: int,
    actor_user_id: int,
    action_type: str,
    previous_state: str,
    new_state: str,
    state_version: int,
    workstation_name: str,
    ip_address: str,
    reason: str,
    created_at_utc: str,
) -> str:
    return compute_history_record_hash_v2(
        previous_record_hash=previous_record_hash,
        document_id=document_id,
        actor_user_id=actor_user_id,
        action_type=action_type,
        previous_state=previous_state,
        new_state=new_state,
        state_version=state_version,
        workstation_name=workstation_name,
        ip_address=ip_address,
        reason=reason,
        created_at_utc=created_at_utc,
    )


def compute_history_record_hash_v1(
    *,
    previous_record_hash: str,
    document_id: int,
    actor_user_id: int,
    action_type: str,
    previous_state: str,
    new_state: str,
    state_version: int,
    workstation_name: str,
    ip_address: str,
    reason: str,
    created_at_utc: str,
) -> str:
    payload = "|".join(
        [
            previous_record_hash,
            str(document_id),
            str(actor_user_id),
            action_type,
            previous_state,
            new_state,
            str(state_version),
            workstation_name,
            ip_address,
            reason,
            created_at_utc,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_history_record_hash_v2(
    *,
    previous_record_hash: str,
    document_id: int,
    actor_user_id: int,
    action_type: str,
    previous_state: str,
    new_state: str,
    state_version: int,
    workstation_name: str,
    ip_address: str,
    reason: str,
    created_at_utc: str,
) -> str:
    payload = {
        "action_type": action_type,
        "actor_user_id": actor_user_id,
        "created_at_utc": created_at_utc,
        "document_id": document_id,
        "ip_address": ip_address,
        "new_state": new_state,
        "previous_record_hash": previous_record_hash,
        "previous_state": previous_state,
        "reason": reason,
        "state_version": state_version,
        "workstation_name": workstation_name,
    }
    serialized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


class DatabaseManager:
    def __init__(self, db_path: Path | str, backup_dir: Path | str, app_logger) -> None:
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.logger = app_logger

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(self._schema_script())
            self._apply_runtime_migrations(connection)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = sqlite3.connect(
                self.db_path,
                timeout=5.0,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            self._configure_connection(connection)
            yield connection
        except sqlite3.Error as exc:
            raise self._classify_sqlite_error(exc) from exc
        finally:
            if connection is not None:
                connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def backup_database(self) -> Path:
        timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
        backup_path = self.backup_dir / f"xdts_backup_{timestamp}.db"
        try:
            with self.connect() as source:
                target = sqlite3.connect(backup_path)
                try:
                    source.backup(target)
                finally:
                    target.close()
        except DatabaseError:
            self.logger.exception("Backup failed.")
            raise
        self.logger.info("Backup created at %s", backup_path)
        return backup_path

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(query, params).fetchone()

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(query, params).fetchall()

    def cleanup_expired_leases(self, *, connection: sqlite3.Connection | None = None) -> int:
        active_connection = connection
        owns_connection = active_connection is None
        if owns_connection:
            active_connection_cm = self.transaction()
            active_connection = active_connection_cm.__enter__()
        try:
            result = active_connection.execute(
                "DELETE FROM document_leases WHERE expires_at_utc <= ?",
                (utc_now_text(),),
            )
            deleted_count = result.rowcount
            if deleted_count:
                self.logger.info("Cleaned %s expired document lease(s).", deleted_count)
            return deleted_count
        finally:
            if owns_connection:
                active_connection_cm.__exit__(None, None, None)

    def append_history(
        self,
        connection: sqlite3.Connection,
        *,
        document_id: int,
        actor_user_id: int,
        action_type: str,
        previous_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
        state_version: int,
        workstation_name: str,
        ip_address: str | None,
        reason: str | None,
    ) -> int:
        previous_hash_row = connection.execute(
            "SELECT id, record_hash FROM history ORDER BY id DESC LIMIT 1"
        ).fetchone()
        previous_record_hash = previous_hash_row["record_hash"] if previous_hash_row else ""
        created_at_utc = utc_now_text()
        previous_state_text = serialize_state(previous_state)
        new_state_text = serialize_state(new_state)
        normalized_ip = ip_address or ""
        normalized_reason = (reason or "").strip()
        record_hash = compute_history_record_hash(
            previous_record_hash=previous_record_hash,
            document_id=document_id,
            actor_user_id=actor_user_id,
            action_type=action_type,
            previous_state=previous_state_text,
            new_state=new_state_text,
            state_version=state_version,
            workstation_name=workstation_name,
            ip_address=normalized_ip,
            reason=normalized_reason,
            created_at_utc=created_at_utc,
        )
        cursor = connection.execute(
            """
            INSERT INTO history (
                document_id,
                actor_user_id,
                action_type,
                previous_state,
                new_state,
                state_version,
                workstation_name,
                ip_address,
                reason,
                created_at_utc,
                previous_record_hash,
                record_hash,
                audit_hash_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                actor_user_id,
                action_type,
                previous_state_text,
                new_state_text,
                state_version,
                workstation_name,
                normalized_ip,
                normalized_reason,
                created_at_utc,
                previous_record_hash,
                record_hash,
                AUDIT_HASH_VERSION_CURRENT,
            ),
        )
        return int(cursor.lastrowid)

    def verify_audit_chain(self) -> AuditVerificationResult:
        rows = self.fetch_all(
            """
            SELECT
                id,
                document_id,
                actor_user_id,
                action_type,
                previous_state,
                new_state,
                state_version,
                workstation_name,
                ip_address,
                reason,
                created_at_utc,
                previous_record_hash,
                record_hash,
                audit_hash_version
            FROM history
            ORDER BY id
            """
        )
        expected_previous_hash = ""
        checked_rows = 0
        for row in rows:
            if row["audit_hash_version"] == AUDIT_HASH_VERSION_LEGACY:
                recalculated_hash = compute_history_record_hash_v1(
                    previous_record_hash=expected_previous_hash,
                    document_id=row["document_id"],
                    actor_user_id=row["actor_user_id"],
                    action_type=row["action_type"],
                    previous_state=row["previous_state"] or "",
                    new_state=row["new_state"] or "",
                    state_version=row["state_version"],
                    workstation_name=row["workstation_name"] or "",
                    ip_address=row["ip_address"] or "",
                    reason=row["reason"] or "",
                    created_at_utc=row["created_at_utc"],
                )
            elif row["audit_hash_version"] == AUDIT_HASH_VERSION_CURRENT:
                recalculated_hash = compute_history_record_hash_v2(
                    previous_record_hash=expected_previous_hash,
                    document_id=row["document_id"],
                    actor_user_id=row["actor_user_id"],
                    action_type=row["action_type"],
                    previous_state=row["previous_state"] or "",
                    new_state=row["new_state"] or "",
                    state_version=row["state_version"],
                    workstation_name=row["workstation_name"] or "",
                    ip_address=row["ip_address"] or "",
                    reason=row["reason"] or "",
                    created_at_utc=row["created_at_utc"],
                )
            else:
                return AuditVerificationResult(
                    ok=False,
                    checked_rows=checked_rows,
                    broken_history_id=row["id"],
                    message=f"Unsupported audit hash version: {row['audit_hash_version']}.",
                )
            if row["previous_record_hash"] != expected_previous_hash:
                return AuditVerificationResult(
                    ok=False,
                    checked_rows=checked_rows,
                    broken_history_id=row["id"],
                    message="History chain previous hash mismatch.",
                )
            if row["record_hash"] != recalculated_hash:
                return AuditVerificationResult(
                    ok=False,
                    checked_rows=checked_rows,
                    broken_history_id=row["id"],
                    message="History chain record hash mismatch.",
                )
            expected_previous_hash = row["record_hash"]
            checked_rows += 1
        return AuditVerificationResult(
            ok=True,
            checked_rows=checked_rows,
            message="Audit chain verified successfully.",
        )

    def _configure_connection(self, connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")

    def _apply_runtime_migrations(self, connection: sqlite3.Connection) -> None:
        history_columns = {
            row["name"]: row
            for row in connection.execute("PRAGMA table_info(history)").fetchall()
        }
        if "audit_hash_version" not in history_columns:
            connection.execute(
                """
                ALTER TABLE history
                ADD COLUMN audit_hash_version INTEGER NOT NULL DEFAULT 1
                """
            )

    def _classify_sqlite_error(self, exc: sqlite3.Error) -> DatabaseError:
        message = str(exc).lower()
        if isinstance(exc, sqlite3.IntegrityError):
            return IntegrityConstraintError(str(exc))
        if "database is locked" in message or "database table is locked" in message:
            return DatabaseLockError("Database is busy. Please retry.")
        if "unable to open database file" in message or "readonly database" in message:
            return DatabaseUnavailableError("Database unavailable. Please retry.")
        if isinstance(exc, sqlite3.OperationalError):
            return DatabaseUnavailableError("Database unavailable. Please retry.")
        return DatabaseError("Database operation failed.")

    def _schema_script(self) -> str:
        roles = ", ".join(f"'{role}'" for role in ROLE_VALUES)
        statuses = ", ".join(f"'{status}'" for status in DOCUMENT_STATUS_VALUES)
        return f"""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            password_algorithm TEXT NOT NULL,
            password_iterations INTEGER NOT NULL CHECK(password_iterations > 0),
            role TEXT NOT NULL CHECK(role IN ({roles})),
            failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK(failed_attempts >= 0),
            cooldown_until_utc TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
            created_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_number TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ({statuses})),
            current_holder_user_id INTEGER,
            created_by_user_id INTEGER NOT NULL,
            last_state_version INTEGER NOT NULL DEFAULT 1 CHECK(last_state_version >= 1),
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            FOREIGN KEY(current_holder_user_id) REFERENCES users(id),
            FOREIGN KEY(created_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            previous_state TEXT NOT NULL DEFAULT '',
            new_state TEXT NOT NULL DEFAULT '',
            state_version INTEGER NOT NULL CHECK(state_version >= 0),
            workstation_name TEXT NOT NULL,
            ip_address TEXT,
            reason TEXT,
            created_at_utc TEXT NOT NULL,
            previous_record_hash TEXT NOT NULL DEFAULT '',
            record_hash TEXT NOT NULL,
            audit_hash_version INTEGER NOT NULL DEFAULT 1 CHECK(audit_hash_version >= 1),
            FOREIGN KEY(document_id) REFERENCES documents(id),
            FOREIGN KEY(actor_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS document_leases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            workstation_name TEXT NOT NULL,
            lease_start_utc TEXT NOT NULL,
            expires_at_utc TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_documents_document_number
            ON documents(document_number);
        CREATE INDEX IF NOT EXISTS idx_documents_current_holder
            ON documents(current_holder_user_id);
        CREATE INDEX IF NOT EXISTS idx_documents_last_state_version
            ON documents(last_state_version);
        CREATE INDEX IF NOT EXISTS idx_history_document_created
            ON history(document_id, created_at_utc);
        CREATE INDEX IF NOT EXISTS idx_history_actor_created
            ON history(actor_user_id, created_at_utc);
        CREATE INDEX IF NOT EXISTS idx_document_leases_document_expires
            ON document_leases(document_id, expires_at_utc);

        CREATE TRIGGER IF NOT EXISTS history_prevent_update
        BEFORE UPDATE ON history
        BEGIN
            SELECT RAISE(ABORT, 'history is append-only');
        END;

        CREATE TRIGGER IF NOT EXISTS history_prevent_delete
        BEFORE DELETE ON history
        BEGIN
            SELECT RAISE(ABORT, 'history is append-only');
        END;
        """
