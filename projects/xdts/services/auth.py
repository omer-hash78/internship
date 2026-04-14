from __future__ import annotations

import logging

from core import auth

from core.database import (
    DatabaseError,
    IntegrityConstraintError,
    parse_utc,
    utc_now,
    utc_now_text,
)

from .models import SessionUser
from .support import AuthenticationError, ValidationError


class AuthServiceMixin:
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
