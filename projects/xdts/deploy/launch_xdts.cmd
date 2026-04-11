@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%xdts_runtime.cmd"
if errorlevel 1 exit /b 1

if not defined XDTS_PYTHON (
    echo XDTS_PYTHON is not set in xdts_runtime.cmd
    exit /b 1
)
if not defined XDTS_DB_PATH (
    echo XDTS_DB_PATH is not set in xdts_runtime.cmd
    exit /b 1
)
if not defined XDTS_LOG_DIR (
    echo XDTS_LOG_DIR is not set in xdts_runtime.cmd
    exit /b 1
)
if not defined XDTS_BACKUP_DIR (
    echo XDTS_BACKUP_DIR is not set in xdts_runtime.cmd
    exit /b 1
)

"%XDTS_PYTHON%" "%SCRIPT_DIR%..\main.py" --db-path "%XDTS_DB_PATH%" --log-dir "%XDTS_LOG_DIR%" --backup-dir "%XDTS_BACKUP_DIR%"
exit /b %errorlevel%
