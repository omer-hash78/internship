# XDTS Deployment Guide

## Purpose
This guide defines how to prepare and deploy the current XDTS build to a workstation without introducing extra runtime dependencies or installer tooling.

## Deployment Model

The current XDTS deployment model is a folder-based workstation bundle.

The bundle contains:
- the Python application files
- deployment launcher scripts
- rollout and operator documentation

The shared SQLite database remains on the approved network location.
Logs and backups remain local to each workstation.

Production is the live combination of:
- the copied workstation bundle on each real user PC
- the single shared `xdts.db` file on the approved network path

The repository and the local `dist` folder are not production by themselves.

## Quick Rollout SOP

Use this sequence for a normal department rollout:
1. Finalize the approved XDTS source build in the repository.
2. Run the bundle builder to recreate `projects/xdts/dist/xdts-workstation`.
3. Choose the real shared production database path, such as `\\OPS-SRV\DepartmentApps\XDTS\xdts.db`.
4. Copy the built `xdts-workstation` folder to each target workstation, for example `C:\XDTS\`.
5. On each workstation, create `deploy\xdts_runtime.cmd` from the template and set the same `XDTS_DB_PATH`.
6. On one approved workstation only, run `deploy\initialize_admin.cmd <admin_username>`.
7. Log in as admin and create the remaining user accounts.
8. Tell users to start XDTS with `deploy\launch_xdts.cmd`.
9. Run `Verify Audit` and `Backup` as part of first-day validation.

## Shared Database Requirement

All active XDTS workstations must point to the same live database file.

Recommended model:
- host `xdts.db` on an always-available file server or NAS share
- use a UNC path such as `\\server\share\xdts\xdts.db`

Do not use:
- a different local database file on each PC
- a sync folder such as OneDrive, Dropbox, or Google Drive as the live database
- manual copy-and-replace workflows between workstations

If the shared database is hosted on a normal office PC, that PC must remain powered on and reachable while XDTS is in use.

## Prerequisites

Before deployment:
1. Install a supported Python 3 runtime on the workstation.
2. Confirm the workstation can access the approved shared database path.
3. Confirm the workstation can write to its local log and backup directories.
4. Confirm the operator has the approved rollout documentation.

## Build The Workstation Bundle

From the repository root, run:

```powershell
powershell -ExecutionPolicy Bypass -File projects/xdts/tools/build_workstation_bundle.ps1
```

Expected result:
- a bundle is created under `projects/xdts/dist/xdts-workstation`

Operational note:
- the builder recreates the `dist\xdts-workstation` folder
- permanent deployment logic changes must be made in the source files under `projects/xdts`, then rebuilt

## Configure The Bundle

1. Copy the built `xdts-workstation` folder to the target workstation.
2. Open the copied bundle's `deploy` folder.
3. Copy `xdts_runtime.template.cmd` to `xdts_runtime.cmd`.
4. Replace the placeholder values:
   - `XDTS_PYTHON`
   - `XDTS_PYTHONW` for windowless GUI launch, if available
   - `XDTS_DB_PATH`
   - `XDTS_LOG_DIR`
   - `XDTS_BACKUP_DIR`

Recommended values:
- `XDTS_PYTHONW`: `pythonw` or `pyw` so `launch_xdts.cmd` does not keep a console window open during normal GUI use
- `XDTS_DB_PATH`: the approved shared SQLite file path
- `XDTS_LOG_DIR`: a local workstation path such as `%LOCALAPPDATA%\XDTS\logs`
- `XDTS_BACKUP_DIR`: a local workstation path such as `%LOCALAPPDATA%\XDTS\backups`

Example runtime file:

```cmd
@echo off
setlocal

set "XDTS_PYTHON=py"
set "XDTS_PYTHONW=pythonw"
set "XDTS_DB_PATH=\\OPS-SRV\DepartmentApps\XDTS\xdts.db"
set "XDTS_LOG_DIR=%LOCALAPPDATA%\XDTS\logs"
set "XDTS_BACKUP_DIR=%LOCALAPPDATA%\XDTS\backups"

endlocal & (
    set "XDTS_PYTHON=%XDTS_PYTHON%"
    set "XDTS_PYTHONW=%XDTS_PYTHONW%"
    set "XDTS_DB_PATH=%XDTS_DB_PATH%"
    set "XDTS_LOG_DIR=%XDTS_LOG_DIR%"
    set "XDTS_BACKUP_DIR=%XDTS_BACKUP_DIR%"
)
```

## Launcher Scripts

The deployment bundle includes:
- `deploy\launch_xdts.cmd`
- `deploy\initialize_admin.cmd`
- `deploy\verify_audit.cmd`

Usage:

Start the GUI:

```cmd
deploy\launch_xdts.cmd
```

Operational note:
- `launch_xdts.cmd` prefers `XDTS_PYTHONW` when configured so the GUI opens without leaving a persistent terminal window behind
- `initialize_admin.cmd` and `verify_audit.cmd` still use the console Python launcher because they prompt for credentials and print results

Initialize the first admin:

```cmd
deploy\initialize_admin.cmd <admin_username>
```

Verify the audit chain:

```cmd
deploy\verify_audit.cmd <admin_username>
```

Normal users should only need:
- the copied bundle on their workstation
- Python installed
- a correct `deploy\xdts_runtime.cmd`
- their assigned XDTS username and password

## Recommended Workstation Validation

After copying the bundle to a workstation:
1. Run `deploy\launch_xdts.cmd`.
2. Confirm the login screen appears.
3. Log in as admin.
4. Run the checks in `docs\review\xdts_gui_smoke_checklist.md`.
5. Run `Verify Audit`.
6. Run `Backup`.

## Operational Rules

- do not point logs at the shared network database folder
- do not point backups at the live shared database file
- do not edit the shared SQLite database manually
- keep all active workstations on the approved build after rollout
- initialize the first admin only after `XDTS_DB_PATH` points to the real shared database
- do not initialize against a temporary local database and then switch the path later

## Current Packaging Scope

This deployment model is intentionally simple.

It does not yet include:
- MSI packaging
- executable bundling
- auto-update handling
- centralized installer orchestration

Those can be added later if the department needs a more managed rollout path.
