from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from database import DOCUMENT_STATUS_VALUES
from services import (
    AuthenticationError,
    AvailabilityError,
    ConflictError,
    LeaseError,
    SessionUser,
    ValidationError,
    XDTSService,
    XDTSServiceError,
)


class XDTSApplication(tk.Tk):
    def __init__(self, service: XDTSService) -> None:
        super().__init__()
        self.service = service
        self.current_user: SessionUser | None = None
        self.selected_documents: dict[str, dict] = {}

        self.title("X Documentation Tracing System")
        self.geometry("1100x680")
        self.minsize(980, 620)

        self.container = ttk.Frame(self, padding=16)
        self.container.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Ready")
        self._build_login_view()

    def _clear_container(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()

    def _build_login_view(self) -> None:
        self._clear_container()
        self.current_user = None

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

        top = ttk.Frame(self.container)
        top.pack(fill="x")

        ttk.Label(
            top,
            text=f"User: {self.current_user.username} ({self.current_user.role})",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        ttk.Button(top, text="Logout", command=self._build_login_view).pack(side="right")

        actions = ttk.Frame(self.container, padding=(0, 12))
        actions.pack(fill="x")
        ttk.Button(actions, text="Refresh", command=self.refresh_documents).pack(
            side="left"
        )
        ttk.Button(actions, text="Add Document", command=self._open_add_document_dialog).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Transfer", command=self._open_transfer_dialog).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="View History", command=self._open_history_dialog).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Verify Audit", command=self._verify_audit_chain).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(actions, text="Backup", command=self._backup_database).pack(
            side="left", padx=(8, 0)
        )

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
            self.container,
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
            "updated_at_utc": "Updated (UTC)",
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
        self.tree.pack(fill="both", expand=True)

        status_bar = ttk.Label(
            self.container,
            textvariable=self.status_var,
            padding=(0, 10, 0, 0),
        )
        status_bar.pack(fill="x")

        self.refresh_documents()

    def refresh_documents(self) -> None:
        if self.current_user is None:
            return
        try:
            documents = self.service.list_documents(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return

        self.selected_documents = {}
        for item in self.tree.get_children():
            self.tree.delete(item)

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
        self.status_var.set(f"Loaded {len(documents)} document(s).")

    def _open_add_document_dialog(self) -> None:
        if self.current_user is None:
            return
        if self.current_user.role not in {"admin", "operator"}:
            messagebox.showerror("Not allowed", "You do not have permission for this action.")
            return
        try:
            users = self.service.list_users(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return

        dialog = tk.Toplevel(self)
        dialog.title("Register Document")
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)

        fields = [
            ("Document Number", ttk.Entry(frame, width=40)),
            ("Title", ttk.Entry(frame, width=40)),
            ("Description", ttk.Entry(frame, width=40)),
        ]
        for row_index, (label_text, widget) in enumerate(fields):
            ttk.Label(frame, text=label_text).grid(row=row_index * 2, column=0, sticky="w")
            widget.grid(row=row_index * 2 + 1, column=0, sticky="ew", pady=(0, 8))

        status_box = ttk.Combobox(frame, values=DOCUMENT_STATUS_VALUES, state="readonly")
        status_box.set("REGISTERED")
        ttk.Label(frame, text="Status").grid(row=6, column=0, sticky="w")
        status_box.grid(row=7, column=0, sticky="ew", pady=(0, 8))

        user_map = {user["username"]: user["id"] for user in users}
        holder_box = ttk.Combobox(frame, values=list(user_map), state="readonly")
        holder_box.set(self.current_user.username)
        ttk.Label(frame, text="Current Holder").grid(row=8, column=0, sticky="w")
        holder_box.grid(row=9, column=0, sticky="ew", pady=(0, 8))

        def submit() -> None:
            try:
                self.service.register_document(
                    self.current_user,
                    document_number=fields[0][1].get(),
                    title=fields[1][1].get(),
                    description=fields[2][1].get(),
                    status=status_box.get(),
                    current_holder_user_id=user_map.get(holder_box.get()),
                )
            except XDTSServiceError as exc:
                self._present_error(exc)
                return
            dialog.destroy()
            self.refresh_documents()
            self.status_var.set("Document registered.")

        ttk.Button(frame, text="Create", command=submit).grid(row=10, column=0, sticky="ew")

    def _open_transfer_dialog(self) -> None:
        if self.current_user is None:
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("No selection", "Select a document first.")
            return
        document = self.selected_documents[selection[0]]
        try:
            self.service.acquire_lease(self.current_user, document["id"])
            users = self.service.list_users(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return

        dialog = tk.Toplevel(self)
        dialog.title("Transfer Document")
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=f"{document['document_number']} | version {document['last_state_version']}",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        user_map = {user["username"]: user["id"] for user in users}
        ttk.Label(frame, text="New Holder").grid(row=1, column=0, sticky="w")
        holder_box = ttk.Combobox(frame, values=list(user_map), state="readonly")
        holder_box.set(document["current_holder_username"] or self.current_user.username)
        holder_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(frame, text="New Status").grid(row=3, column=0, sticky="w")
        status_box = ttk.Combobox(frame, values=DOCUMENT_STATUS_VALUES, state="readonly")
        status_box.set(document["status"])
        status_box.grid(row=4, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(frame, text="Reason").grid(row=5, column=0, sticky="w")
        reason_text = tk.Text(frame, width=48, height=6)
        reason_text.grid(row=6, column=0, sticky="ew", pady=(0, 12))

        transfer_completed = {"value": False}

        def close_dialog() -> None:
            if not transfer_completed["value"]:
                try:
                    self.service.release_lease(self.current_user, document["id"])
                except XDTSServiceError:
                    pass
            dialog.destroy()

        def submit() -> None:
            try:
                self.service.transfer_document(
                    self.current_user,
                    document_id=document["id"],
                    new_holder_user_id=user_map[holder_box.get()],
                    expected_version=document["last_state_version"],
                    reason=reason_text.get("1.0", "end").strip(),
                    new_status=status_box.get(),
                )
            except XDTSServiceError as exc:
                self._present_error(exc)
                return
            transfer_completed["value"] = True
            dialog.destroy()
            self.refresh_documents()
            self.status_var.set("Document transferred.")

        ttk.Button(frame, text="Transfer", command=submit).grid(row=7, column=0, sticky="ew")
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)

    def _open_history_dialog(self) -> None:
        if self.current_user is None:
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("No selection", "Select a document first.")
            return
        document = self.selected_documents[selection[0]]
        try:
            history_rows = self.service.get_document_history(self.current_user, document["id"])
        except XDTSServiceError as exc:
            self._present_error(exc)
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"History - {document['document_number']}")
        dialog.geometry("980x420")

        tree = ttk.Treeview(
            dialog,
            columns=("created_at", "actor", "action", "version", "reason", "workstation"),
            show="headings",
        )
        for column, heading, width in [
            ("created_at", "Timestamp (UTC)", 150),
            ("actor", "Actor", 110),
            ("action", "Action", 170),
            ("version", "Version", 70),
            ("reason", "Reason", 360),
            ("workstation", "Workstation", 120),
        ]:
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=12, pady=12)

        for row in history_rows:
            tree.insert(
                "",
                "end",
                values=(
                    row["created_at_utc"],
                    row["actor_username"],
                    row["action_type"],
                    row["state_version"],
                    row["reason"],
                    row["workstation_name"],
                ),
            )

    def _verify_audit_chain(self) -> None:
        if self.current_user is None:
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
        try:
            backup_path = self.service.backup_database(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return
        messagebox.showinfo("Backup created", backup_path)

    def _present_error(self, exc: XDTSServiceError) -> None:
        if isinstance(exc, (ValidationError, AuthenticationError)):
            messagebox.showerror("Validation error", str(exc))
        elif isinstance(exc, LeaseError):
            messagebox.showerror("Lease conflict", str(exc))
        elif isinstance(exc, ConflictError):
            messagebox.showerror("Conflict", str(exc))
        elif isinstance(exc, AvailabilityError):
            messagebox.showerror("Database unavailable", str(exc))
        else:
            messagebox.showerror("Operation failed", str(exc))
