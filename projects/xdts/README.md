# XDTS

X Documentation Tracing System (XDTS) is a Python desktop application for tracking document custody, transfers, and audit history in a shared operational environment.

The current first release includes:
- Tkinter desktop GUI
- SQLite shared-database support with conservative network-safe settings
- role-based access control for `admin`, `operator`, and `viewer`
- document registration and transfer
- lease-based edit coordination
- append-only audit history with verification
- local workstation logging
- admin user management with password reset
- admin summary reporting
- backup through SQLite's backup API
- folder-based workstation deployment bundle

## Run

Main GUI:

```powershell
python projects/xdts/main.py
```

Initialize the first admin:

```powershell
python projects/xdts/main.py --initialize-admin --username <admin_name>
```

Verify the audit chain:

```powershell
python projects/xdts/main.py --verify-audit --username <admin_name>
```

## Verify

Compile check:

```powershell
python -m compileall projects/xdts
```

Automated tests:

```powershell
python -m unittest discover -s projects/xdts/tests -v
```

Build workstation bundle:

```powershell
powershell -ExecutionPolicy Bypass -File projects/xdts/tools/build_workstation_bundle.ps1
```

## Deployment

Deployment launcher and configuration templates are in:
- `projects/xdts/deploy`

Primary deployment guidance is in:
- `projects/xdts/docs/rollout/xdts_deployment_guide.md`

## Documentation

Start here:
- `projects/xdts/docs/review/xdts_first_release_handoff.md`
- `projects/xdts/docs/review/xdts_system_walkthrough.md`

Core operating docs:
- `projects/xdts/docs/rollout/xdts_admin_guide.md`
- `projects/xdts/docs/rollout/xdts_user_guide.md`
- `projects/xdts/docs/rollout/xdts_operator_failure_guide.md`
- `projects/xdts/docs/rollout/xdts_rollout_plan.md`
- `projects/xdts/docs/rollout/xdts_release_notes_first_release.md`

Verification and status docs:
- `projects/xdts/docs/review/implementation_plan_03_status.md`
- `projects/xdts/docs/review/xdts_gui_smoke_checklist.md`
- `projects/xdts/docs/review/xdts_completed_phase_walkthrough.md`

## Project Structure

- `main.py`: entry point and CLI modes
- `gui.py`: Tkinter UI
- `services.py`: business logic and authorization
- `database.py`: schema, transactions, audit chain, backup
- `auth.py`: password hashing and verification
- `logger.py`: workstation-local rotating log
- `tests/`: automated service and GUI smoke tests
- `deploy/`: launcher scripts and runtime config template
- `tools/`: deployment bundle builder
- `docs/`: review, rollout, and operating documentation
