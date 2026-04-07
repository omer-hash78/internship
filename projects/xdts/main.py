from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from database import DatabaseManager
from gui import XDTSApplication
from logger import build_application_logger
from services import AuthenticationError, ValidationError, XDTSService


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
    parser.add_argument(
        "--initialize-admin",
        action="store_true",
        help="Create the initial admin account when no active admin exists.",
    )
    parser.add_argument(
        "--username",
        help="Username used for explicit admin initialization or authenticated CLI actions.",
    )
    return parser.parse_args()


def prompt_for_password(prompt_text: str = "Password: ") -> str:
    return getpass.getpass(prompt_text)


def main() -> int:
    args = parse_args()
    app_logger = build_application_logger(Path(args.log_dir))
    database = DatabaseManager(args.db_path, args.backup_dir, app_logger)
    app_logger.info(
        "application_startup mode=main db_path=%s backup_dir=%s",
        args.db_path,
        args.backup_dir,
    )
    try:
        service = XDTSService(database, app_logger)

        if args.initialize_admin:
            username = (args.username or input("Initial admin username: ")).strip()
            password = prompt_for_password("Initial admin password: ")
            confirm_password = prompt_for_password("Confirm password: ")
            if password != confirm_password:
                print("Passwords do not match.")
                return 1
            try:
                service.initialize_admin(username=username, password=password)
                print(f"Initial admin account '{username}' created.")
                return 0
            except ValidationError as exc:
                print(str(exc))
                return 1
            except Exception as exc:
                print(str(exc))
                return 1

        if args.verify_audit:
            username = (args.username or input("Username: ")).strip()
            password = prompt_for_password()
            try:
                actor = service.authenticate(username, password)
                print(service.verify_audit_chain(actor))
                return 0
            except AuthenticationError as exc:
                print(str(exc))
                return 1
            except Exception as exc:
                print(str(exc))
                return 1

        application = XDTSApplication(service)
        application.mainloop()
        return 0
    finally:
        app_logger.info("application_shutdown mode=main")


if __name__ == "__main__":
    raise SystemExit(main())
