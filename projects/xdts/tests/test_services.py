from __future__ import annotations

import sys
import shutil
import unittest
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import DatabaseManager
from logger import build_application_logger
from services import XDTSService


class XDTSServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_root = PROJECT_ROOT / ".test-work" / uuid.uuid4().hex
        self.test_root.mkdir(parents=True, exist_ok=True)
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

    def test_bootstrap_admin_can_authenticate(self) -> None:
        session = self.service.authenticate("admin", "ChangeMe123!")
        self.assertEqual(session.username, "admin")
        self.assertEqual(session.role, "admin")

    def test_register_and_transfer_document_updates_history(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
