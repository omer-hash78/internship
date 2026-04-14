from __future__ import annotations

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

from .database import LOCAL_TIMEZONE


class LocalTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        timestamp = datetime.fromtimestamp(record.created, LOCAL_TIMEZONE)
        if datefmt:
            return timestamp.strftime(datefmt)
        return timestamp.isoformat(timespec="seconds")


def build_application_logger(log_dir: Path | str, *, name: str = "xdts") -> logging.Logger:
    log_root = Path(log_dir)
    log_root.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    target_log = log_root / "xdts.log"
    if any(
        isinstance(handler, logging.handlers.RotatingFileHandler)
        and Path(handler.baseFilename) == target_log
        for handler in logger.handlers
    ):
        return logger

    handler = logging.handlers.RotatingFileHandler(
        target_log,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = LocalTimeFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
