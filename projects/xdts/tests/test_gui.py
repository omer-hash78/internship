from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gui
from gui import XDTSApplication
from services import SessionUser


class StubService:
    def __init__(self) -> None:
        self.create_user_calls: list[dict[str, str]] = []
        self.list_users_result = [
            {"id": 1, "username": "admin", "role": "admin"},
            {"id": 2, "username": "operator1", "role": "operator"},
        ]

    def has_active_admin(self) -> bool:
        return True

    def list_documents(self, actor: SessionUser) -> list[dict]:
        return []

    def list_users(self, actor: SessionUser) -> list[dict]:
        return list(self.list_users_result)

    def create_user(self, actor: SessionUser, *, username: str, password: str, role: str) -> int:
        self.create_user_calls.append(
            {"username": username, "password": password, "role": role}
        )
        return 3

    def reset_user_password(self, actor: SessionUser, *, target_user_id: int, new_password: str) -> None:
        return None

    def get_system_report(self, actor: SessionUser) -> dict:
        return {
            "document_total": 0,
            "active_user_total": 2,
            "active_lease_total": 0,
            "documents_by_status": [],
            "users_by_role": [{"role": "admin", "count": 1}],
            "history_by_action": [],
        }


class XDTSGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = StubService()
        self._original_showerror = gui.messagebox.showerror
        self._original_showinfo = gui.messagebox.showinfo
        self.captured_errors: list[tuple[str, str]] = []
        self.captured_infos: list[tuple[str, str]] = []
        gui.messagebox.showerror = self._capture_error
        gui.messagebox.showinfo = self._capture_info
        try:
            self.app = XDTSApplication(self.service)
        except tk.TclError as exc:
            self.skipTest(f"Tkinter GUI unavailable in this environment: {exc}")
        self.app.withdraw()
        self.app.update_idletasks()

    def tearDown(self) -> None:
        gui.messagebox.showerror = self._original_showerror
        gui.messagebox.showinfo = self._original_showinfo
        if hasattr(self, "app"):
            self.app.destroy()

    def _capture_error(self, title: str, message: str) -> None:
        self.captured_errors.append((title, message))

    def _capture_info(self, title: str, message: str) -> None:
        self.captured_infos.append((title, message))

    def _all_widgets(self, root) -> list:
        widgets = [root]
        for child in root.winfo_children():
            widgets.extend(self._all_widgets(child))
        return widgets

    def _button_texts(self) -> list[str]:
        texts: list[str] = []
        for widget in self._all_widgets(self.app.container):
            if isinstance(widget, ttk.Button):
                texts.append(widget.cget("text"))
        return texts

    def test_admin_dashboard_shows_admin_actions(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")

        self.app._build_dashboard()
        self.app.update_idletasks()

        button_texts = self._button_texts()
        self.assertIn("Manage Users", button_texts)
        self.assertIn("Reports", button_texts)
        self.assertIn("Backup", button_texts)
        self.assertIn("Verify Audit", button_texts)
        self.assertIn("Add Document", button_texts)
        self.assertIn("Transfer", button_texts)

    def test_viewer_dashboard_hides_admin_and_operator_actions(self) -> None:
        self.app.current_user = SessionUser(id=2, username="viewer1", role="viewer")

        self.app._build_dashboard()
        self.app.update_idletasks()

        button_texts = self._button_texts()
        self.assertIn("Refresh", button_texts)
        self.assertIn("View History", button_texts)
        self.assertNotIn("Add Document", button_texts)
        self.assertNotIn("Transfer", button_texts)
        self.assertNotIn("Manage Users", button_texts)
        self.assertNotIn("Reports", button_texts)
        self.assertNotIn("Backup", button_texts)
        self.assertNotIn("Verify Audit", button_texts)

    def test_user_management_rejects_password_mismatch_before_service_call(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")

        self.app._open_user_management_dialog()
        self.app.update_idletasks()

        dialog = self.app.winfo_children()[-1]
        entries = [widget for widget in self._all_widgets(dialog) if isinstance(widget, ttk.Entry)]
        self.assertGreaterEqual(len(entries), 3)
        username_entry, password_entry, confirm_entry = entries[:3]
        username_entry.insert(0, "new-user")
        password_entry.insert(0, "Password123!")
        confirm_entry.insert(0, "Mismatch123!")

        create_button = next(
            widget
            for widget in self._all_widgets(dialog)
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Create User"
        )
        create_button.invoke()

        self.assertEqual(self.service.create_user_calls, [])
        self.assertIn(("Validation error", "Passwords do not match."), self.captured_errors)


if __name__ == "__main__":
    unittest.main()
