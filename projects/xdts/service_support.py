from __future__ import annotations

import json
import logging
import socket
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

from database import (
    DatabaseError,
    DatabaseLockError,
    DatabaseUnavailableError,
    IntegrityConstraintError,
    utc_now,
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


class ServiceSupport:
    MAX_FAILED_ATTEMPTS = 5
    COOLDOWN_HOURS = 1
    LEASE_DURATION_SECONDS = 120

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

    def _require_role(self, actor, allowed_roles: set[str]) -> None:
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
        if isinstance(exc, (DatabaseLockError, DatabaseUnavailableError)):
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
        if not getattr(self, "config", None) or not self.config.capture_ip:
            return ""
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

    def _deserialize_state(self, value: str) -> dict[str, Any]:
        if not value:
            return {}
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
        return {}

    def _format_holder_name(
        self, holder_usernames: dict[int, str], holder_user_id: Any
    ) -> str:
        if not isinstance(holder_user_id, int):
            return ""
        return holder_usernames.get(holder_user_id, f"user_id={holder_user_id}")

    def _raise_database_error(
        self,
        exc: DatabaseError,
        *,
        operation: str,
        actor=None,
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
        actor=None,
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
        actor=None,
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
