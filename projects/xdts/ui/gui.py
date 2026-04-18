from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from core.config import RuntimeConfig
from core.database import DOCUMENT_STATUS_VALUES, TIMEZONE_LABEL, utc_now_text
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
from .i18n import DEFAULT_LANGUAGE, LANGUAGE_CODES_BY_LABEL, LANGUAGE_LABELS, translate


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
        self.language_code = DEFAULT_LANGUAGE
        self._preferred_holder_filter_id: int | None = None

        self.title(self.t("app_title"))
        self.geometry("1100x680")
        self.minsize(900, 360)

        self.container = ttk.Frame(self, padding=16)
        self.container.pack(fill="both", expand=True)

        self.language_var = tk.StringVar(value=LANGUAGE_LABELS[self.language_code])
        self.status_var = tk.StringVar(value=self.t("status_ready"))
        self.last_refresh_var = tk.StringVar(
            value=self.t("last_refreshed_pending", timezone=TIMEZONE_LABEL)
        )
        self.query_filter_var = tk.StringVar()
        self.status_filter_var = tk.StringVar(value=self.t("all_statuses"))
        self.holder_filter_var = tk.StringVar(value=self.t("all_holders"))
        self._build_login_view()

    def t(self, key: str, **kwargs: object) -> str:
        return translate(self.language_code, key, **kwargs)

    def localize_status(self, value: str) -> str:
        return self.t(f"status_{value}") if value in DOCUMENT_STATUS_VALUES else value

    def localize_role(self, value: str) -> str:
        role_key = f"role_{value}"
        localized = self.t(role_key)
        return localized if localized != role_key else value

    def localize_label(self, value: str) -> str:
        if value in DOCUMENT_STATUS_VALUES:
            return self.localize_status(value)
        if value in {"admin", "operator", "viewer"}:
            return self.localize_role(value)
        return value

    def _build_language_selector(self, parent: tk.Misc) -> ttk.Frame:
        selector = ttk.Frame(parent)
        ttk.Label(selector, text=self.t("language")).pack(side="left")
        box = ttk.Combobox(
            selector,
            textvariable=self.language_var,
            values=list(LANGUAGE_LABELS.values()),
            state="readonly",
            width=10,
        )
        box.pack(side="left", padx=(6, 0))
        box.bind("<<ComboboxSelected>>", self._handle_language_selected)
        return selector

    def _handle_language_selected(self, _event: tk.Event | None = None) -> None:
        selected_code = LANGUAGE_CODES_BY_LABEL.get(self.language_var.get(), DEFAULT_LANGUAGE)
        if selected_code == self.language_code:
            return

        self.language_code = selected_code
        self.title(self.t("app_title"))
        self.status_var.set(self.t("status_ready"))
        if self.current_user is None:
            self._build_login_view()
            return
        self._build_dashboard()

    def _status_filter_options(self) -> list[tuple[str, str | None]]:
        return [
            (self.t("all_statuses"), None),
            *[(self.localize_status(status), status) for status in DOCUMENT_STATUS_VALUES],
        ]

    def _resolve_status_filter_value(self, value: str) -> str | None:
        if not value:
            return None
        for language_code in LANGUAGE_LABELS:
            if value == translate(language_code, "all_statuses"):
                return None
            for status in DOCUMENT_STATUS_VALUES:
                if value == translate(language_code, f"status_{status}"):
                    return status
        return value if value in DOCUMENT_STATUS_VALUES else None

    def _set_status_filter_display(self, status_value: str | None) -> None:
        options = self._status_filter_options()
        display_value = next(
            (label for label, raw_value in options if raw_value == status_value),
            self.t("all_statuses"),
        )
        self.status_filter_var.set(display_value)

    def _is_all_holders_value(self, value: str) -> bool:
        return value in {
            "",
            translate("en", "all_holders"),
            translate("tr", "all_holders"),
        }

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
        self.title(self.t("app_title"))
        self.status_var.set(self.t("status_ready"))
        self.last_refresh_var.set(self.t("last_refreshed_pending", timezone=TIMEZONE_LABEL))
        self.status_filter_var.set(self.t("all_statuses"))
        self.holder_filter_var.set(self.t("all_holders"))

        login_language_selector = self._build_language_selector(self.container)
        login_language_selector.place(relx=1.0, rely=0.0, anchor="ne")

        frame = ttk.Frame(self.container, padding=(28, 24))
        frame.place(relx=0.5, rely=0.5, anchor="center")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(
            frame,
            text=self.t("app_title"),
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))

        ttk.Label(frame, text=self.t("username")).grid(row=1, column=0, sticky="w")
        username_entry = ttk.Entry(frame, width=32)
        username_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        ttk.Label(frame, text=self.t("password")).grid(row=3, column=0, sticky="w")
        password_entry = ttk.Entry(frame, width=32, show="*")
        password_entry.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 16))

        try:
            has_active_admin = self.service.has_active_admin()
        except XDTSServiceError:
            has_active_admin = True

        if has_active_admin:
            guidance_text = self.t("login_use_account")
        else:
            guidance_text = self.t("login_no_admin")
        ttk.Label(
            frame,
            text=guidance_text,
            wraplength=360,
            foreground="#555555",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 18))

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

        ttk.Button(frame, text=self.t("login"), command=submit_login).grid(
            row=6, column=0, sticky="ew"
        )
        ttk.Button(frame, text=self.t("exit"), command=self.destroy).grid(
            row=6, column=1, sticky="ew", padx=(10, 0)
        )

        username_entry.focus_set()
        username_entry.bind("<Return>", submit_login)
        password_entry.bind("<Return>", submit_login)

    def _build_dashboard(self) -> None:
        current_status_filter = self._resolve_status_filter_value(self.status_filter_var.get())
        self._preferred_holder_filter_id = self._resolve_holder_filter_id()
        self._clear_container()
        if self.current_user is None:
            self._build_login_view()
            return
        self.title(self.t("app_title"))

        content = self._build_scrollable_body(self.container, bind_target=self, fill_height=True)

        top = ttk.Frame(content)
        top.pack(fill="x")

        right_controls = ttk.Frame(top)
        right_controls.pack(side="right")
        self._build_language_selector(right_controls).pack(side="left")
        ttk.Button(right_controls, text=self.t("logout"), command=self._build_login_view).pack(
            side="left", padx=(8, 0)
        )
        ttk.Label(
            top,
            text=self.t(
                "user_banner",
                username=self.current_user.username,
                role=self.localize_role(self.current_user.role),
            ),
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        actions = ttk.Frame(content, padding=(0, 12))
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text=self.t("refresh"),
            command=lambda: self.refresh_documents(reason="manual"),
        ).pack(
            side="left"
        )
        ttk.Button(actions, text=self.t("view_history"), command=self._open_history_dialog).pack(
            side="left", padx=(8, 0)
        )
        if self.current_user.role in {"admin", "operator"}:
            ttk.Button(
                actions,
                text=self.t("add_document"),
                command=self._open_add_document_dialog,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text=self.t("transfer"),
                command=self._open_transfer_dialog,
            ).pack(side="left", padx=(8, 0))
        if self.current_user.role == "admin":
            ttk.Button(
                actions,
                text=self.t("manage_users"),
                command=self._open_user_management_dialog,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text=self.t("view_logs"),
                command=self._open_log_dialog,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text=self.t("reports"),
                command=self._open_report_dialog,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text=self.t("verify_audit"),
                command=self._verify_audit_chain,
            ).pack(side="left", padx=(8, 0))
            ttk.Button(
                actions,
                text=self.t("backup"),
                command=self._backup_database,
            ).pack(side="left", padx=(8, 0))

        filters = ttk.LabelFrame(content, text=self.t("filters"), padding=12)
        filters.pack(fill="x")
        filters.columnconfigure(1, weight=1)

        ttk.Label(filters, text=self.t("search")).grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(filters, textvariable=self.query_filter_var, width=32)
        search_entry.grid(row=0, column=1, sticky="ew", padx=(6, 12))

        ttk.Label(filters, text=self.t("status")).grid(row=0, column=2, sticky="w")
        status_values = [label for label, _raw_value in self._status_filter_options()]
        status_box = ttk.Combobox(
            filters,
            textvariable=self.status_filter_var,
            values=status_values,
            state="readonly",
            width=18,
        )
        status_box.grid(row=0, column=3, sticky="ew", padx=(6, 12))
        self._set_status_filter_display(current_status_filter)

        ttk.Label(filters, text=self.t("current_holder")).grid(row=0, column=4, sticky="w")
        self.holder_filter_box = ttk.Combobox(
            filters,
            textvariable=self.holder_filter_var,
            values=[self.t("all_holders")],
            state="readonly",
            width=22,
        )
        self.holder_filter_box.grid(row=0, column=5, sticky="ew", padx=(6, 12))

        ttk.Button(
            filters,
            text=self.t("apply_filters"),
            command=lambda: self.refresh_documents(reason="manual"),
        ).grid(row=0, column=6, sticky="ew")
        ttk.Button(filters, text=self.t("clear"), command=self._clear_filters).grid(
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
            "document_number": self.t("document_number"),
            "title": self.t("title"),
            "status": self.t("status"),
            "current_holder": self.t("current_holder"),
            "version": self.t("version"),
            "lease": self.t("active_lease"),
            "updated_at_utc": self.t("updated", timezone=TIMEZONE_LABEL),
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
            text=self.t("showing_documents", page_size=self.PAGE_SIZE),
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
        self.status_filter_var.set(self.t("all_statuses"))
        self.holder_filter_var.set(self.t("all_holders"))
        self.refresh_documents(reason="manual")

    def _resolve_holder_filter_id(self) -> int | None:
        value = self.holder_filter_var.get()
        if self._is_all_holders_value(value):
            return None
        return self._holder_filters.get(value)

    def _set_last_refreshed(self) -> None:
        self.last_refresh_var.set(
            self.t("last_refreshed", timezone=TIMEZONE_LABEL, timestamp=utc_now_text())
        )

    def _refresh_holder_filters(self) -> None:
        if self.current_user is None:
            return
        try:
            holders = self.service.list_document_holders(self.current_user)
        except XDTSServiceError:
            return
        current_value = self.holder_filter_var.get()
        self._holder_filters = {holder["username"]: holder["id"] for holder in holders}
        values = [self.t("all_holders"), *self._holder_filters.keys()]
        self.holder_filter_box.configure(values=values)
        selected_value = current_value
        if self._preferred_holder_filter_id is not None:
            for username, holder_id in self._holder_filters.items():
                if holder_id == self._preferred_holder_filter_id:
                    selected_value = username
                    break
        elif self._is_all_holders_value(current_value):
            selected_value = self.t("all_holders")
        if selected_value not in values:
            selected_value = self.t("all_holders")
        self.holder_filter_var.set(selected_value)
        self._preferred_holder_filter_id = None

    def refresh_documents(
        self,
        *,
        reason: str = "manual",
        show_errors: bool = True,
    ) -> None:
        if self.current_user is None:
            return
        if reason == "auto" and self._modal_depth > 0:
            self.status_var.set(self.t("auto_refresh_paused"))
            self._schedule_auto_refresh()
            return

        existing_selection = set(self.tree.selection()) if hasattr(self, "tree") else set()
        status_filter = self._resolve_status_filter_value(self.status_filter_var.get())
        try:
            documents = self.service.list_documents(
                self.current_user,
                status=status_filter,
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
                    self.localize_status(document["status"]),
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
        self.status_var.set(self.t("loaded_documents", count=len(documents)))
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
            messagebox.showerror(self.t("not_allowed_title"), self.t("no_permission_message"))
            return
        try:
            message = self.service.verify_audit_chain(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return
        messagebox.showinfo(self.t("audit_verification_title"), message)

    def _backup_database(self) -> None:
        if self.current_user is None:
            return
        if self.current_user.role != "admin":
            messagebox.showerror(self.t("not_allowed_title"), self.t("no_permission_message"))
            return
        try:
            backup_path = self.service.backup_database(self.current_user)
        except XDTSServiceError as exc:
            self._present_error(exc)
            return
        messagebox.showinfo(self.t("backup_created_title"), backup_path)

    def _present_error(self, exc: XDTSServiceError) -> None:
        if isinstance(exc, AuthorizationError):
            messagebox.showerror(self.t("not_allowed_title"), str(exc))
        elif isinstance(exc, (ValidationError, AuthenticationError)):
            messagebox.showerror(self.t("validation_error_title"), str(exc))
        elif isinstance(exc, LeaseError):
            messagebox.showerror(self.t("lease_conflict_title"), str(exc))
        elif isinstance(exc, ConflictError):
            messagebox.showerror(self.t("conflict_title"), str(exc))
        elif isinstance(exc, AvailabilityError):
            messagebox.showerror(self.t("database_unavailable_title"), str(exc))
        else:
            messagebox.showerror(self.t("operation_failed_title"), str(exc))

        if isinstance(exc, (LeaseError, ConflictError, AvailabilityError)) and self.current_user:
            self.refresh_documents(reason="error", show_errors=False)
