from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int(value: str | None, *, default: int, minimum: int = 0) -> int:
    if value is None:
        return default
    try:
        parsed = int(value.strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


@dataclass(frozen=True)
class RuntimeConfig:
    capture_ip: bool = False
    auto_refresh_seconds: int = 60

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> "RuntimeConfig":
        source = environ or os.environ
        return cls(
            capture_ip=_parse_bool(source.get("XDTS_CAPTURE_IP"), default=False),
            auto_refresh_seconds=_parse_int(
                source.get("XDTS_AUTO_REFRESH_SECONDS"),
                default=60,
                minimum=0,
            ),
        )
