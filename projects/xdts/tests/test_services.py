from __future__ import annotations

import sys
import shutil
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
        expired_at = utc_now().replace(year=2020).isoformat().replace("+00:00", "Z")
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


if __name__ == "__main__":
    unittest.main()
