from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from database import DOCUMENT_STATUS_VALUES
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


class XDTSApplication(tk.Tk):
    def __init__(self, service: XDTSService) -> None:
        super().__init__()
        self.service = service
        self.current_user: SessionUser | None = None
        self.selected_documents: dict[str, dict] = {}

        self.title("X Documentation Tracing System")
        self.geometry("1100x680")
        self.minsize(900, 360)

        self.container = ttk.Frame(self, padding=16)
        self.container.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Ready")
        self._build_login_view()

    def _clear_container(self) -> None:
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
        ttk.Button(actions, text="Refresh", command=self.refresh_documents).pack(
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
            content,
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
        if self.current_user.role == "admin":
            try:
                users = self.service.list_users(self.current_user)
            except XDTSServiceError as exc:
                self._present_error(exc)
                return
            user_map = {user["username"]: user["id"] for user in users}
            holder_values = list(user_map)
            holder_state = "readonly"
        else:
            user_map = {self.current_user.username: self.current_user.id}
            holder_values = [self.current_user.username]
            holder_state = "disabled"

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

        holder_box = ttk.Combobox(frame, values=holder_values, state=holder_state)
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

    def _open_user_management_dialog(self) -> None:
        if self.current_user is None:
            return
        if self.current_user.role != "admin":
            messagebox.showerror("Not allowed", "You do not have permission for this action.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("User Management")
        dialog.geometry("760x520")
        dialog.transient(self)
        dialog.grab_set()

        container = self._build_scrollable_body(dialog, padding=16, bind_target=dialog)

        ttk.Label(
            container,
            text="Active Users",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "First-release user management supports active-user review, "
                "new account creation, and password reset."
            ),
            foreground="#555555",
            wraplength=700,
        ).pack(anchor="w", pady=(4, 12))

        user_tree = ttk.Treeview(
            container,
            columns=("username", "role"),
            show="headings",
            height=10,
        )
        user_tree.heading("username", text="Username")
        user_tree.heading("role", text="Role")
        user_tree.column("username", width=260, anchor="w")
        user_tree.column("role", width=160, anchor="w")
        user_tree.pack(fill="x")

        form = ttk.LabelFrame(container, text="Create User", padding=16)
        form.pack(fill="x", pady=(16, 0))

        ttk.Label(form, text="Username").grid(row=0, column=0, sticky="w")
        username_entry = ttk.Entry(form, width=32)
        username_entry.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(form, text="Password").grid(row=2, column=0, sticky="w")
        password_entry = ttk.Entry(form, width=32, show="*")
        password_entry.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(form, text="Confirm Password").grid(row=4, column=0, sticky="w")
        confirm_password_entry = ttk.Entry(form, width=32, show="*")
        confirm_password_entry.grid(row=5, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(form, text="Role").grid(row=6, column=0, sticky="w")
        role_box = ttk.Combobox(form, values=("admin", "operator", "viewer"), state="readonly")
        role_box.set("viewer")
        role_box.grid(row=7, column=0, sticky="ew", pady=(0, 10))

        form.columnconfigure(0, weight=1)

        def refresh_users() -> None:
            try:
                users = self.service.list_users(self.current_user)
            except XDTSServiceError as exc:
                self._present_error(exc)
                return

            for item in user_tree.get_children():
                user_tree.delete(item)
            for user in users:
                user_tree.insert(
                    "",
                    "end",
                    iid=str(user["id"]),
                    values=(user["username"], user["role"]),
                )

        def create_user() -> None:
            if password_entry.get() != confirm_password_entry.get():
                messagebox.showerror("Validation error", "Passwords do not match.")
                return
            try:
                self.service.create_user(
                    self.current_user,
                    username=username_entry.get(),
                    password=password_entry.get(),
                    role=role_box.get(),
                )
            except XDTSServiceError as exc:
                self._present_error(exc)
                return
            username_entry.delete(0, "end")
            password_entry.delete(0, "end")
            confirm_password_entry.delete(0, "end")
            role_box.set("viewer")
            refresh_users()
            self.status_var.set("User account created.")

        def reset_password() -> None:
            selection = user_tree.selection()
            if not selection:
                messagebox.showerror("No selection", "Select a user first.")
                return
            user_record = user_tree.item(selection[0], "values")
            target_user_id = int(selection[0])

            reset_dialog = tk.Toplevel(dialog)
            reset_dialog.title("Reset Password")
            reset_dialog.transient(dialog)
            reset_dialog.grab_set()

            reset_frame = ttk.Frame(reset_dialog, padding=16)
            reset_frame.pack(fill="both", expand=True)

            ttk.Label(
                reset_frame,
                text=f"Reset password for {user_record[0]}",
                font=("Segoe UI", 10, "bold"),
            ).grid(row=0, column=0, sticky="w", pady=(0, 12))

            ttk.Label(reset_frame, text="New Password").grid(row=1, column=0, sticky="w")
            new_password_entry = ttk.Entry(reset_frame, width=32, show="*")
            new_password_entry.grid(row=2, column=0, sticky="ew", pady=(0, 10))

            ttk.Label(reset_frame, text="Confirm Password").grid(row=3, column=0, sticky="w")
            confirm_reset_entry = ttk.Entry(reset_frame, width=32, show="*")
            confirm_reset_entry.grid(row=4, column=0, sticky="ew", pady=(0, 10))

            reset_frame.columnconfigure(0, weight=1)

            def submit_reset() -> None:
                if new_password_entry.get() != confirm_reset_entry.get():
                    messagebox.showerror("Validation error", "Passwords do not match.")
                    return
                try:
                    self.service.reset_user_password(
                        self.current_user,
                        target_user_id=target_user_id,
                        new_password=new_password_entry.get(),
                    )
                except XDTSServiceError as exc:
                    self._present_error(exc)
                    return
                reset_dialog.destroy()
                self.status_var.set(f"Password reset for {user_record[0]}.")

            ttk.Button(reset_frame, text="Reset Password", command=submit_reset).grid(
                row=5, column=0, sticky="ew"
            )
            new_password_entry.focus_set()

        def deactivate_user() -> None:
            selection = user_tree.selection()
            if not selection:
                messagebox.showerror("No selection", "Select a user first.")
                return
            user_record = user_tree.item(selection[0], "values")
            if not messagebox.askyesno(
                "Deactivate User",
                f"Deactivate user {user_record[0]}?",
            ):
                return
            try:
                self.service.deactivate_user(
                    self.current_user,
                    target_user_id=int(selection[0]),
                )
            except XDTSServiceError as exc:
                self._present_error(exc)
                return
            refresh_users()
            self.status_var.set(f"User account deactivated for {user_record[0]}.")

        button_row = ttk.Frame(form)
        button_row.grid(row=8, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(button_row, text="Create User", command=create_user).pack(side="left")
        ttk.Button(button_row, text="Refresh Users", command=refresh_users).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(button_row, text="Reset Password", command=reset_password).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(button_row, text="Deactivate User", command=deactivate_user).pack(
            side="left", padx=(8, 0)
        )

        refresh_users()
        username_entry.focus_set()

    def _open_transfer_dialog(self) -> None:
        if self.current_user is None:
            return
        if self.current_user.role not in {"admin", "operator"}:
            messagebox.showerror("Not allowed", "You do not have permission for this action.")
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("No selection", "Select a document first.")
            return
        document = self.selected_documents[selection[0]]
        if (
            self.current_user.role != "admin"
            and document["current_holder_username"] != self.current_user.username
        ):
            messagebox.showerror(
                "Not allowed",
                "Only admins can transfer documents they do not currently hold.",
            )
            return
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
            columns=(
                "created_at",
                "actor",
                "action",
                "version",
                "reason",
                "workstation",
            ),
            show="headings",
        )
        for column, heading, width in [
            ("created_at", "Timestamp (UTC)", 150),
            ("actor", "Actor", 110),
            ("action", "Action", 320),
            ("version", "Version", 70),
            ("reason", "Reason", 250),
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
                    row["action_display"],
                    row["state_version"],
                    row["reason"],
                    row["workstation_name"],
                ),
            )

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

    def _open_log_dialog(self) -> None:
        if self.current_user is None:
            return
        if self.current_user.role != "admin":
            messagebox.showerror("Not allowed", "You do not have permission for this action.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Recent Log Activity")
        dialog.geometry("920x520")
        dialog.transient(self)
        dialog.grab_set()

        container = ttk.Frame(dialog, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Latest workstation log entries",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            container,
            text="Shows the most recent local XDTS actions and failures for this workstation.",
            foreground="#555555",
            wraplength=860,
        ).pack(anchor="w", pady=(4, 12))

        text_frame = ttk.Frame(container)
        text_frame.pack(fill="both", expand=True)

        log_text = tk.Text(text_frame, wrap="none", state="disabled")
        y_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=log_text.yview)
        x_scroll = ttk.Scrollbar(text_frame, orient="horizontal", command=log_text.xview)
        log_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        log_text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        def refresh_logs() -> None:
            try:
                lines = self.service.get_recent_log_lines(self.current_user, limit=200)
            except XDTSServiceError as exc:
                self._present_error(exc)
                return

            log_text.configure(state="normal")
            log_text.delete("1.0", "end")
            if lines:
                log_text.insert("1.0", "\n".join(lines))
            else:
                log_text.insert("1.0", "No log entries are available for this workstation yet.")
            log_text.configure(state="disabled")
            log_text.see("end")

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(12, 0))
        ttk.Button(button_row, text="Refresh Logs", command=refresh_logs).pack(side="left")
        ttk.Button(button_row, text="Close", command=dialog.destroy).pack(side="right")

        refresh_logs()

    def _open_report_dialog(self) -> None:
        if self.current_user is None:
            return
        if self.current_user.role != "admin":
            messagebox.showerror("Not allowed", "You do not have permission for this action.")
            return
        try:
            report = self.service.get_system_report(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return

        dialog = tk.Toplevel(self)
        dialog.title("System Report")
        dialog.geometry("720x480")
        dialog.transient(self)
        dialog.grab_set()

        container = ttk.Frame(dialog, padding=16)
        container.pack(fill="both", expand=True)

        summary = ttk.LabelFrame(container, text="Summary", padding=16)
        summary.pack(fill="x")
        ttk.Label(
            summary,
            text=(
                f"Documents: {report['document_total']}    "
                f"Active users: {report['active_user_total']}    "
                f"Active leases: {report['active_lease_total']}"
            ),
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        sections = [
            ("Documents By Status", "status", "Status", report["documents_by_status"]),
            ("Users By Role", "role", "Role", report["users_by_role"]),
            ("History By Action", "action_type", "Action", report["history_by_action"]),
        ]

        for title, key_name, label_text, rows in sections:
            frame = ttk.LabelFrame(container, text=title, padding=12)
            frame.pack(fill="both", expand=True, pady=(12, 0))
            tree = ttk.Treeview(frame, columns=(key_name, "count"), show="headings", height=5)
            tree.heading(key_name, text=label_text)
            tree.heading("count", text="Count")
            tree.column(key_name, width=360, anchor="w")
            tree.column("count", width=100, anchor="w")
            tree.pack(fill="both", expand=True)
            for row in rows:
                tree.insert("", "end", values=(row[key_name], row["count"]))

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
