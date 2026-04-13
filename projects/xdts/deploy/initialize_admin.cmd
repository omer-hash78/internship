@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
if not exist "%SCRIPT_DIR%xdts_runtime.cmd" (
    echo xdts_runtime.cmd is missing in the deploy folder.
    echo Copy xdts_runtime.template.cmd to xdts_runtime.cmd and set the required values.
    exit /b 1
)
call "%SCRIPT_DIR%xdts_runtime.cmd"
if errorlevel 1 exit /b 1

if "%~1"=="" (
    echo Usage: initialize_admin.cmd ^<admin_username^>
    exit /b 1
)

"%XDTS_PYTHON%" "%SCRIPT_DIR%..\main.py" --db-path "%XDTS_DB_PATH%" --log-dir "%XDTS_LOG_DIR%" --backup-dir "%XDTS_BACKUP_DIR%" --initialize-admin --username "%~1"
exit /b %errorlevel%
