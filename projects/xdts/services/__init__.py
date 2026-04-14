from __future__ import annotations

import socket

from core.config import RuntimeConfig
from core.database import DatabaseManager

from .admin import AdminServiceMixin
from .auth import AuthServiceMixin
from .documents import DocumentServiceMixin
from .models import (
    CountSummary,
    DocumentHistoryItem,
    DocumentListItem,
    SessionUser,
    SystemReport,
    UserSummary,
)
from .reporting import ReportingServiceMixin
from .support import (
    AuthenticationError,
    AuthorizationError,
    AvailabilityError,
    ConflictError,
    LeaseError,
    NotFoundError,
    ServiceSupport,
    ValidationError,
    XDTSServiceError,
)


class XDTSService(
    ServiceSupport,
    AuthServiceMixin,
    DocumentServiceMixin,
    AdminServiceMixin,
    ReportingServiceMixin,
):
    def __init__(
        self,
        database: DatabaseManager,
        app_logger,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.database = database
        self.logger = app_logger
        self.config = config or RuntimeConfig()
        self.workstation_name = socket.gethostname()
        self.ip_address = self._discover_ip_address()
        self.database.initialize()


__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "AvailabilityError",
    "ConflictError",
    "CountSummary",
    "DocumentHistoryItem",
    "DocumentListItem",
    "LeaseError",
    "NotFoundError",
    "SessionUser",
    "SystemReport",
    "UserSummary",
    "ValidationError",
    "XDTSService",
    "XDTSServiceError",
]
