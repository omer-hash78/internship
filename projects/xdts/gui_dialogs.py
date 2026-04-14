from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from database import DOCUMENT_STATUS_VALUES, TIMEZONE_LABEL
from services import XDTSServiceError

if TYPE_CHECKING:
    from gui import XDTSApplication


def open_add_document_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role not in {"admin", "operator"}:
        messagebox.showerror("Not allowed", "You do not have permission for this action.")
        return
    if app.current_user.role == "admin":
        try:
            users = app.service.list_users(app.current_user)
        except XDTSServiceError as exc:
            app._present_error(exc)
            return
        user_map = {user["username"]: user["id"] for user in users}
        holder_values = list(user_map)
        holder_state = "readonly"
    else:
        user_map = {app.current_user.username: app.current_user.id}
        holder_values = [app.current_user.username]
        holder_state = "disabled"

    dialog = tk.Toplevel(app)
    dialog.title("Register Document")
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

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
    holder_box.set(app.current_user.username)
    ttk.Label(frame, text="Current Holder").grid(row=8, column=0, sticky="w")
    holder_box.grid(row=9, column=0, sticky="ew", pady=(0, 8))

    def submit() -> None:
        try:
            app.service.register_document(
                app.current_user,
                document_number=fields[0][1].get(),
                title=fields[1][1].get(),
                description=fields[2][1].get(),
                status=status_box.get(),
                current_holder_user_id=user_map.get(holder_box.get()),
            )
        except XDTSServiceError as exc:
            app._present_error(exc)
            return
        dialog.destroy()
        app.refresh_documents(reason="mutation")
        app.status_var.set("Document registered.")

    ttk.Button(frame, text="Create", command=submit).grid(row=10, column=0, sticky="ew")


def open_user_management_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role != "admin":
        messagebox.showerror("Not allowed", "You do not have permission for this action.")
        return

    dialog = tk.Toplevel(app)
    dialog.title("User Management")
    dialog.geometry("760x520")
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

    container = app._build_scrollable_body(dialog, padding=16, bind_target=dialog)

    ttk.Label(
        container,
        text="Active Users",
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        container,
        text=(
            "Post-release user management supports active-user review, "
            "new account creation, password reset, and user deactivation."
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
            users = app.service.list_users(app.current_user)
        except XDTSServiceError as exc:
            app._present_error(exc)
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
            app.service.create_user(
                app.current_user,
                username=username_entry.get(),
                password=password_entry.get(),
                role=role_box.get(),
            )
        except XDTSServiceError as exc:
            app._present_error(exc)
            return
        username_entry.delete(0, "end")
        password_entry.delete(0, "end")
        confirm_password_entry.delete(0, "end")
        role_box.set("viewer")
        refresh_users()
        app.status_var.set("User account created.")

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
        app._register_modal(reset_dialog)

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
                app.service.reset_user_password(
                    app.current_user,
                    target_user_id=target_user_id,
                    new_password=new_password_entry.get(),
                )
            except XDTSServiceError as exc:
                app._present_error(exc)
                return
            reset_dialog.destroy()
            app.status_var.set(f"Password reset for {user_record[0]}.")

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
            app.service.deactivate_user(
                app.current_user,
                target_user_id=int(selection[0]),
            )
        except XDTSServiceError as exc:
            app._present_error(exc)
            return
        refresh_users()
        app.status_var.set(f"User account deactivated for {user_record[0]}.")

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


def open_transfer_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role not in {"admin", "operator"}:
        messagebox.showerror("Not allowed", "You do not have permission for this action.")
        return
    selection = app.tree.selection()
    if not selection:
        messagebox.showerror("No selection", "Select a document first.")
        return
    document = app.selected_documents[selection[0]]
    if (
        app.current_user.role != "admin"
        and document["current_holder_username"] != app.current_user.username
    ):
        messagebox.showerror(
            "Not allowed",
            "Only admins can transfer documents they do not currently hold.",
        )
        return
    try:
        app.service.acquire_lease(app.current_user, document["id"])
        users = app.service.list_users(app.current_user)
    except XDTSServiceError as exc:
        app._present_error(exc)
        return

    dialog = tk.Toplevel(app)
    dialog.title("Transfer Document")
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

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
    holder_box.set(document["current_holder_username"] or app.current_user.username)
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
                app.service.release_lease(app.current_user, document["id"])
            except XDTSServiceError:
                pass
        dialog.destroy()

    def submit() -> None:
        try:
            app.service.transfer_document(
                app.current_user,
                document_id=document["id"],
                new_holder_user_id=user_map[holder_box.get()],
                expected_version=document["last_state_version"],
                reason=reason_text.get("1.0", "end").strip(),
                new_status=status_box.get(),
            )
        except XDTSServiceError as exc:
            app._present_error(exc)
            return
        transfer_completed["value"] = True
        dialog.destroy()
        app.refresh_documents(reason="mutation")
        app.status_var.set("Document transferred.")

    ttk.Button(frame, text="Transfer", command=submit).grid(row=7, column=0, sticky="ew")
    dialog.protocol("WM_DELETE_WINDOW", close_dialog)


def open_history_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    selection = app.tree.selection()
    if not selection:
        messagebox.showerror("No selection", "Select a document first.")
        return
    document = app.selected_documents[selection[0]]
    try:
        history_rows = app.service.get_document_history(app.current_user, document["id"], limit=200)
    except XDTSServiceError as exc:
        app._present_error(exc)
        return

    dialog = tk.Toplevel(app)
    dialog.title(f"History - {document['document_number']}")
    dialog.geometry("980x420")
    dialog.transient(app)
    app._register_modal(dialog)

    container = ttk.Frame(dialog, padding=12)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text="Showing up to 200 most recent history records.",
        foreground="#555555",
    ).pack(anchor="w", pady=(0, 8))

    tree = ttk.Treeview(
        container,
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
        ("created_at", f"Timestamp", 180),
        ("actor", "Actor", 110),
        ("action", "Action", 320),
        ("version", "Version", 70),
        ("reason", "Reason", 250),
        ("workstation", "Workstation", 120),
    ]:
        tree.heading(column, text=heading)
        tree.column(column, width=width, anchor="w")
    tree.pack(fill="both", expand=True)

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


def open_log_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role != "admin":
        messagebox.showerror("Not allowed", "You do not have permission for this action.")
        return

    dialog = tk.Toplevel(app)
    dialog.title("Recent Log Activity")
    dialog.geometry("920x520")
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

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
            lines = app.service.get_recent_log_lines(app.current_user, limit=200)
        except XDTSServiceError as exc:
            app._present_error(exc)
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


def open_report_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role != "admin":
        messagebox.showerror("Not allowed", "You do not have permission for this action.")
        return
    try:
        report = app.service.get_system_report(app.current_user)
    except XDTSServiceError as exc:
        app._present_error(exc)
        return

    dialog = tk.Toplevel(app)
    dialog.title("System Report")
    dialog.geometry("720x480")
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

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
        ("Documents By Status", report["documents_by_status"]),
        ("Users By Role", report["users_by_role"]),
        ("History By Action", report["history_by_action"]),
    ]

    for title, rows in sections:
        frame = ttk.LabelFrame(container, text=title, padding=12)
        frame.pack(fill="both", expand=True, pady=(12, 0))
        tree = ttk.Treeview(frame, columns=("label", "count"), show="headings", height=5)
        tree.heading("label", text="Label")
        tree.heading("count", text="Count")
        tree.column("label", width=360, anchor="w")
        tree.column("count", width=100, anchor="w")
        tree.pack(fill="both", expand=True)
        for row in rows:
            tree.insert("", "end", values=(row["label"], row["count"]))
