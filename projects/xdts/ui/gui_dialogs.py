from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from core.database import DOCUMENT_STATUS_VALUES
from services import XDTSServiceError

if TYPE_CHECKING:
    from .gui import XDTSApplication


def open_add_document_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role not in {"admin", "operator"}:
        messagebox.showerror(app.t("not_allowed_title"), app.t("no_permission_message"))
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
    dialog.title(app.t("register_document_title"))
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill="both", expand=True)

    status_map = {
        app.localize_status(status): status for status in DOCUMENT_STATUS_VALUES
    }
    fields = [
        (app.t("document_number"), ttk.Entry(frame, width=40)),
        (app.t("title"), ttk.Entry(frame, width=40)),
        (app.t("description"), ttk.Entry(frame, width=40)),
    ]
    for row_index, (label_text, widget) in enumerate(fields):
        ttk.Label(frame, text=label_text).grid(row=row_index * 2, column=0, sticky="w")
        widget.grid(row=row_index * 2 + 1, column=0, sticky="ew", pady=(0, 8))

    status_box = ttk.Combobox(frame, values=list(status_map), state="readonly")
    status_box.set(app.localize_status("REGISTERED"))
    ttk.Label(frame, text=app.t("status")).grid(row=6, column=0, sticky="w")
    status_box.grid(row=7, column=0, sticky="ew", pady=(0, 8))

    holder_box = ttk.Combobox(frame, values=holder_values, state=holder_state)
    holder_box.set(app.current_user.username)
    ttk.Label(frame, text=app.t("current_holder")).grid(row=8, column=0, sticky="w")
    holder_box.grid(row=9, column=0, sticky="ew", pady=(0, 8))

    def submit() -> None:
        try:
            app.service.register_document(
                app.current_user,
                document_number=fields[0][1].get(),
                title=fields[1][1].get(),
                description=fields[2][1].get(),
                status=status_map[status_box.get()],
                current_holder_user_id=user_map.get(holder_box.get()),
            )
        except XDTSServiceError as exc:
            app._present_error(exc)
            return
        dialog.destroy()
        app.refresh_documents(reason="mutation")
        app.status_var.set(app.t("document_registered"))

    ttk.Button(frame, text=app.t("create"), command=submit).grid(row=10, column=0, sticky="ew")


def open_user_management_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role != "admin":
        messagebox.showerror(app.t("not_allowed_title"), app.t("no_permission_message"))
        return

    dialog = tk.Toplevel(app)
    dialog.title(app.t("user_management_title"))
    dialog.geometry("760x520")
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

    container = app._build_scrollable_body(dialog, padding=16, bind_target=dialog)

    ttk.Label(
        container,
        text=app.t("active_users"),
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        container,
        text=app.t("user_management_description"),
        foreground="#555555",
        wraplength=700,
    ).pack(anchor="w", pady=(4, 12))

    user_tree = ttk.Treeview(
        container,
        columns=("username", "role"),
        show="headings",
        height=10,
    )
    user_tree.heading("username", text=app.t("username"))
    user_tree.heading("role", text=app.t("role"))
    user_tree.column("username", width=260, anchor="w")
    user_tree.column("role", width=160, anchor="w")
    user_tree.pack(fill="x")

    form = ttk.LabelFrame(container, text=app.t("create_user_group"), padding=16)
    form.pack(fill="x", pady=(16, 0))

    ttk.Label(form, text=app.t("username")).grid(row=0, column=0, sticky="w")
    username_entry = ttk.Entry(form, width=32)
    username_entry.grid(row=1, column=0, sticky="ew", pady=(0, 10))

    ttk.Label(form, text=app.t("password")).grid(row=2, column=0, sticky="w")
    password_entry = ttk.Entry(form, width=32, show="*")
    password_entry.grid(row=3, column=0, sticky="ew", pady=(0, 10))

    ttk.Label(form, text=app.t("confirm_password")).grid(row=4, column=0, sticky="w")
    confirm_password_entry = ttk.Entry(form, width=32, show="*")
    confirm_password_entry.grid(row=5, column=0, sticky="ew", pady=(0, 10))

    ttk.Label(form, text=app.t("role")).grid(row=6, column=0, sticky="w")
    role_map = {
        app.localize_role(role): role for role in ("admin", "operator", "viewer")
    }
    role_box = ttk.Combobox(form, values=list(role_map), state="readonly")
    role_box.set(app.localize_role("viewer"))
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
                values=(user["username"], app.localize_role(user["role"])),
            )

    def create_user() -> None:
        if password_entry.get() != confirm_password_entry.get():
            messagebox.showerror(
                app.t("validation_error_title"),
                app.t("passwords_do_not_match"),
            )
            return
        try:
            app.service.create_user(
                app.current_user,
                username=username_entry.get(),
                password=password_entry.get(),
                role=role_map[role_box.get()],
            )
        except XDTSServiceError as exc:
            app._present_error(exc)
            return
        username_entry.delete(0, "end")
        password_entry.delete(0, "end")
        confirm_password_entry.delete(0, "end")
        role_box.set(app.localize_role("viewer"))
        refresh_users()
        app.status_var.set(app.t("user_account_created"))

    def reset_password() -> None:
        selection = user_tree.selection()
        if not selection:
            messagebox.showerror(app.t("no_selection_title"), app.t("select_user_first"))
            return
        user_record = user_tree.item(selection[0], "values")
        target_user_id = int(selection[0])

        reset_dialog = tk.Toplevel(dialog)
        reset_dialog.title(app.t("reset_password_title"))
        reset_dialog.transient(dialog)
        reset_dialog.grab_set()
        app._register_modal(reset_dialog)

        reset_frame = ttk.Frame(reset_dialog, padding=16)
        reset_frame.pack(fill="both", expand=True)

        ttk.Label(
            reset_frame,
            text=app.t("reset_password_for", username=user_record[0]),
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        ttk.Label(reset_frame, text=app.t("new_password")).grid(row=1, column=0, sticky="w")
        new_password_entry = ttk.Entry(reset_frame, width=32, show="*")
        new_password_entry.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(reset_frame, text=app.t("confirm_password")).grid(row=3, column=0, sticky="w")
        confirm_reset_entry = ttk.Entry(reset_frame, width=32, show="*")
        confirm_reset_entry.grid(row=4, column=0, sticky="ew", pady=(0, 10))

        reset_frame.columnconfigure(0, weight=1)

        def submit_reset() -> None:
            if new_password_entry.get() != confirm_reset_entry.get():
                messagebox.showerror(
                    app.t("validation_error_title"),
                    app.t("passwords_do_not_match"),
                )
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
            app.status_var.set(app.t("password_reset_for", username=user_record[0]))

        ttk.Button(reset_frame, text=app.t("reset_password"), command=submit_reset).grid(
            row=5, column=0, sticky="ew"
        )
        new_password_entry.focus_set()

    def deactivate_user() -> None:
        selection = user_tree.selection()
        if not selection:
            messagebox.showerror(app.t("no_selection_title"), app.t("select_user_first"))
            return
        user_record = user_tree.item(selection[0], "values")
        if not messagebox.askyesno(
            app.t("deactivate_user_title"),
            app.t("deactivate_user_confirm", username=user_record[0]),
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
        app.status_var.set(app.t("user_account_deactivated", username=user_record[0]))

    button_row = ttk.Frame(form)
    button_row.grid(row=8, column=0, sticky="ew", pady=(4, 0))
    ttk.Button(button_row, text=app.t("create_user_group"), command=create_user).pack(side="left")
    ttk.Button(button_row, text=app.t("refresh_users"), command=refresh_users).pack(
        side="left", padx=(8, 0)
    )
    ttk.Button(button_row, text=app.t("reset_password"), command=reset_password).pack(
        side="left", padx=(8, 0)
    )
    ttk.Button(button_row, text=app.t("deactivate_user"), command=deactivate_user).pack(
        side="left", padx=(8, 0)
    )

    refresh_users()
    username_entry.focus_set()


def open_transfer_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role not in {"admin", "operator"}:
        messagebox.showerror(app.t("not_allowed_title"), app.t("no_permission_message"))
        return
    selection = app.tree.selection()
    if not selection:
        messagebox.showerror(app.t("no_selection_title"), app.t("select_document_first"))
        return
    document = app.selected_documents[selection[0]]
    if (
        app.current_user.role != "admin"
        and document["current_holder_username"] != app.current_user.username
    ):
        messagebox.showerror(
            app.t("not_allowed_title"),
            app.t("admin_transfer_only_current_holder"),
        )
        return
    try:
        app.service.acquire_lease(app.current_user, document["id"])
        users = app.service.list_users(app.current_user)
    except XDTSServiceError as exc:
        app._present_error(exc)
        return

    dialog = tk.Toplevel(app)
    dialog.title(app.t("transfer_document_title"))
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
    status_map = {
        app.localize_status(status): status for status in DOCUMENT_STATUS_VALUES
    }
    ttk.Label(frame, text=app.t("new_holder")).grid(row=1, column=0, sticky="w")
    holder_box = ttk.Combobox(frame, values=list(user_map), state="readonly")
    holder_box.set(document["current_holder_username"] or app.current_user.username)
    holder_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))

    ttk.Label(frame, text=app.t("new_status")).grid(row=3, column=0, sticky="w")
    status_box = ttk.Combobox(frame, values=list(status_map), state="readonly")
    status_box.set(app.localize_status(document["status"]))
    status_box.grid(row=4, column=0, sticky="ew", pady=(0, 8))

    ttk.Label(frame, text=app.t("reason")).grid(row=5, column=0, sticky="w")
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
                new_status=status_map[status_box.get()],
            )
        except XDTSServiceError as exc:
            app._present_error(exc)
            return
        transfer_completed["value"] = True
        dialog.destroy()
        app.refresh_documents(reason="mutation")
        app.status_var.set(app.t("document_transferred"))

    ttk.Button(frame, text=app.t("transfer"), command=submit).grid(row=7, column=0, sticky="ew")
    dialog.protocol("WM_DELETE_WINDOW", close_dialog)


def open_history_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    selection = app.tree.selection()
    if not selection:
        messagebox.showerror(app.t("no_selection_title"), app.t("select_document_first"))
        return
    document = app.selected_documents[selection[0]]
    try:
        history_rows = app.service.get_document_history(app.current_user, document["id"], limit=200)
    except XDTSServiceError as exc:
        app._present_error(exc)
        return

    dialog = tk.Toplevel(app)
    dialog.title(app.t("history_title", document_number=document["document_number"]))
    dialog.geometry("980x420")
    dialog.transient(app)
    app._register_modal(dialog)

    container = ttk.Frame(dialog, padding=12)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text=app.t("history_limit_notice"),
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
        ("created_at", app.t("timestamp"), 180),
        ("actor", app.t("actor"), 110),
        ("action", app.t("action"), 320),
        ("version", app.t("version"), 70),
        ("reason", app.t("reason"), 250),
        ("workstation", app.t("workstation"), 120),
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
        messagebox.showerror(app.t("not_allowed_title"), app.t("no_permission_message"))
        return

    dialog = tk.Toplevel(app)
    dialog.title(app.t("recent_log_activity_title"))
    dialog.geometry("920x520")
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

    container = ttk.Frame(dialog, padding=16)
    container.pack(fill="both", expand=True)

    ttk.Label(
        container,
        text=app.t("latest_workstation_log_entries"),
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w")
    ttk.Label(
        container,
        text=app.t("log_dialog_description"),
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
            log_text.insert("1.0", app.t("no_log_entries"))
        log_text.configure(state="disabled")
        log_text.see("end")

    button_row = ttk.Frame(container)
    button_row.pack(fill="x", pady=(12, 0))
    ttk.Button(button_row, text=app.t("refresh_logs"), command=refresh_logs).pack(side="left")
    ttk.Button(button_row, text=app.t("close"), command=dialog.destroy).pack(side="right")

    refresh_logs()


def open_report_dialog(app: "XDTSApplication") -> None:
    if app.current_user is None:
        return
    if app.current_user.role != "admin":
        messagebox.showerror(app.t("not_allowed_title"), app.t("no_permission_message"))
        return
    try:
        report = app.service.get_system_report(app.current_user)
    except XDTSServiceError as exc:
        app._present_error(exc)
        return

    dialog = tk.Toplevel(app)
    dialog.title(app.t("system_report_title"))
    dialog.geometry("720x480")
    dialog.transient(app)
    dialog.grab_set()
    app._register_modal(dialog)

    container = ttk.Frame(dialog, padding=16)
    container.pack(fill="both", expand=True)

    summary = ttk.LabelFrame(container, text=app.t("summary"), padding=16)
    summary.pack(fill="x")
    ttk.Label(
        summary,
        text=app.t(
            "report_summary",
            document_total=report["document_total"],
            active_user_total=report["active_user_total"],
            active_lease_total=report["active_lease_total"],
        ),
        font=("Segoe UI", 10, "bold"),
    ).pack(anchor="w")

    sections = [
        (app.t("documents_by_status"), report["documents_by_status"]),
        (app.t("users_by_role"), report["users_by_role"]),
        (app.t("history_by_action"), report["history_by_action"]),
    ]

    for title, rows in sections:
        frame = ttk.LabelFrame(container, text=title, padding=12)
        frame.pack(fill="both", expand=True, pady=(12, 0))
        tree = ttk.Treeview(frame, columns=("label", "count"), show="headings", height=5)
        tree.heading("label", text=app.t("label"))
        tree.heading("count", text=app.t("count"))
        tree.column("label", width=360, anchor="w")
        tree.column("count", width=100, anchor="w")
        tree.pack(fill="both", expand=True)
        for row in rows:
            tree.insert("", "end", values=(app.localize_label(row["label"]), row["count"]))
