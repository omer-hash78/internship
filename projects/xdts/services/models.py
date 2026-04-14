from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class RecordView:
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass(frozen=True)
class SessionUser(RecordView):
    id: int
    username: str
    role: str


@dataclass(frozen=True)
class UserSummary(RecordView):
    id: int
    username: str
    role: str


@dataclass(frozen=True)
class DocumentListItem(RecordView):
    id: int
    document_number: str
    title: str
    description: str
    status: str
    last_state_version: int
    updated_at_utc: str
    current_holder_username: str
    current_holder_user_id: int | None
    lease_holder_username: str
    lease_workstation_name: str
    expires_at_utc: str
    lease_display: str


@dataclass(frozen=True)
class DocumentHistoryItem(RecordView):
    id: int
    created_at_utc: str
    action_type: str
    action_display: str
    reason: str
    state_version: int
    workstation_name: str
    ip_address: str
    actor_username: str


@dataclass(frozen=True)
class CountSummary(RecordView):
    label: str
    count: int


@dataclass(frozen=True)
class SystemReport(RecordView):
    document_total: int
    active_user_total: int
    active_lease_total: int
    documents_by_status: list[CountSummary]
    users_by_role: list[CountSummary]
    history_by_action: list[CountSummary]
