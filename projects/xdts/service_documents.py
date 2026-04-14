from __future__ import annotations

from datetime import timedelta

from database import DOCUMENT_STATUS_VALUES, DatabaseError, IntegrityConstraintError, utc_now, utc_now_text
from service_models import DocumentHistoryItem, DocumentListItem, UserSummary
from service_support import AuthorizationError, LeaseError, NotFoundError, ValidationError


class DocumentServiceMixin:
    def list_document_holders(self, actor) -> list[UserSummary]:
        self._require_role(actor, {"admin", "operator", "viewer"})
        try:
            rows = self.database.fetch_all(
                """
                SELECT DISTINCT u.id, u.username, u.role
                FROM documents d
                JOIN users u ON u.id = d.current_holder_user_id
                WHERE u.is_active = 1
                ORDER BY u.username
                """
            )
        except DatabaseError as exc:
            self._raise_database_error(exc, operation="list_document_holders", actor=actor)
        return [
            UserSummary(id=int(row["id"]), username=row["username"], role=row["role"])
            for row in rows
        ]

    def list_documents(
        self,
        actor,
        *,
        status: str | None = None,
        holder_user_id: int | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocumentListItem]:
        self._require_role(actor, {"admin", "operator", "viewer"})
        normalized_status = status.strip() if status else None
        if normalized_status and normalized_status not in DOCUMENT_STATUS_VALUES:
            raise ValidationError("Invalid document status filter.")
        normalized_query = query.strip() if query else None
        normalized_limit = max(1, min(limit, 500))
        normalized_offset = max(0, offset)
        snapshot_time = utc_now_text()
        conditions: list[str] = []
        params: list[object] = [snapshot_time]
        if normalized_status:
            conditions.append("d.status = ?")
            params.append(normalized_status)
        if holder_user_id is not None:
            conditions.append("d.current_holder_user_id = ?")
            params.append(holder_user_id)
        if normalized_query:
            conditions.append(
                """
                (
                    d.document_number LIKE ?
                    OR d.title LIKE ?
                    OR holder.username LIKE ?
                )
                """
            )
            wildcard = f"%{normalized_query}%"
            params.extend([wildcard, wildcard, wildcard])

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        try:
            with self.database.read_transaction() as connection:
                rows = connection.execute(
                    f"""
                    SELECT
                        d.id,
                        d.document_number,
                        d.title,
                        d.description,
                        d.status,
                        d.last_state_version,
                        d.updated_at_utc,
                        d.current_holder_user_id,
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
                    {where_clause}
                    ORDER BY d.document_number
                    LIMIT ? OFFSET ?
                    """,
                    tuple(params + [normalized_limit, normalized_offset]),
                ).fetchall()
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
            documents.append(
                DocumentListItem(
                    id=int(item["id"]),
                    document_number=item["document_number"],
                    title=item["title"],
                    description=item["description"],
                    status=item["status"],
                    last_state_version=int(item["last_state_version"]),
                    updated_at_utc=item["updated_at_utc"],
                    current_holder_username=item["current_holder_username"] or "",
                    current_holder_user_id=item["current_holder_user_id"],
                    lease_holder_username=item["lease_holder_username"] or "",
                    lease_workstation_name=item["lease_workstation_name"] or "",
                    expires_at_utc=item["expires_at_utc"] or "",
                    lease_display=" | ".join(lease_parts),
                )
            )
        return documents

    def register_document(
        self,
        actor,
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

    def acquire_lease(self, actor, document_id: int) -> str:
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

    def release_lease(self, actor, document_id: int) -> None:
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
        actor,
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
                actor_row = connection.execute(
                    "SELECT role FROM users WHERE id = ? AND is_active = 1",
                    (actor.id,),
                ).fetchone()
                document_row = connection.execute(
                    "SELECT * FROM documents WHERE id = ?",
                    (document_id,),
                ).fetchone()
                if not document_row:
                    raise NotFoundError("Document not found.")
                if (
                    actor_row
                    and actor_row["role"] != "admin"
                    and document_row["current_holder_user_id"] != actor.id
                ):
                    raise AuthorizationError(
                        "Only admins can transfer documents they do not currently hold."
                    )
                if document_row["last_state_version"] != expected_version:
                    self._raise_conflict_error(
                        "Document changed since it was loaded. Refresh and retry.",
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

    def get_document_history(
        self,
        actor,
        document_id: int,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[DocumentHistoryItem]:
        self._require_role(actor, {"admin", "operator", "viewer"})
        normalized_limit = max(1, min(limit, 500))
        normalized_offset = max(0, offset)
        try:
            rows = self.database.fetch_all(
                """
                SELECT
                    h.id,
                    h.created_at_utc,
                    h.action_type,
                    h.reason,
                    h.state_version,
                    h.previous_state,
                    h.new_state,
                    h.workstation_name,
                    h.ip_address,
                    u.username AS actor_username
                FROM history h
                JOIN users u ON u.id = h.actor_user_id
                WHERE h.document_id = ?
                ORDER BY h.id DESC
                LIMIT ? OFFSET ?
                """,
                (document_id, normalized_limit, normalized_offset),
            )
        except DatabaseError as exc:
            self._raise_database_error(
                exc,
                operation="get_document_history",
                actor=actor,
                document_id=document_id,
            )
        prepared_rows = []
        holder_user_ids: set[int] = set()
        for row in rows:
            item = dict(row)
            previous_state = self._deserialize_state(item.pop("previous_state", ""))
            new_state = self._deserialize_state(item.pop("new_state", ""))
            for holder_user_id in (
                previous_state.get("current_holder_user_id"),
                new_state.get("current_holder_user_id"),
            ):
                if isinstance(holder_user_id, int):
                    holder_user_ids.add(holder_user_id)
            prepared_rows.append((item, previous_state, new_state))

        holder_usernames: dict[int, str] = {}
        if holder_user_ids:
            try:
                placeholders = ", ".join("?" for _ in holder_user_ids)
                holder_rows = self.database.fetch_all(
                    f"SELECT id, username FROM users WHERE id IN ({placeholders})",
                    tuple(sorted(holder_user_ids)),
                )
            except DatabaseError as exc:
                self._raise_database_error(
                    exc,
                    operation="get_document_history.resolve_holders",
                    actor=actor,
                    document_id=document_id,
                )
            holder_usernames = {int(row["id"]): row["username"] for row in holder_rows}

        history_rows = []
        for item, previous_state, new_state in reversed(prepared_rows):
            previous_holder_id = previous_state.get("current_holder_user_id")
            new_holder_id = new_state.get("current_holder_user_id")
            previous_holder = self._format_holder_name(holder_usernames, previous_holder_id)
            new_holder = self._format_holder_name(holder_usernames, new_holder_id)
            if previous_holder and new_holder and previous_holder != new_holder:
                action_display = f"{item['action_type']} ({previous_holder} -> {new_holder})"
            else:
                action_display = item["action_type"]
            history_rows.append(
                DocumentHistoryItem(
                    id=int(item["id"]),
                    created_at_utc=item["created_at_utc"],
                    action_type=item["action_type"],
                    action_display=action_display,
                    reason=item["reason"] or "",
                    state_version=int(item["state_version"]),
                    workstation_name=item["workstation_name"],
                    ip_address=item["ip_address"] or "",
                    actor_username=item["actor_username"],
                )
            )
        return history_rows
