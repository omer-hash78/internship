from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services import SessionUser
from ui import XDTSApplication
from ui import gui


class StubService:
    def __init__(self) -> None:
        self.create_user_calls: list[dict[str, str]] = []
        self.acquire_lease_calls: list[tuple[int, int]] = []
        self.deactivate_user_calls: list[dict[str, int]] = []
        self.list_documents_calls: list[dict[str, object]] = []
        self.list_users_result = [
            {"id": 1, "username": "admin", "role": "admin"},
            {"id": 2, "username": "operator1", "role": "operator"},
        ]
        self.list_document_holders_result = [
            {"id": 1, "username": "admin", "role": "admin"},
            {"id": 2, "username": "operator1", "role": "operator"},
        ]
        self.documents_result = [
            {
                "id": 11,
                "document_number": "XDTS-001",
                "title": "Main Procedure",
                "description": "Primary document",
                "status": "REGISTERED",
                "current_holder_username": "admin",
                "current_holder_user_id": 1,
                "last_state_version": 1,
                "lease_display": "",
                "updated_at_utc": "2026-04-13T12:10:00+03:00",
            }
        ]
        self.recent_log_lines_result = [
            "2026-04-13T12:00:00+03:00 INFO [xdts] application_startup",
            "2026-04-13T12:01:00+03:00 INFO [xdts] document_registered",
        ]

    def has_active_admin(self) -> bool:
        return True

    def authenticate(self, username: str, password: str) -> SessionUser:
        return SessionUser(id=1, username=username or "admin", role="admin")

    def list_documents(
        self,
        actor: SessionUser,
        *,
        status: str | None = None,
        holder_user_id: int | None = None,
        query: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        self.list_documents_calls.append(
            {
                "actor_id": actor.id,
                "status": status,
                "holder_user_id": holder_user_id,
                "query": query,
                "limit": limit,
                "offset": offset,
            }
        )
        documents = list(self.documents_result)
        if status:
            documents = [doc for doc in documents if doc["status"] == status]
        if holder_user_id is not None:
            documents = [
                doc for doc in documents if doc.get("current_holder_user_id") == holder_user_id
            ]
        if query:
            needle = query.lower()
            documents = [
                doc
                for doc in documents
                if needle in doc["document_number"].lower()
                or needle in doc["title"].lower()
                or needle in doc.get("current_holder_username", "").lower()
            ]
        return documents[offset : offset + limit]

    def list_document_holders(self, actor: SessionUser) -> list[dict]:
        return list(self.list_document_holders_result)

    def list_users(self, actor: SessionUser) -> list[dict]:
        return list(self.list_users_result)

    def create_user(self, actor: SessionUser, *, username: str, password: str, role: str) -> int:
        self.create_user_calls.append(
            {"username": username, "password": password, "role": role}
        )
        return 3

    def reset_user_password(
        self, actor: SessionUser, *, target_user_id: int, new_password: str
    ) -> None:
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

    def acquire_lease(self, actor: SessionUser, document_id: int) -> str:
        self.acquire_lease_calls.append((actor.id, document_id))
        return "2026-04-13T13:00:00+03:00"

    def release_lease(self, actor: SessionUser, document_id: int) -> None:
        return None

    def deactivate_user(self, actor: SessionUser, *, target_user_id: int) -> None:
        self.deactivate_user_calls.append({"actor_id": actor.id, "target_user_id": target_user_id})
        self.list_users_result = [
            user for user in self.list_users_result if user["id"] != target_user_id
        ]

    def get_document_history(
        self,
        actor: SessionUser,
        document_id: int,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        return [
            {
                "created_at_utc": "2026-04-13T12:10:00+03:00",
                "actor_username": "admin",
                "action_type": "DOCUMENT_TRANSFERRED",
                "action_display": "DOCUMENT_TRANSFERRED (admin -> operator1)",
                "state_version": 2,
                "reason": "Move to review.",
                "workstation_name": "WORKSTATION-1",
            }
        ][offset : offset + limit]


class XDTSGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = StubService()
        self._original_showerror = gui.messagebox.showerror
        self._original_showinfo = gui.messagebox.showinfo
        self._original_askyesno = gui.messagebox.askyesno
        self.captured_errors: list[tuple[str, str]] = []
        self.captured_infos: list[tuple[str, str]] = []
        gui.messagebox.showerror = self._capture_error
        gui.messagebox.showinfo = self._capture_info
        gui.messagebox.askyesno = self._confirm_yes
        try:
            self.app = XDTSApplication(self.service)
        except tk.TclError as exc:
            self.skipTest(f"Tkinter GUI unavailable in this environment: {exc}")
        self.app.withdraw()
        self.app.update_idletasks()

    def tearDown(self) -> None:
        gui.messagebox.showerror = self._original_showerror
        gui.messagebox.showinfo = self._original_showinfo
        gui.messagebox.askyesno = self._original_askyesno
        if hasattr(self, "app"):
            self.app._cancel_auto_refresh()
            self.app.destroy()

    def _capture_error(self, title: str, message: str) -> None:
        self.captured_errors.append((title, message))

    def _capture_info(self, title: str, message: str) -> None:
        self.captured_infos.append((title, message))

    def _confirm_yes(self, title: str, message: str) -> bool:
        return True

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

    def _label_texts(self) -> list[str]:
        texts: list[str] = []
        for widget in self._all_widgets(self.app.container):
            if isinstance(widget, ttk.Label):
                texts.append(widget.cget("text"))
        return texts

    def test_initial_view_is_login(self) -> None:
        label_texts = self._label_texts()

        self.assertIn("X Documentation Tracing System", label_texts)
        self.assertIn("Username", label_texts)
        self.assertIn("Password", label_texts)
        self.assertEqual(self._button_texts(), ["Login", "Exit"])

    def test_successful_login_opens_action_view(self) -> None:
        entries = [widget for widget in self._all_widgets(self.app.container) if isinstance(widget, ttk.Entry)]
        username_entry, password_entry = entries[:2]
        username_entry.insert(0, "admin")
        password_entry.insert(0, "secret")

        login_button = next(
            widget
            for widget in self._all_widgets(self.app.container)
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Login"
        )
        login_button.invoke()
        self.app.update_idletasks()

        label_texts = self._label_texts()
        self.assertIn("Welcome. Choose an action to continue.", label_texts)
        self.assertIn("Language", label_texts)
        self.assertEqual(
            self._button_texts(),
            ["Add/Delete Document", "Create A Record", "Document Tracking", "Exit"],
        )

    def test_action_view_has_language_combobox(self) -> None:
        self.app._complete_login(SessionUser(id=1, username="admin", role="admin"))
        comboboxes = [
            widget for widget in self._all_widgets(self.app.container) if isinstance(widget, ttk.Combobox)
        ]

        self.assertEqual(len(comboboxes), 1)
        self.assertEqual(tuple(comboboxes[0].cget("values")), ("English", "Türkçe"))

    def test_action_tracking_button_opens_dashboard(self) -> None:
        self.app._complete_login(SessionUser(id=1, username="admin", role="admin"))

        tracking_button = next(
            widget
            for widget in self._all_widgets(self.app.container)
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Document Tracking"
        )
        tracking_button.invoke()
        self.app.update_idletasks()

        self.assertIn("Refresh", self._button_texts())

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

    def test_language_switch_rerenders_dashboard_in_turkish(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")

        self.app._build_dashboard()
        self.app.language_var.set("Türkçe")
        self.app._handle_language_selected()
        self.app.update_idletasks()

        button_texts = self._button_texts()
        label_texts = self._label_texts()
        self.assertIn("Kullanıcıları Yönet", button_texts)
        self.assertIn("Kayıtları Görüntüle", button_texts)
        self.assertIn("Dil", label_texts)
        self.assertTrue(self.app.last_refresh_var.get().startswith("Son yenileme (UTC+03:00): "))

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

    def test_operator_cannot_open_transfer_dialog_for_other_users_document(self) -> None:
        self.app.current_user = SessionUser(id=2, username="operator1", role="operator")
        self.app._build_dashboard()

        self.app.selected_documents["42"] = {
            "id": 42,
            "document_number": "XDTS-TRANSFER-GUI-001",
            "status": "REGISTERED",
            "current_holder_username": "admin",
            "last_state_version": 1,
        }
        self.app.tree.insert(
            "",
            "end",
            iid="42",
            values=(
                "XDTS-TRANSFER-GUI-001",
                "Transfer GUI Restriction",
                "REGISTERED",
                "admin",
                1,
                "",
                "2026-04-13T13:00:00+03:00",
            ),
        )
        self.app.tree.selection_set("42")

        initial_children = len(self.app.winfo_children())
        self.app._open_transfer_dialog()
        self.app.update_idletasks()

        self.assertEqual(self.service.acquire_lease_calls, [])
        self.assertEqual(len(self.app.winfo_children()), initial_children)
        self.assertIn(
            (
                "Not allowed",
                "Only admins can transfer documents they do not currently hold.",
            ),
            self.captured_errors,
        )

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

    def test_user_management_can_deactivate_selected_user(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")

        self.app._open_user_management_dialog()
        self.app.update_idletasks()

        dialog = self.app.winfo_children()[-1]
        treeviews = [widget for widget in self._all_widgets(dialog) if isinstance(widget, ttk.Treeview)]
        user_tree = treeviews[0]
        user_tree.selection_set("2")

        deactivate_button = next(
            widget
            for widget in self._all_widgets(dialog)
            if isinstance(widget, ttk.Button) and widget.cget("text") == "Deactivate User"
        )
        deactivate_button.invoke()
        self.app.update_idletasks()

        self.assertEqual(
            self.service.deactivate_user_calls,
            [{"actor_id": 1, "target_user_id": 2}],
        )
        self.assertEqual(user_tree.get_children(), ("1",))

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
        self.app.tree.item(
            "11",
            values=("XDTS-HIST-001", "Title", "IN_REVIEW", "admin", 2, "", "2026-04-13T12:10:00+03:00"),
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

    def test_dashboard_filter_controls_use_server_side_query_parameters(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")
        self.app._build_dashboard()
        self.app.update_idletasks()

        self.app.query_filter_var.set("operator1")
        self.app.status_filter_var.set("REGISTERED")
        self.app.holder_filter_var.set("operator1")
        self.app.refresh_documents(reason="manual")

        last_call = self.service.list_documents_calls[-1]
        self.assertEqual(last_call["status"], "REGISTERED")
        self.assertEqual(last_call["holder_user_id"], 2)
        self.assertEqual(last_call["query"], "operator1")
        self.assertEqual(last_call["limit"], 200)
        self.assertEqual(last_call["offset"], 0)

    def test_dashboard_auto_refresh_is_scheduled_after_build(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")
        self.app._build_dashboard()
        self.app.update_idletasks()

        self.assertIsNotNone(self.app._auto_refresh_job)
        self.assertTrue(
            self.app.last_refresh_var.get().startswith("Last refreshed (UTC+03:00): ")
        )

    def test_auto_refresh_pauses_while_modal_dialog_is_open(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")
        self.app._build_dashboard()
        self.app.update_idletasks()
        initial_calls = len(self.service.list_documents_calls)

        self.app._open_user_management_dialog()
        self.app.update_idletasks()
        self.app._auto_refresh_tick()

        self.assertEqual(len(self.service.list_documents_calls), initial_calls)
        self.assertIn("paused", self.app.status_var.get().lower())

    def test_conflict_like_errors_trigger_dashboard_refresh(self) -> None:
        self.app.current_user = SessionUser(id=1, username="admin", role="admin")
        self.app._build_dashboard()
        self.app.update_idletasks()
        initial_calls = len(self.service.list_documents_calls)

        self.app._present_error(gui.LeaseError("Lease expired."))

        self.assertGreater(len(self.service.list_documents_calls), initial_calls)
        self.assertIn(("Lease conflict", "Lease expired."), self.captured_errors)

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
