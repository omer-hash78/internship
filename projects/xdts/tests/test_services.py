from __future__ import annotations

import sys
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import RuntimeConfig
from database import (
    AUDIT_HASH_VERSION_CURRENT,
    AUDIT_HASH_VERSION_LEGACY,
    DatabaseManager,
    DatabaseUnavailableError,
    utc_now,
    compute_history_record_hash_v1,
    serialize_state,
    utc_now_text,
)
from logger import build_application_logger
from services import (
    AuthenticationError,
    AuthorizationError,
    AvailabilityError,
    ConflictError,
    LeaseError,
    ValidationError,
    XDTSService,
)


class XDTSServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_root = PROJECT_ROOT / ".test-work" / uuid.uuid4().hex
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.test_root / "logs" / "xdts.log"
        self.logger = build_application_logger(
            self.test_root / "logs",
            name=f"xdts.test.{uuid.uuid4().hex}",
        )
        self.database = DatabaseManager(
            self.test_root / "xdts.db",
            self.test_root / "backups",
            self.logger,
        )
        self.service = XDTSService(self.database, self.logger)

    def tearDown(self) -> None:
        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)
        shutil.rmtree(self.test_root, ignore_errors=True)

    def initialize_admin(self) -> None:
        self.service.initialize_admin(username="admin", password="ChangeMe123!")

    def flush_logs(self) -> str:
        for handler in self.logger.handlers:
            handler.flush()
        if not self.log_path.exists():
            return ""
        return self.log_path.read_text(encoding="utf-8")

    def test_explicit_admin_initialization_can_authenticate(self) -> None:
        self.initialize_admin()
        session = self.service.authenticate("admin", "ChangeMe123!")
        self.assertEqual(session.username, "admin")
        self.assertEqual(session.role, "admin")

    def test_register_and_transfer_document_updates_history(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        operator_id = self.service.create_user(
            admin,
            username="operator1",
            password="Operator123!",
            role="operator",
        )
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-001",
            title="Transfer Procedure",
            description="Test document",
            status="REGISTERED",
        )

        self.service.acquire_lease(admin, document_id)
        self.service.transfer_document(
            admin,
            document_id=document_id,
            new_holder_user_id=operator_id,
            expected_version=1,
            reason="Handing off for review.",
            new_status="IN_REVIEW",
        )

        documents = self.service.list_documents(admin)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["last_state_version"], 2)
        self.assertEqual(documents[0]["status"], "IN_REVIEW")

        history_rows = self.service.get_document_history(admin, document_id)
        self.assertEqual(len(history_rows), 2)
        self.assertEqual(history_rows[-1]["action_type"], "DOCUMENT_TRANSFERRED")
        self.assertEqual(
            history_rows[-1]["action_display"],
            "DOCUMENT_TRANSFERRED (admin -> operator1)",
        )
        self.assertEqual(
            self.service.verify_audit_chain(admin),
            "Audit chain verified successfully.",
        )

    def test_role_change_is_enforced_against_persisted_state(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")

        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE users SET role = 'viewer' WHERE id = ?",
                (admin.id,),
            )

        with self.assertRaises(AuthorizationError):
            self.service.create_user(
                admin,
                username="blocked",
                password="Blocked123!",
                role="viewer",
            )

    def test_duplicate_username_returns_validation_error(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="duplicate-user",
            password="Password123!",
            role="viewer",
        )

        with self.assertRaises(ValidationError) as context:
            self.service.create_user(
                admin,
                username="duplicate-user",
                password="Password123!",
                role="viewer",
            )

        self.assertEqual(str(context.exception), "Username already exists.")

    def test_create_user_requires_password(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")

        with self.assertRaises(ValidationError) as context:
            self.service.create_user(
                admin,
                username="no-password-user",
                password="",
                role="viewer",
            )

        self.assertEqual(str(context.exception), "Password is required.")

    def test_admin_can_reset_user_password(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        viewer_id = self.service.create_user(
            admin,
            username="reset-user",
            password="Original123!",
            role="viewer",
        )

        self.service.reset_user_password(
            admin,
            target_user_id=viewer_id,
            new_password="Updated123!",
        )

        with self.assertRaises(AuthenticationError):
            self.service.authenticate("reset-user", "Original123!")

        reset_user = self.service.authenticate("reset-user", "Updated123!")
        self.assertEqual(reset_user.username, "reset-user")

    def test_admin_can_deactivate_user(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="deactivate-user",
            password="Viewer123!",
            role="viewer",
        )
        target_user = self.service.authenticate("deactivate-user", "Viewer123!")

        self.service.deactivate_user(admin, target_user_id=target_user.id)

        listed_users = self.service.list_users(admin)
        self.assertFalse(any(user["username"] == "deactivate-user" for user in listed_users))
        with self.assertRaises(AuthenticationError):
            self.service.authenticate("deactivate-user", "Viewer123!")

    def test_admin_cannot_deactivate_own_account(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")

        with self.assertRaises(ValidationError) as context:
            self.service.deactivate_user(admin, target_user_id=admin.id)

        self.assertEqual(str(context.exception), "You cannot deactivate your own account.")

    def test_admin_can_deactivate_another_admin(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        second_admin_id = self.service.create_user(
            admin,
            username="second-admin",
            password="Admin123!",
            role="admin",
        )
        self.service.authenticate("second-admin", "Admin123!")

        self.service.deactivate_user(admin, target_user_id=second_admin_id)

        listed_users = self.service.list_users(admin)
        self.assertFalse(any(user["username"] == "second-admin" for user in listed_users))
        with self.assertRaises(AuthenticationError):
            self.service.authenticate("second-admin", "Admin123!")

    def test_duplicate_document_number_returns_validation_error(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.register_document(
            admin,
            document_number="XDTS-DUP-001",
            title="First",
            description="Original",
            status="REGISTERED",
        )

        with self.assertRaises(ValidationError) as context:
            self.service.register_document(
                admin,
                document_number="XDTS-DUP-001",
                title="Second",
                description="Duplicate",
                status="REGISTERED",
            )

        self.assertEqual(str(context.exception), "Document number already exists.")

    def test_list_documents_does_not_cleanup_expired_leases_on_refresh(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-LEASE-READ-001",
            title="Read Only Listing",
            description="Expired leases should remain until cleanup points.",
            status="REGISTERED",
        )

        expired_at = utc_now().replace(year=2020).isoformat()
        with self.database.transaction() as connection:
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
                """,
                (
                    document_id,
                    admin.id,
                    "WORKSTATION-1",
                    "2020-01-01T00:00:00+03:00",
                    expired_at,
                ),
            )

        self.service.list_documents(admin)

        lease_row = self.database.fetch_one(
            "SELECT id FROM document_leases WHERE document_id = ?",
            (document_id,),
        )
        self.assertIsNotNone(lease_row)

    def test_list_documents_supports_filters_and_paging(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        operator_id = self.service.create_user(
            admin,
            username="filter-operator",
            password="Operator123!",
            role="operator",
        )
        viewer_id = self.service.create_user(
            admin,
            username="filter-viewer",
            password="Viewer123!",
            role="viewer",
        )
        self.service.register_document(
            admin,
            document_number="XDTS-FILTER-001",
            title="Operator Owned",
            description="Filter target one",
            status="REGISTERED",
            current_holder_user_id=operator_id,
        )
        self.service.register_document(
            admin,
            document_number="XDTS-FILTER-002",
            title="Viewer Review",
            description="Filter target two",
            status="IN_REVIEW",
            current_holder_user_id=viewer_id,
        )
        self.service.register_document(
            admin,
            document_number="XDTS-FILTER-003",
            title="Viewer Archive",
            description="Filter target three",
            status="ARCHIVED",
            current_holder_user_id=viewer_id,
        )

        status_filtered = self.service.list_documents(admin, status="IN_REVIEW")
        holder_filtered = self.service.list_documents(admin, holder_user_id=viewer_id)
        query_filtered = self.service.list_documents(admin, query="Operator")
        paged = self.service.list_documents(admin, limit=1, offset=1)

        self.assertEqual([row["document_number"] for row in status_filtered], ["XDTS-FILTER-002"])
        self.assertEqual(
            [row["document_number"] for row in holder_filtered],
            ["XDTS-FILTER-002", "XDTS-FILTER-003"],
        )
        self.assertEqual([row["document_number"] for row in query_filtered], ["XDTS-FILTER-001"])
        self.assertEqual(len(paged), 1)
        self.assertEqual(paged[0]["document_number"], "XDTS-FILTER-002")

    def test_list_documents_defaults_to_first_100_results(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        for index in range(105):
            self.service.register_document(
                admin,
                document_number=f"XDTS-BULK-{index:03d}",
                title=f"Bulk {index}",
                description="Load test",
                status="REGISTERED",
            )

        documents = self.service.list_documents(admin)

        self.assertEqual(len(documents), 100)
        self.assertEqual(documents[0]["document_number"], "XDTS-BULK-000")
        self.assertEqual(documents[-1]["document_number"], "XDTS-BULK-099")

    def test_document_history_supports_paging(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        operator_one = self.service.create_user(
            admin,
            username="history-operator-1",
            password="Operator123!",
            role="operator",
        )
        operator_two = self.service.create_user(
            admin,
            username="history-operator-2",
            password="Operator123!",
            role="operator",
        )
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-HISTORY-PAGE-001",
            title="History Paging",
            description="History paging test",
            status="REGISTERED",
        )

        self.service.acquire_lease(admin, document_id)
        self.service.transfer_document(
            admin,
            document_id=document_id,
            new_holder_user_id=operator_one,
            expected_version=1,
            reason="First handoff.",
            new_status="IN_REVIEW",
        )
        self.service.acquire_lease(admin, document_id)
        self.service.transfer_document(
            admin,
            document_id=document_id,
            new_holder_user_id=operator_two,
            expected_version=2,
            reason="Second handoff.",
            new_status="APPROVED",
        )

        newest_page = self.service.get_document_history(admin, document_id, limit=1, offset=0)
        next_page = self.service.get_document_history(admin, document_id, limit=1, offset=1)

        self.assertEqual(len(newest_page), 1)
        self.assertEqual(newest_page[0]["reason"], "Second handoff.")
        self.assertEqual(len(next_page), 1)
        self.assertEqual(next_page[0]["reason"], "First handoff.")

    def test_operator_cannot_assign_registered_document_to_another_user(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="assign-operator",
            password="Operator123!",
            role="operator",
        )
        target_user_id = self.service.create_user(
            admin,
            username="assign-viewer",
            password="Viewer123!",
            role="viewer",
        )
        operator = self.service.authenticate("assign-operator", "Operator123!")

        with self.assertRaises(ValidationError) as context:
            self.service.register_document(
                operator,
                document_number="XDTS-ASSIGN-001",
                title="Operator Assignment Block",
                description="Operators must register to themselves.",
                status="REGISTERED",
                current_holder_user_id=target_user_id,
            )

        self.assertEqual(
            str(context.exception),
            "Only admins can assign a document to another user.",
        )

    def test_viewer_cannot_list_users(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="viewer1",
            password="Viewer123!",
            role="viewer",
        )
        viewer = self.service.authenticate("viewer1", "Viewer123!")

        with self.assertRaises(AuthorizationError):
            self.service.list_users(viewer)

    def test_operator_can_list_users(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="operator4",
            password="Operator123!",
            role="operator",
        )
        operator = self.service.authenticate("operator4", "Operator123!")

        users = self.service.list_users(operator)

        self.assertGreaterEqual(len(users), 2)
        self.assertTrue(any(user["username"] == "admin" for user in users))

    def test_failed_login_cooldown_is_enforced_after_five_attempts(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="cooldown-user",
            password="Correct123!",
            role="viewer",
        )

        for _ in range(5):
            with self.assertRaises(AuthenticationError):
                self.service.authenticate("cooldown-user", "WrongPassword!")

        with self.assertRaises(AuthenticationError) as context:
            self.service.authenticate("cooldown-user", "Correct123!")

        self.assertIn("Account locked until", str(context.exception))

        user_row = self.database.fetch_one(
            "SELECT failed_attempts, cooldown_until_utc FROM users WHERE username = ?",
            ("cooldown-user",),
        )
        self.assertEqual(user_row["failed_attempts"], 5)
        self.assertIsNotNone(user_row["cooldown_until_utc"])

    def test_audit_verification_supports_mixed_hash_versions(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        operator_id = self.service.create_user(
            admin,
            username="operator2",
            password="Operator123!",
            role="operator",
        )

        created_at_utc = utc_now_text()
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
                    "XDTS-LEGACY-001",
                    "Legacy Document",
                    "Created for migration compatibility test",
                    "REGISTERED",
                    admin.id,
                    admin.id,
                    created_at_utc,
                    created_at_utc,
                ),
            )
            document_id = int(cursor.lastrowid)
            previous_state = ""
            new_state = serialize_state(
                {
                    "current_holder_user_id": admin.id,
                    "description": "Created for migration compatibility test",
                    "document_number": "XDTS-LEGACY-001",
                    "last_state_version": 1,
                    "status": "REGISTERED",
                    "title": "Legacy Document",
                }
            )
            legacy_hash = compute_history_record_hash_v1(
                previous_record_hash="",
                document_id=document_id,
                actor_user_id=admin.id,
                action_type="DOCUMENT_REGISTERED",
                previous_state=previous_state,
                new_state=new_state,
                state_version=1,
                workstation_name=self.service.workstation_name,
                ip_address=self.service.ip_address,
                reason="Initial registration",
                created_at_utc=created_at_utc,
            )
            connection.execute(
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
                    admin.id,
                    "DOCUMENT_REGISTERED",
                    previous_state,
                    new_state,
                    1,
                    self.service.workstation_name,
                    self.service.ip_address,
                    "Initial registration",
                    created_at_utc,
                    "",
                    legacy_hash,
                    AUDIT_HASH_VERSION_LEGACY,
                ),
            )

        self.service.acquire_lease(admin, document_id)
        self.service.transfer_document(
            admin,
            document_id=document_id,
            new_holder_user_id=operator_id,
            expected_version=1,
            reason="Mixed-version audit test.",
            new_status="IN_REVIEW",
        )

        rows = self.database.fetch_all(
            "SELECT audit_hash_version FROM history WHERE document_id = ? ORDER BY id",
            (document_id,),
        )
        self.assertEqual([row["audit_hash_version"] for row in rows], [1, 2])
        self.assertEqual(
            self.service.verify_audit_chain(admin),
            "Audit chain verified successfully.",
        )

    def test_audit_verification_detects_tampering(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-TAMPER-001",
            title="Tamper Test",
            description="Tamper detection",
            status="REGISTERED",
        )

        rows = self.database.fetch_all(
            "SELECT id, audit_hash_version FROM history WHERE document_id = ?",
            (document_id,),
        )
        self.assertEqual(rows[0]["audit_hash_version"], AUDIT_HASH_VERSION_CURRENT)

        with self.database.transaction() as connection:
            connection.execute(
                "DROP TRIGGER history_prevent_update"
            )
            connection.execute(
                "DROP TRIGGER history_prevent_delete"
            )
            connection.execute(
                "UPDATE history SET record_hash = ? WHERE id = ?",
                ("tampered", rows[0]["id"]),
            )

        with self.assertRaises(ConflictError):
            self.service.verify_audit_chain(admin)

    def test_database_unavailable_is_logged_with_operation_context(self) -> None:
        class FailingDatabase:
            def initialize(self) -> None:
                return None

            def cleanup_expired_leases(self) -> int:
                raise DatabaseUnavailableError("Database unavailable. Please retry.")

        failing_service = XDTSService(FailingDatabase(), self.logger)

        with self.assertRaises(AvailabilityError):
            failing_service.authenticate("admin", "irrelevant")

        log_output = self.flush_logs()
        self.assertIn("database_unavailable", log_output)
        self.assertIn("operation=authenticate.lookup", log_output)
        self.assertIn("username=admin", log_output)

    def test_lease_conflict_is_logged_with_document_context(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        operator_id = self.service.create_user(
            admin,
            username="operator3",
            password="Operator123!",
            role="operator",
        )
        operator = self.service.authenticate("operator3", "Operator123!")
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-LEASE-001",
            title="Lease Test",
            description="Lease logging test",
            status="REGISTERED",
        )

        self.service.acquire_lease(admin, document_id)

        with self.assertRaises(LeaseError):
            self.service.acquire_lease(operator, document_id)

        log_output = self.flush_logs()
        self.assertIn("lease_conflict", log_output)
        self.assertIn("operation=acquire_lease", log_output)
        self.assertIn(f"document_id={document_id}", log_output)
        self.assertIn("actor=operator3", log_output)

    def test_lease_expiry_blocks_transfer(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        operator_id = self.service.create_user(
            admin,
            username="operator5",
            password="Operator123!",
            role="operator",
        )
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-LEASE-EXP-001",
            title="Lease Expiry Test",
            description="Lease expiry",
            status="REGISTERED",
        )

        self.service.acquire_lease(admin, document_id)
        expired_at = utc_now().replace(year=2020).isoformat()
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE document_leases SET expires_at_utc = ? WHERE document_id = ?",
                (expired_at, document_id),
            )

        with self.assertRaises(LeaseError) as context:
            self.service.transfer_document(
                admin,
                document_id=document_id,
                new_holder_user_id=operator_id,
                expected_version=1,
                reason="Should fail because lease expired.",
                new_status="IN_REVIEW",
            )

        self.assertIn("lease expired", str(context.exception).lower())

    def test_operator_cannot_transfer_document_held_by_another_user(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="transfer-operator",
            password="Operator123!",
            role="operator",
        )
        target_user_id = self.service.create_user(
            admin,
            username="transfer-viewer",
            password="Viewer123!",
            role="viewer",
        )
        operator = self.service.authenticate("transfer-operator", "Operator123!")
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-TRANSFER-OWN-001",
            title="Transfer Ownership Restriction",
            description="Only the holder can transfer unless admin.",
            status="REGISTERED",
        )

        self.service.acquire_lease(operator, document_id)

        with self.assertRaises(AuthorizationError) as context:
            self.service.transfer_document(
                operator,
                document_id=document_id,
                new_holder_user_id=target_user_id,
                expected_version=1,
                reason="Attempt transfer without current ownership.",
                new_status="IN_REVIEW",
            )

        self.assertEqual(
            str(context.exception),
            "Only admins can transfer documents they do not currently hold.",
        )

    def test_backup_database_creates_backup_file(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.register_document(
            admin,
            document_number="XDTS-BACKUP-001",
            title="Backup Test",
            description="Backup smoke coverage",
            status="REGISTERED",
        )

        backup_path = Path(self.service.backup_database(admin))

        self.assertTrue(backup_path.exists())
        self.assertEqual(backup_path.suffix, ".db")

    def test_admin_system_report_returns_summary_counts(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        operator_id = self.service.create_user(
            admin,
            username="report-operator",
            password="Operator123!",
            role="operator",
        )
        self.service.create_user(
            admin,
            username="report-viewer",
            password="Viewer123!",
            role="viewer",
        )
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-REPORT-001",
            title="Reporting Test",
            description="Report coverage",
            status="REGISTERED",
        )
        self.service.acquire_lease(admin, document_id)
        self.service.transfer_document(
            admin,
            document_id=document_id,
            new_holder_user_id=operator_id,
            expected_version=1,
            reason="Prepare reporting coverage.",
            new_status="IN_REVIEW",
        )

        report = self.service.get_system_report(admin)

        self.assertEqual(report["document_total"], 1)
        self.assertEqual(report["active_user_total"], 3)
        self.assertEqual(report["active_lease_total"], 0)
        self.assertIn(("IN_REVIEW", 1), [(row["label"], row["count"]) for row in report["documents_by_status"]])
        self.assertIn(("admin", 1), [(row["label"], row["count"]) for row in report["users_by_role"]])
        self.assertIn(("operator", 1), [(row["label"], row["count"]) for row in report["users_by_role"]])
        self.assertIn(("viewer", 1), [(row["label"], row["count"]) for row in report["users_by_role"]])
        self.assertIn(
            ("DOCUMENT_REGISTERED", 1),
            [(row["label"], row["count"]) for row in report["history_by_action"]],
        )
        self.assertIn(
            ("DOCUMENT_TRANSFERRED", 1),
            [(row["label"], row["count"]) for row in report["history_by_action"]],
        )

    def test_operator_cannot_access_system_report(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="report-operator-two",
            password="Operator123!",
            role="operator",
        )
        operator = self.service.authenticate("report-operator-two", "Operator123!")

        with self.assertRaises(AuthorizationError):
            self.service.get_system_report(operator)

    def test_admin_can_read_recent_log_lines(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.register_document(
            admin,
            document_number="XDTS-LOG-001",
            title="Log Viewer Test",
            description="Recent logs",
            status="REGISTERED",
        )

        lines = self.service.get_recent_log_lines(admin, limit=5)

        self.assertTrue(lines)
        self.assertTrue(any("Successful login for username 'admin'." in line for line in lines))
        self.assertTrue(any("Document 'XDTS-LOG-001' registered by 'admin'." in line for line in lines))

    def test_operator_cannot_read_recent_log_lines(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        self.service.create_user(
            admin,
            username="log-operator",
            password="Operator123!",
            role="operator",
        )
        operator = self.service.authenticate("log-operator", "Operator123!")

        with self.assertRaises(AuthorizationError):
            self.service.get_recent_log_lines(operator)

    def test_ip_capture_is_disabled_by_default(self) -> None:
        self.initialize_admin()
        admin = self.service.authenticate("admin", "ChangeMe123!")
        document_id = self.service.register_document(
            admin,
            document_number="XDTS-PRIV-001",
            title="Privacy Default",
            description="IP should be empty by default",
            status="REGISTERED",
        )

        history_rows = self.service.get_document_history(admin, document_id)

        self.assertEqual(self.service.ip_address, "")
        self.assertEqual(history_rows[0]["ip_address"], "")

    def test_ip_capture_can_be_enabled_via_runtime_config(self) -> None:
        enabled_root = self.test_root / "capture-ip"
        enabled_root.mkdir(parents=True, exist_ok=True)
        enabled_logger = build_application_logger(
            enabled_root / "logs",
            name=f"xdts.test.capture.{uuid.uuid4().hex}",
        )
        enabled_database = DatabaseManager(
            enabled_root / "xdts.db",
            enabled_root / "backups",
            enabled_logger,
        )
        with mock.patch.object(XDTSService, "_discover_ip_address", return_value="10.20.30.40"):
            enabled_service = XDTSService(
                enabled_database,
                enabled_logger,
                RuntimeConfig(capture_ip=True, auto_refresh_seconds=60),
            )
        try:
            enabled_service.initialize_admin(username="admin", password="ChangeMe123!")
            admin = enabled_service.authenticate("admin", "ChangeMe123!")
            document_id = enabled_service.register_document(
                admin,
                document_number="XDTS-PRIV-002",
                title="Privacy Enabled",
                description="IP should be stored when enabled",
                status="REGISTERED",
            )

            history_rows = enabled_service.get_document_history(admin, document_id)

            self.assertEqual(enabled_service.ip_address, "10.20.30.40")
            self.assertEqual(history_rows[0]["ip_address"], "10.20.30.40")
        finally:
            for handler in list(enabled_logger.handlers):
                handler.close()
                enabled_logger.removeHandler(handler)

    def test_system_report_uses_single_read_snapshot(self) -> None:
        class FakeRow(dict):
            def __getitem__(self, key):
                return super().__getitem__(key)

        class FakeCursor:
            def __init__(self, row=None, rows=None):
                self._row = row
                self._rows = rows or []

            def fetchone(self):
                return self._row

            def fetchall(self):
                return self._rows

        class FakeConnection:
            def __init__(self):
                self.begin_calls = 0
                self.executed: list[str] = []

            def execute(self, query, params=()):
                normalized = " ".join(query.split())
                self.executed.append(normalized)
                if normalized == "BEGIN":
                    self.begin_calls += 1
                    return FakeCursor()
                if "COUNT(*) AS count FROM documents" in normalized and "GROUP BY" not in normalized:
                    return FakeCursor(row=FakeRow(count=2))
                if "COUNT(*) AS count FROM users WHERE is_active = 1" in normalized:
                    return FakeCursor(row=FakeRow(count=3))
                if "COUNT(*) AS count FROM document_leases" in normalized:
                    return FakeCursor(row=FakeRow(count=1))
                if "FROM documents GROUP BY status" in normalized:
                    return FakeCursor(rows=[FakeRow(status="REGISTERED", count=2)])
                if "FROM users WHERE is_active = 1 GROUP BY role" in normalized:
                    return FakeCursor(rows=[FakeRow(role="admin", count=1)])
                if "FROM history GROUP BY action_type" in normalized:
                    return FakeCursor(rows=[FakeRow(action_type="DOCUMENT_REGISTERED", count=2)])
                raise AssertionError(f"Unexpected query: {normalized}")

            def commit(self):
                return None

            def rollback(self):
                return None

        class SnapshotDatabase:
            def __init__(self):
                self.connection = FakeConnection()

            def initialize(self) -> None:
                return None

            @contextmanager
            def read_transaction(self):
                self.connection.execute("BEGIN")
                yield self.connection
                self.connection.commit()

            def fetch_one(self, *_args, **_kwargs):
                raise AssertionError("fetch_one should not be used for snapshot reporting")

            def fetch_all(self, *_args, **_kwargs):
                raise AssertionError("fetch_all should not be used for snapshot reporting")

        snapshot_database = SnapshotDatabase()
        snapshot_service = XDTSService(snapshot_database, self.logger)
        admin_actor = type("Actor", (), {"id": 1, "username": "admin", "role": "admin"})()
        snapshot_service._require_role = lambda actor, allowed_roles: None

        report = snapshot_service.get_system_report(admin_actor)

        self.assertEqual(snapshot_database.connection.begin_calls, 1)
        self.assertEqual(report["document_total"], 2)
        self.assertEqual(report["active_user_total"], 3)
        self.assertEqual(report["active_lease_total"], 1)


if __name__ == "__main__":
    unittest.main()
