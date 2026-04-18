# XDTS

X Documentation Tracing System (XDTS) is a Python desktop application for tracking document custody, transfers, audit history, and core admin operations in a shared operational environment.

## Current Scope

The current build includes:

- Tkinter desktop GUI
- SQLite shared-database support with conservative network-safe settings
- role-based access control for `admin`, `operator`, and `viewer`
- document registration and transfer with holder-based restrictions
- lease-based edit coordination for transfer operations
- append-only audit history with inline transfer-target visibility
- local workstation logging with an admin log viewer
- admin user management with password reset and user deactivation
- admin summary reporting
- audit-chain verification
- backup through SQLite's backup API
- workstation deployment bundle tooling

## Quick Start

Run the GUI:

```powershell
python projects/xdts/main.py
```

Initialize the first admin:

```powershell
python projects/xdts/main.py --initialize-admin --username <admin_name>
```

Verify the audit chain from the CLI:

```powershell
python projects/xdts/main.py --verify-audit --username <admin_name>
```

## Verification

Compile check:

```powershell
python -m compileall projects/xdts
```

Run automated tests:

```powershell
python -m unittest discover -s projects/xdts/tests -v
```

Validate the PDF pool contract:

```powershell
python projects/xdts/tools/validate_pdf_pool.py --manifest-only
python projects/xdts/tools/validate_pdf_pool.py
```

Build the workstation bundle:

```powershell
powershell -ExecutionPolicy Bypass -File projects/xdts/tools/build_workstation_bundle.ps1
```

## Project Layout

- `main.py`: entry point and CLI modes
- `ui/`: Tkinter application shell and dialogs
- `services/`: business logic, permissions, models, and workflow rules
- `core/`: shared runtime infrastructure such as config, auth, database, and logging
- `tests/`: automated service and GUI coverage
- `deploy/`: launcher scripts and runtime configuration template
- `tools/`: deployment bundle builder
- `pdf_pool/`: future-facing sample PDF files only
- `pdf_pool_meta/`: PDF pool inventory and authoring rules
- `docs/`: rollout, review, user, and operations documentation

## Deployment Notes

- Source deployment scripts and runtime templates are in `deploy/`.
- Built workstation bundle output is created under `dist/xdts-workstation/`.
- For rollout testing and real workstation distribution, use the copied bundle from `dist/`, not the source `deploy/` folder directly.
- Primary deployment guidance is in `docs/operations/xdts_deployment_guide.md`.

## Documentation Guide

Start here:

- `docs/review/xdts_first_release_handoff.md`
- `docs/review/xdts_system_walkthrough.md`

Core operating docs:

- `docs/user/xdts_admin_guide.md`
- `docs/user/xdts_user_guide.md`
- `docs/operations/xdts_operator_failure_guide.md`
- `docs/operations/xdts_rollout_plan.md`
- `docs/operations/xdts_release_notes_first_release.md`

Verification reference:

- `docs/review/xdts_first_release_handoff.md`
- `docs/review/xdts_system_walkthrough.md`

Historical background:

- `docs/archive/README.md`
