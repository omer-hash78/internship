from __future__ import annotations

import logging

from core.database import DatabaseError, utc_now_text

from .models import CountSummary, SystemReport
from .support import ConflictError


class ReportingServiceMixin:
    def verify_audit_chain(self, actor) -> str:
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

    def backup_database(self, actor) -> str:
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

    def get_system_report(self, actor) -> SystemReport:
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

        return SystemReport(
            document_total=int(document_total_row["count"]) if document_total_row else 0,
            active_user_total=int(user_total_row["count"]) if user_total_row else 0,
            active_lease_total=int(active_lease_row["count"]) if active_lease_row else 0,
            documents_by_status=[
                CountSummary(label=row["status"], count=int(row["count"])) for row in status_rows
            ],
            users_by_role=[
                CountSummary(label=row["role"], count=int(row["count"])) for row in role_rows
            ],
            history_by_action=[
                CountSummary(label=row["action_type"], count=int(row["count"]))
                for row in activity_rows
            ],
        )

    def get_recent_log_lines(self, actor, *, limit: int = 200) -> list[str]:
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
