from __future__ import annotations

import logging
import logging.handlers
import time
from pathlib import Path


class UTCFormatter(logging.Formatter):
    converter = time.gmtime


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
    formatter = UTCFormatter(
        "%(asctime)sZ %(levelname)s [%(name)s] %(message)s",
        "%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
