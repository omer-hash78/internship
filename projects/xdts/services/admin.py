from __future__ import annotations

from core import auth

from core.database import DatabaseError, IntegrityConstraintError, utc_now_text

from .models import UserSummary
from .support import NotFoundError, ValidationError


class AdminServiceMixin:
    def create_user(
        self,
        actor,
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

    def list_users(self, actor) -> list[UserSummary]:
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
        return [
            UserSummary(id=int(row["id"]), username=row["username"], role=row["role"])
            for row in rows
        ]

    def reset_user_password(
        self,
        actor,
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

    def deactivate_user(self, actor, *, target_user_id: int) -> None:
        self._require_role(actor, {"admin"})
        if target_user_id == actor.id:
            raise ValidationError("You cannot deactivate your own account.")

        try:
            with self.database.transaction() as connection:
                target_user = connection.execute(
                    """
                    SELECT id, username, role
                    FROM users
                    WHERE id = ? AND is_active = 1
                    """,
                    (target_user_id,),
                ).fetchone()
                if not target_user:
                    raise NotFoundError("User not found.")

                if target_user["role"] == "admin":
                    active_admin_count = connection.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM users
                        WHERE role = 'admin' AND is_active = 1
                        """
                    ).fetchone()
                    if active_admin_count and int(active_admin_count["count"]) <= 1:
                        raise ValidationError("At least one active admin account must remain.")

                connection.execute(
                    """
                    UPDATE users
                    SET is_active = 0
                    WHERE id = ?
                    """,
                    (target_user_id,),
                )
                connection.execute(
                    "DELETE FROM document_leases WHERE user_id = ?",
                    (target_user_id,),
                )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="deactivate_user",
                actor=actor,
                extra_context={"target_user_id": target_user_id},
            )

        self.logger.info(
            "User id=%s deactivated by '%s'.",
            target_user_id,
            actor.username,
        )
