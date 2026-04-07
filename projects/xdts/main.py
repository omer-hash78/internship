from __future__ import annotations

import argparse
from pathlib import Path

from database import DatabaseManager
from gui import XDTSApplication
from logger import build_application_logger
from services import SessionUser, XDTSService


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "xdts.db"
DEFAULT_LOG_DIR = BASE_DIR / "logs"
DEFAULT_BACKUP_DIR = BASE_DIR / "backups"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="XDTS desktop application")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    parser.add_argument(
        "--verify-audit",
        action="store_true",
        help="Verify the audit chain and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_logger = build_application_logger(Path(args.log_dir))
    database = DatabaseManager(args.db_path, args.backup_dir, app_logger)
    service = XDTSService(database, app_logger)

    if args.verify_audit:
        actor = SessionUser(id=1, username="system", role="admin")
        try:
            print(service.verify_audit_chain(actor))
            return 0
        except Exception as exc:
            print(str(exc))
            return 1

    application = XDTSApplication(service)
    application.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
