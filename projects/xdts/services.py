from __future__ import annotations

import logging
import socket
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import auth
from database import (
    DOCUMENT_STATUS_VALUES,
    DatabaseError,
    DatabaseLockError,
    DatabaseManager,
    DatabaseUnavailableError,
    IntegrityConstraintError,
    parse_utc,
    utc_now,
    utc_now_text,
)


class XDTSServiceError(Exception):
    pass


class AuthenticationError(XDTSServiceError):
    pass


class AuthorizationError(XDTSServiceError):
    pass


class ValidationError(XDTSServiceError):
    pass


class ConflictError(XDTSServiceError):
    pass


class LeaseError(XDTSServiceError):
    pass


class NotFoundError(XDTSServiceError):
    pass


class AvailabilityError(XDTSServiceError):
    pass


@dataclass(frozen=True)
class SessionUser:
    id: int
    username: str
    role: str


class XDTSService:
    MAX_FAILED_ATTEMPTS = 5
    COOLDOWN_HOURS = 1
    LEASE_DURATION_SECONDS = 120

    def __init__(self, database: DatabaseManager, app_logger) -> None:
        self.database = database
        self.logger = app_logger
        self.workstation_name = socket.gethostname()
        self.ip_address = self._discover_ip_address()
        self.database.initialize()

    def authenticate(self, username: str, password: str) -> SessionUser:
        normalized_username = username.strip()
        if not normalized_username or not password:
            raise ValidationError("Username and password are required.")

        try:
            self.database.cleanup_expired_leases()
            user_row = self.database.fetch_one(
                "SELECT * FROM users WHERE username = ?",
                (normalized_username,),
            )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="authenticate.lookup",
                extra_context={"username": normalized_username},
            )

        if not user_row or not user_row["is_active"]:
            self._log_service_event(
                logging.WARNING,
                "authentication_failed",
                operation="authenticate.lookup",
                username=normalized_username,
            )
            raise AuthenticationError("Invalid username or password.")

        now = utc_now()
        cooldown_until = parse_utc(user_row["cooldown_until_utc"])
        if cooldown_until and cooldown_until > now:
            self._log_service_event(
                logging.WARNING,
                "authentication_locked_out",
                operation="authenticate.lookup",
                username=normalized_username,
                cooldown_until=user_row["cooldown_until_utc"],
            )
            raise AuthenticationError(
                f"Account locked until {user_row['cooldown_until_utc']}."
            )

        valid_password = auth.verify_password(
            password,
            expected_hash=user_row["password_hash"],
            salt=user_row["password_salt"],
            algorithm=user_row["password_algorithm"],
            iterations=user_row["password_iterations"],
        )
        if not valid_password:
            self._record_failed_login(user_row)
            raise AuthenticationError("Invalid username or password.")

        try:
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    UPDATE users
                    SET failed_attempts = 0, cooldown_until_utc = NULL
                    WHERE id = ?
                    """,
                    (user_row["id"],),
                )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="authenticate.reset_failures",
                extra_context={"username": normalized_username, "user_id": user_row["id"]},
            )

        self.logger.info("Successful login for username '%s'.", normalized_username)
        return SessionUser(
            id=user_row["id"],
            username=user_row["username"],
            role=user_row["role"],
        )

    def has_active_admin(self) -> bool:
        try:
            admin_row = self.database.fetch_one(
                """
                SELECT id
                FROM users
                WHERE role = 'admin' AND is_active = 1
                LIMIT 1
                """
            )
        except DatabaseError as exc:
            self._raise_database_error(exc, operation="has_active_admin")
        return admin_row is not None

    def initialize_admin(
        self,
        *,
        username: str,
        password: str,
    ) -> int:
        normalized_username = username.strip()
        if not normalized_username:
            raise ValidationError("Username is required.")
        if not password:
            raise ValidationError("Password is required.")
        try:
            with self.database.transaction() as connection:
                existing_admin = connection.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE role = 'admin' AND is_active = 1
                    LIMIT 1
                    """
                ).fetchone()
                if existing_admin:
                    raise ValidationError(
                        "An active admin account already exists. Initialization is not allowed."
                    )

                password_data = auth.hash_password(password)
                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        username,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        password_iterations,
                        role,
                        created_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, 'admin', ?)
                    """,
                    (
                        normalized_username,
                        password_data["password_hash"],
                        password_data["salt"],
                        password_data["algorithm"],
                        password_data["iterations"],
                        utc_now_text(),
                    ),
                )
        except IntegrityConstraintError as exc:
            raise self._translate_integrity_error(
                exc,
                duplicate_field="users.username",
                duplicate_message="Username already exists.",
            ) from exc
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="initialize_admin",
                extra_context={"username": normalized_username},
            )

        self.logger.warning(
            "Initial admin account '%s' created through explicit initialization.",
            normalized_username,
        )
        return int(cursor.lastrowid)

    def create_user(
        self,
        actor: SessionUser,
        *,
        username: str,
        password: str,
        role: str,
    ) -> int:
        self._require_role(actor, {"admin"})
        normalized_username = username.strip()
        if not normalized_username:
            raise ValidationError("Username is required.")
        if not password:
            raise ValidationError("Password is required.")
        if role not in {"admin", "operator", "viewer"}:
            raise ValidationError("Invalid role.")
        password_data = auth.hash_password(password)
        try:
            with self.database.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (
                        username,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        password_iterations,
                        role,
                        created_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_username,
                        password_data["password_hash"],
                        password_data["salt"],
                        password_data["algorithm"],
                        password_data["iterations"],
                        role,
                        utc_now_text(),
                    ),
                )
        except IntegrityConstraintError as exc:
            raise self._translate_integrity_error(
                exc,
                duplicate_field="users.username",
                duplicate_message="Username already exists.",
            ) from exc
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="create_user",
                actor=actor,
                extra_context={"target_username": normalized_username, "target_role": role},
            )
        self.logger.info("User '%s' created by '%s'.", normalized_username, actor.username)
        return int(cursor.lastrowid)

    def list_users(self, actor: SessionUser) -> list[dict[str, Any]]:
        self._require_role(actor, {"admin", "operator"})
        try:
            rows = self.database.fetch_all(
                """
                SELECT id, username, role
                FROM users
                WHERE is_active = 1
                ORDER BY username
                """
            )
        except DatabaseError as exc:
            self._raise_database_error(exc, operation="list_users", actor=actor)
        return [dict(row) for row in rows]

    def list_documents(self, actor: SessionUser) -> list[dict[str, Any]]:
        self._require_role(actor, {"admin", "operator", "viewer"})
        try:
            self.database.cleanup_expired_leases()
            rows = self.database.fetch_all(
                """
                SELECT
                    d.id,
                    d.document_number,
                    d.title,
                    d.description,
                    d.status,
                    d.last_state_version,
                    d.updated_at_utc,
                    holder.username AS current_holder_username,
                    lease_user.username AS lease_holder_username,
                    dl.workstation_name AS lease_workstation_name,
                    dl.expires_at_utc
                FROM documents d
                LEFT JOIN users holder ON holder.id = d.current_holder_user_id
                LEFT JOIN document_leases dl
                    ON dl.document_id = d.id
                    AND dl.expires_at_utc > ?
                LEFT JOIN users lease_user ON lease_user.id = dl.user_id
                ORDER BY d.document_number
                """,
                (utc_now_text(),),
            )
        except DatabaseError as exc:
            self._raise_database_error(exc, operation="list_documents", actor=actor)

        documents = []
        for row in rows:
            item = dict(row)
            lease_parts = []
            if item["lease_holder_username"]:
                lease_parts.append(item["lease_holder_username"])
            if item["lease_workstation_name"]:
                lease_parts.append(item["lease_workstation_name"])
            if item["expires_at_utc"]:
                lease_parts.append(f"until {item['expires_at_utc']}")
            item["lease_display"] = " | ".join(lease_parts)
            documents.append(item)
        return documents

    def register_document(
        self,
        actor: SessionUser,
        *,
        document_number: str,
        title: str,
        description: str,
        status: str,
        current_holder_user_id: int | None = None,
        reason: str = "Initial registration",
    ) -> int:
        self._require_role(actor, {"admin", "operator"})
        if not document_number.strip():
            raise ValidationError("Document number is required.")
        if not title.strip():
            raise ValidationError("Title is required.")
        if status not in DOCUMENT_STATUS_VALUES:
            raise ValidationError("Invalid document status.")

        holder_user_id = current_holder_user_id or actor.id
        if actor.role != "admin" and holder_user_id != actor.id:
            raise ValidationError("Only admins can assign a document to another user.")
        created_at_utc = utc_now_text()
        try:
            with self.database.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO documents (
                        document_number,
                        title,
                        description,
                        status,
                        current_holder_user_id,
                        created_by_user_id,
                        last_state_version,
                        created_at_utc,
                        updated_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        document_number.strip(),
                        title.strip(),
                        description.strip(),
                        status,
                        holder_user_id,
                        actor.id,
                        created_at_utc,
                        created_at_utc,
                    ),
                )
                document_id = int(cursor.lastrowid)
                new_state = {
                    "document_number": document_number.strip(),
                    "title": title.strip(),
                    "description": description.strip(),
                    "status": status,
                    "current_holder_user_id": holder_user_id,
                    "last_state_version": 1,
                }
                self.database.append_history(
                    connection,
                    document_id=document_id,
                    actor_user_id=actor.id,
                    action_type="DOCUMENT_REGISTERED",
                    previous_state=None,
                    new_state=new_state,
                    state_version=1,
                    workstation_name=self.workstation_name,
                    ip_address=self.ip_address,
                    reason=reason,
                )
        except IntegrityConstraintError as exc:
            raise self._translate_integrity_error(
                exc,
                duplicate_field="documents.document_number",
                duplicate_message="Document number already exists.",
            ) from exc
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="register_document",
                actor=actor,
                extra_context={"document_number": document_number.strip()},
            )

        self.logger.info(
            "Document '%s' registered by '%s'.",
            document_number.strip(),
            actor.username,
        )
        return document_id

    def acquire_lease(self, actor: SessionUser, document_id: int) -> str:
        self._require_role(actor, {"admin", "operator"})
        now = utc_now()
        expires_at = (now + timedelta(seconds=self.LEASE_DURATION_SECONDS)).replace(
            microsecond=0
        )
        now_text = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        expires_text = expires_at.isoformat().replace("+00:00", "Z")
        try:
            with self.database.transaction() as connection:
                self.database.cleanup_expired_leases(connection=connection)
                document_row = connection.execute(
                    "SELECT id FROM documents WHERE id = ?",
                    (document_id,),
                ).fetchone()
                if not document_row:
                    raise NotFoundError("Document not found.")

                existing_lease = connection.execute(
                    """
                    SELECT dl.*, u.username
                    FROM document_leases dl
                    JOIN users u ON u.id = dl.user_id
                    WHERE dl.document_id = ? AND dl.expires_at_utc > ?
                    """,
                    (document_id, utc_now_text()),
                ).fetchone()
                if existing_lease and (
                    existing_lease["user_id"] != actor.id
                    or existing_lease["workstation_name"] != self.workstation_name
                ):
                    self._raise_lease_error(
                        "Document is currently leased by "
                        f"{existing_lease['username']} on {existing_lease['workstation_name']} "
                        f"until {existing_lease['expires_at_utc']}.",
                        operation="acquire_lease",
                        actor=actor,
                        document_id=document_id,
                        extra_context={
                            "leased_by": existing_lease["username"],
                            "lease_workstation": existing_lease["workstation_name"],
                            "lease_expires": existing_lease["expires_at_utc"],
                        },
                    )

                connection.execute(
                    """
                    INSERT INTO document_leases (
                        document_id,
                        user_id,
                        workstation_name,
                        lease_start_utc,
                        expires_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(document_id) DO UPDATE SET
                        user_id = excluded.user_id,
                        workstation_name = excluded.workstation_name,
                        lease_start_utc = excluded.lease_start_utc,
                        expires_at_utc = excluded.expires_at_utc
                    """,
                    (
                        document_id,
                        actor.id,
                        self.workstation_name,
                        now_text,
                        expires_text,
                    ),
                )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="acquire_lease",
                actor=actor,
                document_id=document_id,
            )

        self.logger.info(
            "Lease acquired for document_id=%s by '%s' until %s.",
            document_id,
            actor.username,
            expires_text,
        )
        return expires_text

    def release_lease(self, actor: SessionUser, document_id: int) -> None:
        self._require_role(actor, {"admin", "operator"})
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    DELETE FROM document_leases
                    WHERE document_id = ?
                      AND user_id = ?
                      AND workstation_name = ?
                    """,
                    (document_id, actor.id, self.workstation_name),
                )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="release_lease",
                actor=actor,
                document_id=document_id,
            )

    def transfer_document(
        self,
        actor: SessionUser,
        *,
        document_id: int,
        new_holder_user_id: int,
        expected_version: int,
        reason: str,
        new_status: str | None = None,
    ) -> None:
        self._require_role(actor, {"admin", "operator"})
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValidationError("Transfer reason is required.")
        if new_status and new_status not in DOCUMENT_STATUS_VALUES:
            raise ValidationError("Invalid document status.")

        try:
            with self.database.transaction() as connection:
                self.database.cleanup_expired_leases(connection=connection)
                document_row = connection.execute(
                    "SELECT * FROM documents WHERE id = ?",
                    (document_id,),
                ).fetchone()
                if not document_row:
                    raise NotFoundError("Document not found.")
                if document_row["last_state_version"] != expected_version:
                    self._raise_conflict_error(
                        "Document changed since it was loaded. Refresh and retry."
                        ,
                        operation="transfer_document",
                        actor=actor,
                        document_id=document_id,
                        extra_context={
                            "expected_version": expected_version,
                            "actual_version": document_row["last_state_version"],
                        },
                    )

                holder_row = connection.execute(
                    "SELECT id FROM users WHERE id = ? AND is_active = 1",
                    (new_holder_user_id,),
                ).fetchone()
                if not holder_row:
                    raise ValidationError("Selected holder is not available.")

                active_lease = connection.execute(
                    """
                    SELECT dl.*, u.username
                    FROM document_leases dl
                    JOIN users u ON u.id = dl.user_id
                    WHERE dl.document_id = ? AND dl.expires_at_utc > ?
                    """,
                    (document_id, utc_now_text()),
                ).fetchone()
                if not active_lease:
                    self._raise_lease_error(
                        "Document lease expired. Reopen transfer and retry.",
                        operation="transfer_document",
                        actor=actor,
                        document_id=document_id,
                        extra_context={"expected_version": expected_version},
                    )
                if (
                    active_lease["user_id"] != actor.id
                    or active_lease["workstation_name"] != self.workstation_name
                ):
                    self._raise_lease_error(
                        "Document is currently leased by "
                        f"{active_lease['username']} on {active_lease['workstation_name']}.",
                        operation="transfer_document",
                        actor=actor,
                        document_id=document_id,
                        extra_context={
                            "leased_by": active_lease["username"],
                            "lease_workstation": active_lease["workstation_name"],
                        },
                    )

                updated_status = new_status or document_row["status"]
                new_version = document_row["last_state_version"] + 1
                updated_at_utc = utc_now_text()
                previous_state = {
                    "document_number": document_row["document_number"],
                    "title": document_row["title"],
                    "description": document_row["description"],
                    "status": document_row["status"],
                    "current_holder_user_id": document_row["current_holder_user_id"],
                    "last_state_version": document_row["last_state_version"],
                }
                new_state = {
                    "document_number": document_row["document_number"],
                    "title": document_row["title"],
                    "description": document_row["description"],
                    "status": updated_status,
                    "current_holder_user_id": new_holder_user_id,
                    "last_state_version": new_version,
                }
                connection.execute(
                    """
                    UPDATE documents
                    SET current_holder_user_id = ?,
                        status = ?,
                        last_state_version = ?,
                        updated_at_utc = ?
                    WHERE id = ?
                    """,
                    (
                        new_holder_user_id,
                        updated_status,
                        new_version,
                        updated_at_utc,
                        document_id,
                    ),
                )
                self.database.append_history(
                    connection,
                    document_id=document_id,
                    actor_user_id=actor.id,
                    action_type="DOCUMENT_TRANSFERRED",
                    previous_state=previous_state,
                    new_state=new_state,
                    state_version=new_version,
                    workstation_name=self.workstation_name,
                    ip_address=self.ip_address,
                    reason=normalized_reason,
                )
                connection.execute(
                    "DELETE FROM document_leases WHERE document_id = ?",
                    (document_id,),
                )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="transfer_document",
                actor=actor,
                document_id=document_id,
                extra_context={
                    "new_holder_user_id": new_holder_user_id,
                    "expected_version": expected_version,
                },
            )

        self.logger.info(
            "Document id=%s transferred by '%s' to user_id=%s.",
            document_id,
            actor.username,
            new_holder_user_id,
        )

    def get_document_history(self, actor: SessionUser, document_id: int) -> list[dict[str, Any]]:
        self._require_role(actor, {"admin", "operator", "viewer"})
        try:
            rows = self.database.fetch_all(
                """
                SELECT
                    h.id,
                    h.created_at_utc,
                    h.action_type,
                    h.reason,
                    h.state_version,
                    h.workstation_name,
                    h.ip_address,
                    u.username AS actor_username
                FROM history h
                JOIN users u ON u.id = h.actor_user_id
                WHERE h.document_id = ?
                ORDER BY h.id
                """,
                (document_id,),
            )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="get_document_history",
                actor=actor,
                document_id=document_id,
            )
        return [dict(row) for row in rows]

    def verify_audit_chain(self, actor: SessionUser) -> str:
        self._require_role(actor, {"admin"})
        try:
            result = self.database.verify_audit_chain()
        except DatabaseError as exc:
            self._raise_database_error(exc, operation="verify_audit_chain", actor=actor)
        if result.ok:
            self._log_service_event(
                logging.INFO,
                "audit_verification_passed",
                operation="verify_audit_chain",
                actor=actor.username,
                actor_id=actor.id,
                checked_rows=result.checked_rows,
            )
            return result.message
        self._log_service_event(
            logging.WARNING,
            "audit_verification_failed",
            operation="verify_audit_chain",
            actor=actor.username,
            actor_id=actor.id,
            broken_history_id=result.broken_history_id,
            checked_rows=result.checked_rows,
        )
        raise ConflictError(
            f"{result.message} First broken history row: {result.broken_history_id}."
        )

    def backup_database(self, actor: SessionUser) -> str:
        self._require_role(actor, {"admin"})
        try:
            backup_path = self.database.backup_database()
        except DatabaseError as exc:
            self._raise_database_error(exc, operation="backup_database", actor=actor)
        self._log_service_event(
            logging.INFO,
            "backup_created",
            operation="backup_database",
            actor=actor.username,
            actor_id=actor.id,
            backup_path=str(backup_path),
        )
        return str(backup_path)

    def reset_user_password(
        self,
        actor: SessionUser,
        *,
        target_user_id: int,
        new_password: str,
    ) -> None:
        self._require_role(actor, {"admin"})
        if not new_password:
            raise ValidationError("Password is required.")

        password_data = auth.hash_password(new_password)
        try:
            with self.database.transaction() as connection:
                target_user = connection.execute(
                    """
                    SELECT id, username
                    FROM users
                    WHERE id = ? AND is_active = 1
                    """,
                    (target_user_id,),
                ).fetchone()
                if not target_user:
                    raise NotFoundError("User not found.")

                connection.execute(
                    """
                    UPDATE users
                    SET password_hash = ?,
                        password_salt = ?,
                        password_algorithm = ?,
                        password_iterations = ?,
                        failed_attempts = 0,
                        cooldown_until_utc = NULL
                    WHERE id = ?
                    """,
                    (
                        password_data["password_hash"],
                        password_data["salt"],
                        password_data["algorithm"],
                        password_data["iterations"],
                        target_user_id,
                    ),
                )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="reset_user_password",
                actor=actor,
                extra_context={"target_user_id": target_user_id},
            )

        self.logger.info(
            "Password reset for user_id=%s by '%s'.",
            target_user_id,
            actor.username,
        )

    def get_system_report(self, actor: SessionUser) -> dict[str, Any]:
        self._require_role(actor, {"admin"})
        try:
            with self.database.read_transaction() as connection:
                snapshot_time = utc_now_text()
                document_total_row = connection.execute(
                    "SELECT COUNT(*) AS count FROM documents"
                ).fetchone()
                user_total_row = connection.execute(
                    "SELECT COUNT(*) AS count FROM users WHERE is_active = 1"
                ).fetchone()
                active_lease_row = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM document_leases
                    WHERE expires_at_utc > ?
                    """,
                    (snapshot_time,),
                ).fetchone()
                status_rows = connection.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM documents
                    GROUP BY status
                    ORDER BY status
                    """
                ).fetchall()
                role_rows = connection.execute(
                    """
                    SELECT role, COUNT(*) AS count
                    FROM users
                    WHERE is_active = 1
                    GROUP BY role
                    ORDER BY role
                    """
                ).fetchall()
                activity_rows = connection.execute(
                    """
                    SELECT action_type, COUNT(*) AS count
                    FROM history
                    GROUP BY action_type
                    ORDER BY action_type
                    """
                ).fetchall()
        except DatabaseError as exc:
            self._raise_database_error(exc, operation="get_system_report", actor=actor)

        return {
            "document_total": int(document_total_row["count"]) if document_total_row else 0,
            "active_user_total": int(user_total_row["count"]) if user_total_row else 0,
            "active_lease_total": int(active_lease_row["count"]) if active_lease_row else 0,
            "documents_by_status": [
                {"status": row["status"], "count": int(row["count"])} for row in status_rows
            ],
            "users_by_role": [
                {"role": row["role"], "count": int(row["count"])} for row in role_rows
            ],
            "history_by_action": [
                {"action_type": row["action_type"], "count": int(row["count"])}
                for row in activity_rows
            ],
        }

    def get_recent_log_lines(self, actor: SessionUser, *, limit: int = 200) -> list[str]:
        self._require_role(actor, {"admin"})
        log_path = self._get_log_path()
        if log_path is None or not log_path.exists():
            return []

        for handler in self.logger.handlers:
            flush = getattr(handler, "flush", None)
            if callable(flush):
                flush()
        lines = log_path.read_text(encoding="utf-8").splitlines()
        if limit <= 0:
            return lines
        return lines[-limit:]

    def _record_failed_login(self, user_row: sqlite3.Row) -> None:
        failed_attempts = int(user_row["failed_attempts"]) + 1
        cooldown_until = None
        if failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            failed_attempts = self.MAX_FAILED_ATTEMPTS
            cooldown_until = (
                utc_now() + timedelta(hours=self.COOLDOWN_HOURS)
            ).replace(microsecond=0)
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    """
                    UPDATE users
                    SET failed_attempts = ?, cooldown_until_utc = ?
                    WHERE id = ?
                    """,
                    (
                        failed_attempts,
                        cooldown_until.isoformat().replace("+00:00", "Z")
                        if cooldown_until
                        else None,
                        user_row["id"],
                    ),
                )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="record_failed_login",
                extra_context={"username": user_row["username"], "user_id": user_row["id"]},
            )
        if cooldown_until:
            self.logger.warning(
                "User '%s' locked out until %s after failed logins.",
                user_row["username"],
                cooldown_until.isoformat().replace("+00:00", "Z"),
            )
        else:
            self.logger.warning(
                "Failed login for username '%s'. Attempts=%s.",
                user_row["username"],
                failed_attempts,
            )

    def _require_role(self, actor: SessionUser, allowed_roles: set[str]) -> None:
        current_user = self._get_active_user(actor.id)
        if current_user is None:
            raise AuthorizationError("Your account is no longer active.")
        if current_user["role"] not in allowed_roles:
            raise AuthorizationError("You do not have permission for this action.")

    def _get_active_user(self, user_id: int) -> sqlite3.Row | None:
        try:
            return self.database.fetch_one(
                """
                SELECT id, username, role, is_active
                FROM users
                WHERE id = ? AND is_active = 1
                """,
                (user_id,),
            )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="get_active_user",
                extra_context={"user_id": user_id},
            )

    def _translate_database_error(self, exc: DatabaseError) -> XDTSServiceError:
        if isinstance(exc, DatabaseLockError):
            return AvailabilityError(str(exc))
        if isinstance(exc, DatabaseUnavailableError):
            return AvailabilityError(str(exc))
        return XDTSServiceError("Database operation failed.")

    def _translate_integrity_error(
        self,
        exc: IntegrityConstraintError,
        *,
        duplicate_field: str,
        duplicate_message: str,
    ) -> ValidationError:
        message = str(exc).lower()
        if duplicate_field.lower() in message:
            return ValidationError(duplicate_message)
        return ValidationError("Request violates a database constraint.")

    def _discover_ip_address(self) -> str:
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except OSError:
            return ""

    def _get_log_path(self) -> Path | None:
        for handler in self.logger.handlers:
            base_filename = getattr(handler, "baseFilename", None)
            if base_filename:
                return Path(base_filename)
        return None

    def _raise_database_error(
        self,
        exc: DatabaseError,
        *,
        operation: str,
        actor: SessionUser | None = None,
        document_id: int | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        translated = self._translate_database_error(exc)
        event_name = "database_operation_failed"
        if isinstance(exc, DatabaseLockError):
            event_name = "database_lock_failure"
        elif isinstance(exc, DatabaseUnavailableError):
            event_name = "database_unavailable"
        self._log_service_event(
            logging.ERROR,
            event_name,
            operation=operation,
            actor=actor.username if actor else None,
            actor_id=actor.id if actor else None,
            document_id=document_id,
            error_type=type(exc).__name__,
            user_message=str(translated),
            **(extra_context or {}),
        )
        raise translated from exc

    def _raise_lease_error(
        self,
        message: str,
        *,
        operation: str,
        actor: SessionUser | None = None,
        document_id: int | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        self._log_service_event(
            logging.WARNING,
            "lease_conflict",
            operation=operation,
            actor=actor.username if actor else None,
            actor_id=actor.id if actor else None,
            document_id=document_id,
            detail=message,
            **(extra_context or {}),
        )
        raise LeaseError(message)

    def _raise_conflict_error(
        self,
        message: str,
        *,
        operation: str,
        actor: SessionUser | None = None,
        document_id: int | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        self._log_service_event(
            logging.WARNING,
            "state_conflict",
            operation=operation,
            actor=actor.username if actor else None,
            actor_id=actor.id if actor else None,
            document_id=document_id,
            detail=message,
            **(extra_context or {}),
        )
        raise ConflictError(message)

    def _log_service_event(self, level: int, event: str, **context: Any) -> None:
        normalized_context = {
            key: value
            for key, value in context.items()
            if value is not None and value != ""
        }
        normalized_context.setdefault("workstation", self.workstation_name)
        parts = [event]
        for key in sorted(normalized_context):
            parts.append(f"{key}={normalized_context[key]}")
        self.logger.log(level, " ".join(parts))
