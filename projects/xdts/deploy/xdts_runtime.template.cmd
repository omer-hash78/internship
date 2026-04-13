@echo off
setlocal

rem Copy this file to xdts_runtime.cmd and replace the placeholder values.

set "XDTS_PYTHON=python"
rem Optional: use pythonw/pyw for the GUI launcher so no console window stays open.
set "XDTS_PYTHONW=pythonw"
set "XDTS_DB_PATH=\\server\share\xdts\xdts.db"
set "XDTS_LOG_DIR=%LOCALAPPDATA%\XDTS\logs"
set "XDTS_BACKUP_DIR=%LOCALAPPDATA%\XDTS\backups"

endlocal & (
    set "XDTS_PYTHON=%XDTS_PYTHON%"
    set "XDTS_PYTHONW=%XDTS_PYTHONW%"
    set "XDTS_DB_PATH=%XDTS_DB_PATH%"
    set "XDTS_LOG_DIR=%XDTS_LOG_DIR%"
    set "XDTS_BACKUP_DIR=%XDTS_BACKUP_DIR%"
)
