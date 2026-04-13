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
        self.recent_log_lines_result = [
            "2026-04-13T09:00:00Z INFO [xdts] application_startup",
            "2026-04-13T09:01:00Z INFO [xdts] document_registered",
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

    def get_recent_log_lines(self, actor: SessionUser, *, limit: int = 200) -> list[str]:
        return self.recent_log_lines_result[-limit:]

    def get_document_history(self, actor: SessionUser, document_id: int) -> list[dict]:
        return [
            {
                "created_at_utc": "2026-04-13T09:10:00Z",
                "actor_username": "admin",
                "action_type": "DOCUMENT_TRANSFERRED",
                "action_display": "DOCUMENT_TRANSFERRED (admin -> operator1)",
                "state_version": 2,
                "reason": "Move to review.",
                "workstation_name": "WORKSTATION-1",
            }
        ]


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
        self.assertIn("View Logs", button_texts)
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
        self.assertNotIn("View Logs", button_texts)
        self.assertNotIn("Reports", button_texts)
        self.assertNotIn("Backup", button_texts)
        self.assertNotIn("Verify Audit", button_texts)

    def test_dashboard_scrolls_when_main_window_is_small(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")

        self.app.deiconify()
        self.app.geometry("1000x360")
        self.app._build_dashboard()
        self.app.update_idletasks()

        canvases = [
            widget for widget in self._all_widgets(self.app.container) if isinstance(widget, tk.Canvas)
        ]
        self.assertEqual(len(canvases), 1)
        canvas = canvases[0]
        self.assertLess(canvas.yview()[1], 1.0)

        canvas.yview_moveto(1.0)
        self.app.update_idletasks()
        self.assertGreater(canvas.yview()[0], 0.0)

    def test_dashboard_table_expands_in_standard_window(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")

        self.app.deiconify()
        self.app.geometry("1100x680")
        self.app._build_dashboard()
        self.app.update_idletasks()

        self.assertGreaterEqual(self.app.tree.winfo_height(), 400)

    def test_operator_add_document_dialog_locks_holder_to_self(self) -> None:
        self.app.current_user = SessionUser(id=2, username="operator1", role="operator")

        self.app._open_add_document_dialog()
        self.app.update_idletasks()

        dialog = self.app.winfo_children()[-1]
        comboboxes = [widget for widget in self._all_widgets(dialog) if isinstance(widget, ttk.Combobox)]
        self.assertEqual(len(comboboxes), 2)

        holder_box = comboboxes[1]
        self.assertEqual(str(holder_box.cget("state")), "disabled")
        self.assertEqual(holder_box.get(), "operator1")

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

    def test_log_dialog_displays_recent_entries_for_admin(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")

        self.app._open_log_dialog()
        self.app.update_idletasks()

        dialog = self.app.winfo_children()[-1]
        log_text = next(widget for widget in self._all_widgets(dialog) if isinstance(widget, tk.Text))
        rendered = log_text.get("1.0", "end").strip()

        self.assertIn("application_startup", rendered)
        self.assertIn("document_registered", rendered)

    def test_history_dialog_shows_transfer_target_inline_with_action(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")
        self.app._build_dashboard()

        self.app.selected_documents["11"] = {
            "id": 11,
            "document_number": "XDTS-HIST-001",
        }
        self.app.tree.insert(
            "",
            "end",
            iid="11",
            values=("XDTS-HIST-001", "Title", "IN_REVIEW", "admin", 2, "", "2026-04-13T09:10:00Z"),
        )
        self.app.tree.selection_set("11")

        self.app._open_history_dialog()
        self.app.update_idletasks()

        dialog = self.app.winfo_children()[-1]
        history_tree = next(
            widget
            for widget in self._all_widgets(dialog)
            if isinstance(widget, ttk.Treeview) and widget is not self.app.tree
        )
        row_values = history_tree.item(history_tree.get_children()[0], "values")

        self.assertNotIn("holder_change", history_tree.cget("columns"))
        self.assertIn("DOCUMENT_TRANSFERRED (admin -> operator1)", row_values)

    def test_user_management_dialog_scrolls_when_window_is_small(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")

        self.app._open_user_management_dialog()
        self.app.update_idletasks()

        dialog = self.app.winfo_children()[-1]
        dialog.geometry("420x260")
        self.app.update_idletasks()

        canvas = next(widget for widget in self._all_widgets(dialog) if isinstance(widget, tk.Canvas))
        self.assertLess(canvas.yview()[1], 1.0)

        canvas.yview_moveto(1.0)
        self.app.update_idletasks()
        self.assertGreater(canvas.yview()[0], 0.0)


if __name__ == "__main__":
    unittest.main()
