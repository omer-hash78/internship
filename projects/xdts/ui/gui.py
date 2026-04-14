from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from core.config import RuntimeConfig
from core.database import TIMEZONE_LABEL, utc_now_text
from services import (
    AuthenticationError,
    AuthorizationError,
    AvailabilityError,
    ConflictError,
    LeaseError,
    SessionUser,
    ValidationError,
    XDTSService,
    XDTSServiceError,
)

from .gui_dialogs import (
    open_add_document_dialog,
    open_history_dialog,
    open_log_dialog,
    open_report_dialog,
    open_transfer_dialog,
    open_user_management_dialog,
)


class XDTSApplication(tk.Tk):
    PAGE_SIZE = 200

    def __init__(self, service: XDTSService, config: RuntimeConfig | None = None) -> None:
        super().__init__()
        self.service = service
        self.config = config or getattr(service, "config", RuntimeConfig())
        self.current_user: SessionUser | None = None
        self.selected_documents: dict[str, object] = {}
        self._holder_filters: dict[str, int] = {}
        self._modal_depth = 0
        self._auto_refresh_job: str | None = None

        self.title("X Documentation Tracing System")
        self.geometry("1100x680")
        self.minsize(900, 360)

        self.container = ttk.Frame(self, padding=16)
        self.container.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Ready")
        self.last_refresh_var = tk.StringVar(value=f"Last refreshed ({TIMEZONE_LABEL}): not yet")
        self.query_filter_var = tk.StringVar()
        self.status_filter_var = tk.StringVar(value="All statuses")
        self.holder_filter_var = tk.StringVar(value="All holders")
        self._build_login_view()

    def _clear_container(self) -> None:
        self._cancel_auto_refresh()
        for child in self.container.winfo_children():
            child.destroy()

    def _build_scrollable_body(
        self,
        parent: tk.Misc,
        *,
        padding: int = 0,
        bind_target: tk.Misc | None = None,
        fill_height: bool = False,
    ) -> ttk.Frame:
        shell = ttk.Frame(parent)
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(shell, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        body = ttk.Frame(canvas, padding=padding)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def update_scrollregion(_event: tk.Event | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def sync_body_size(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)
            if fill_height:
                canvas.itemconfigure(window_id, height=max(event.height, body.winfo_reqheight()))

        def on_mousewheel(event: tk.Event) -> str | None:
            if canvas.yview() == (0.0, 1.0):
                return None
            if getattr(event, "delta", 0):
                canvas.yview_scroll(int(-event.delta / 120), "units")
            elif getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            return "break"

        body.bind("<Configure>", update_scrollregion)
        canvas.bind("<Configure>", sync_body_size)
        scroll_target = bind_target or parent
        scroll_target.bind("<MouseWheel>", on_mousewheel, add="+")
        scroll_target.bind("<Button-4>", on_mousewheel, add="+")
        scroll_target.bind("<Button-5>", on_mousewheel, add="+")
        return body

    def _build_login_view(self) -> None:
        self._clear_container()
        self.current_user = None
        self.selected_documents = {}

        frame = ttk.Frame(self.container, padding=24)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(
            frame,
            text="X Documentation Tracing System",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))

        ttk.Label(frame, text="Username").grid(row=1, column=0, sticky="w")
        username_entry = ttk.Entry(frame, width=28)
        username_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        ttk.Label(frame, text="Password").grid(row=3, column=0, sticky="w")
        password_entry = ttk.Entry(frame, width=28, show="*")
        password_entry.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        try:
            has_active_admin = self.service.has_active_admin()
        except XDTSServiceError:
            has_active_admin = True

        if has_active_admin:
            guidance_text = "Use your assigned XDTS account."
        else:
            guidance_text = (
                "No active admin account is configured. "
                "An authorized operator must run "
                "`python projects/xdts/main.py --initialize-admin` "
                "before normal login can be used."
            )
        ttk.Label(
            frame,
            text=guidance_text,
            wraplength=360,
            foreground="#555555",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 16))

        def submit_login(*_args) -> None:
            try:
                user = self.service.authenticate(
                    username_entry.get(),
                    password_entry.get(),
                )
            except XDTSServiceError as exc:
                self._present_error(exc)
                return
            self.current_user = user
            self._build_dashboard()

        ttk.Button(frame, text="Login", command=submit_login).grid(
            row=6, column=0, sticky="ew"
        )
        ttk.Button(frame, text="Exit", command=self.destroy).grid(
            row=6, column=1, sticky="ew", padx=(8, 0)
        )

        username_entry.focus_set()
        username_entry.bind("<Return>", submit_login)
        password_entry.bind("<Return>", submit_login)

    def _build_dashboard(self) -> None:
        self._clear_container()
        if self.current_user is None:
            self._build_login_view()
            return

        content = self._build_scrollable_body(self.container, bind_target=self, fill_height=True)

        top = ttk.Frame(content)
        top.pack(fill="x")

        ttk.Label(
            top,
            text=f"User: {self.current_user.username} ({self.current_user.role})",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        ttk.Button(top, text="Logout", command=self._build_login_view).pack(side="right")

        actions = ttk.Frame(content, padding=(0, 12))
        actions.pack(fill="x")
        ttk.Button(actions, text="Refresh", command=lambda: self.refresh_documents(reason="manual")).pack(
            side="left"
        )
        ttk.Button(actions, text="View History", command=self._open_history_dialog).pack(
            side="left", padx=(8, 0)
        )
        if self.current_user.role in {"admin", "operator"}:
            ttk.Button(
                actions,
                text="Add Document",
                command=self._open_add_document_dialog,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text="Transfer",
                command=self._open_transfer_dialog,
            ).pack(side="left", padx=(8, 0))
        if self.current_user.role == "admin":
            ttk.Button(
                actions,
                text="Manage Users",
                command=self._open_user_management_dialog,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text="View Logs",
                command=self._open_log_dialog,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text="Reports",
                command=self._open_report_dialog,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text="Verify Audit",
                command=self._verify_audit_chain,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text="Backup",
                command=self._backup_database,
            ).pack(side="left", padx=(8, 0))

        filters = ttk.LabelFrame(content, text="Filters", padding=12)
        filters.pack(fill="x")
        filters.columnconfigure(1, weight=1)

        ttk.Label(filters, text="Search").grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(filters, textvariable=self.query_filter_var, width=32)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(6, 12))

        ttk.Label(filters, text="Status").grid(row=0, column=2, sticky="w")
        status_values = ["All statuses", "REGISTERED", "IN_REVIEW", "APPROVED", "ARCHIVED"]
        status_box = ttk.Combobox(
            filters,
            textvariable=self.status_filter_var,
            values=status_values,
            state="readonly",
            width=18,
        )
        status_box.grid(row=0, column=3, sticky="ew", padx=(6, 12))

        ttk.Label(filters, text="Current Holder").grid(row=0, column=4, sticky="w")
        self.holder_filter_box = ttk.Combobox(
            filters,
            textvariable=self.holder_filter_var,
            values=["All holders"],
            state="readonly",
            width=22,
        )
        self.holder_filter_box.grid(row=0, column=5, sticky="ew", padx=(6, 12))

        ttk.Button(
            filters,
            text="Apply Filters",
            command=lambda: self.refresh_documents(reason="manual"),
        ).grid(row=0, column=6, sticky="ew")
        ttk.Button(filters, text="Clear", command=self._clear_filters).grid(
            row=0, column=7, sticky="ew", padx=(8, 0)
        )
        search_entry.bind("<Return>", lambda _event: self.refresh_documents(reason="manual"))

        columns = (
            "document_number",
            "title",
            "status",
            "current_holder",
            "version",
            "lease",
            "updated_at_utc",
        )
        self.tree = ttk.Treeview(
            content,
            columns=columns,
            show="headings",
            height=20,
        )
        headings = {
            "document_number": "Document Number",
            "title": "Title",
            "status": "Status",
            "current_holder": "Current Holder",
            "version": "Version",
            "lease": "Active Lease",
            "updated_at_utc": f"Updated ({TIMEZONE_LABEL})",
        }
        widths = {
            "document_number": 140,
            "title": 240,
            "status": 120,
            "current_holder": 140,
            "version": 70,
            "lease": 280,
            "updated_at_utc": 150,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="w")
        self.tree.pack(fill="both", expand=True, pady=(12, 0))

        footer = ttk.Frame(content)
        footer.pack(fill="x")
        ttk.Label(
            footer,
            text=f"Showing up to {self.PAGE_SIZE} matching documents per refresh.",
            foreground="#555555",
        ).pack(side="left", pady=(10, 0))
        ttk.Label(footer, textvariable=self.last_refresh_var).pack(side="right", pady=(10, 0))

        status_bar = ttk.Label(
            content,
            textvariable=self.status_var,
            padding=(0, 10, 0, 0),
        )
        status_bar.pack(fill="x")

        self.refresh_documents(reason="manual")

    def _clear_filters(self) -> None:
        self.query_filter_var.set("")
        self.status_filter_var.set("All statuses")
        self.holder_filter_var.set("All holders")
        self.refresh_documents(reason="manual")

    def _resolve_holder_filter_id(self) -> int | None:
        value = self.holder_filter_var.get()
        if not value or value == "All holders":
            return None
        return self._holder_filters.get(value)

    def _set_last_refreshed(self) -> None:
        self.last_refresh_var.set(f"Last refreshed ({TIMEZONE_LABEL}): {utc_now_text()}")

    def _refresh_holder_filters(self) -> None:
        if self.current_user is None:
            return
        try:
            holders = self.service.list_document_holders(self.current_user)
        except XDTSServiceError:
            return
        current_value = self.holder_filter_var.get()
        self._holder_filters = {holder["username"]: holder["id"] for holder in holders}
        values = ["All holders", *self._holder_filters.keys()]
        self.holder_filter_box.configure(values=values)
        if current_value not in values:
            self.holder_filter_var.set("All holders")

    def refresh_documents(
        self,
        *,
        reason: str = "manual",
        show_errors: bool = True,
    ) -> None:
        if self.current_user is None:
            return
        if reason == "auto" and self._modal_depth > 0:
            self.status_var.set("Auto-refresh paused while a dialog is open.")
            self._schedule_auto_refresh()
            return

        existing_selection = set(self.tree.selection()) if hasattr(self, "tree") else set()
        status_filter = self.status_filter_var.get()
        try:
            documents = self.service.list_documents(
                self.current_user,
                status=None if status_filter == "All statuses" else status_filter,
                holder_user_id=self._resolve_holder_filter_id(),
                query=self.query_filter_var.get().strip() or None,
                limit=self.PAGE_SIZE,
                offset=0,
            )
            self._refresh_holder_filters()
        except XDTSServiceError as exc:
            if show_errors:
                self._present_error(exc)
            else:
                self.status_var.set(str(exc))
            self._schedule_auto_refresh()
            return

        self.selected_documents = {}
        for item in self.tree.get_children():
            self.tree.delete(item)

        restored_selection: list[str] = []
        for document in documents:
            item_id = str(document["id"])
            self.selected_documents[item_id] = document
            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    document["document_number"],
                    document["title"],
                    document["status"],
                    document["current_holder_username"] or "",
                    document["last_state_version"],
                    document["lease_display"],
                    document["updated_at_utc"],
                ),
            )
            if item_id in existing_selection:
                restored_selection.append(item_id)
        if restored_selection:
            self.tree.selection_set(restored_selection)
        self.status_var.set(f"Loaded {len(documents)} document(s).")
        self._set_last_refreshed()
        self._schedule_auto_refresh()

    def _schedule_auto_refresh(self) -> None:
        self._cancel_auto_refresh()
        if self.current_user is None or self.config.auto_refresh_seconds <= 0:
            return
        self._auto_refresh_job = self.after(
            self.config.auto_refresh_seconds * 1000,
            self._auto_refresh_tick,
        )

    def _cancel_auto_refresh(self) -> None:
        if self._auto_refresh_job is None:
            return
        try:
            self.after_cancel(self._auto_refresh_job)
        except tk.TclError:
            pass
        self._auto_refresh_job = None

    def _auto_refresh_tick(self) -> None:
        self._auto_refresh_job = None
        self.refresh_documents(reason="auto", show_errors=False)

    def _register_modal(self, dialog: tk.Toplevel) -> None:
        self._modal_depth += 1
        dialog._xdts_modal_registered = True  # type: ignore[attr-defined]

        def on_destroy(_event: tk.Event | None = None) -> None:
            if getattr(dialog, "_xdts_modal_registered", False):
                dialog._xdts_modal_registered = False  # type: ignore[attr-defined]
                self._modal_depth = max(0, self._modal_depth - 1)
                self._schedule_auto_refresh()

        dialog.bind("<Destroy>", on_destroy, add="+")

    def _open_add_document_dialog(self) -> None:
        open_add_document_dialog(self)

    def _open_user_management_dialog(self) -> None:
        open_user_management_dialog(self)

    def _open_transfer_dialog(self) -> None:
        open_transfer_dialog(self)

    def _open_history_dialog(self) -> None:
        open_history_dialog(self)

    def _open_log_dialog(self) -> None:
        open_log_dialog(self)

    def _open_report_dialog(self) -> None:
        open_report_dialog(self)

    def _verify_audit_chain(self) -> None:
        if self.current_user is None:
            return
        if self.current_user.role != "admin":
            messagebox.showerror("Not allowed", "You do not have permission for this action.")
            return
        try:
            message = self.service.verify_audit_chain(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return
        messagebox.showinfo("Audit verification", message)

    def _backup_database(self) -> None:
        if self.current_user is None:
            return
        if self.current_user.role != "admin":
            messagebox.showerror("Not allowed", "You do not have permission for this action.")
            return
        try:
            backup_path = self.service.backup_database(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return
        messagebox.showinfo("Backup created", backup_path)

    def _present_error(self, exc: XDTSServiceError) -> None:
        if isinstance(exc, AuthorizationError):
            messagebox.showerror("Not allowed", str(exc))
        elif isinstance(exc, (ValidationError, AuthenticationError)):
            messagebox.showerror("Validation error", str(exc))
        elif isinstance(exc, LeaseError):
            messagebox.showerror("Lease conflict", str(exc))
        elif isinstance(exc, ConflictError):
            messagebox.showerror("Conflict", str(exc))
        elif isinstance(exc, AvailabilityError):
            messagebox.showerror("Database unavailable", str(exc))
        else:
            messagebox.showerror("Operation failed", str(exc))

        if isinstance(exc, (LeaseError, ConflictError, AvailabilityError)) and self.current_user:
            self.refresh_documents(reason="error", show_errors=False)
