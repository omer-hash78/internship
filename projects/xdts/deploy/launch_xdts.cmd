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

if defined XDTS_PYTHONW (
    set "XDTS_GUI_PYTHON=%XDTS_PYTHONW%"
) else (
    call :resolve_gui_python "%XDTS_PYTHON%"
)
if not defined XDTS_GUI_PYTHON (
    set "XDTS_GUI_PYTHON=%XDTS_PYTHON%"
)

start "" "%XDTS_GUI_PYTHON%" "%SCRIPT_DIR%..\main.py" --db-path "%XDTS_DB_PATH%" --log-dir "%XDTS_LOG_DIR%" --backup-dir "%XDTS_BACKUP_DIR%"
exit /b 0

:resolve_gui_python
set "XDTS_GUI_PYTHON="
set "PYTHON_CMD=%~1"

if /I "%PYTHON_CMD%"=="python" (
    where pythonw >nul 2>&1 && set "XDTS_GUI_PYTHON=pythonw"
    goto :eof
)
if /I "%PYTHON_CMD%"=="python.exe" (
    where pythonw.exe >nul 2>&1 && set "XDTS_GUI_PYTHON=pythonw.exe"
    goto :eof
)
if /I "%PYTHON_CMD%"=="py" (
    where pyw >nul 2>&1 && set "XDTS_GUI_PYTHON=pyw"
    goto :eof
)
if /I "%PYTHON_CMD%"=="py.exe" (
    where pyw.exe >nul 2>&1 && set "XDTS_GUI_PYTHON=pyw.exe"
    goto :eof
)
if /I "%PYTHON_CMD:~-11%"=="pythonw.exe" (
    set "XDTS_GUI_PYTHON=%PYTHON_CMD%"
    goto :eof
)
if /I "%PYTHON_CMD:~-10%"=="python.exe" (
    set "PYTHONW_CMD=%PYTHON_CMD:~0,-10%pythonw.exe"
    if exist "%PYTHONW_CMD%" set "XDTS_GUI_PYTHON=%PYTHONW_CMD%"
)
goto :eof
