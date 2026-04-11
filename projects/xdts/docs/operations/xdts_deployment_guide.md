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

## Configure The Bundle

1. Open the bundle's `deploy` folder.
2. Copy `xdts_runtime.template.cmd` to `xdts_runtime.cmd`.
3. Replace the placeholder values:
   - `XDTS_PYTHON`
   - `XDTS_DB_PATH`
   - `XDTS_LOG_DIR`
   - `XDTS_BACKUP_DIR`

Recommended values:
- `XDTS_DB_PATH`: the approved shared SQLite file path
- `XDTS_LOG_DIR`: a local workstation path such as `%LOCALAPPDATA%\XDTS\logs`
- `XDTS_BACKUP_DIR`: a local workstation path such as `%LOCALAPPDATA%\XDTS\backups`

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

Initialize the first admin:

```cmd
deploy\initialize_admin.cmd <admin_username>
```

Verify the audit chain:

```cmd
deploy\verify_audit.cmd <admin_username>
```

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

## Current Packaging Scope

This deployment model is intentionally simple.

It does not yet include:
- MSI packaging
- executable bundling
- auto-update handling
- centralized installer orchestration

Those can be added later if the department needs a more managed rollout path.
