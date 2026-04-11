# XDTS First Release Handoff

## Purpose
This document is the handoff summary for the completed first-release XDTS package.

It provides:
- the release scope
- the main verification evidence
- the primary operator and deployment entry points
- the follow-on items that are outside the current first-release scope

## Release Scope

The current XDTS first release includes:
- shared-network SQLite operation with conservative connection settings
- PBKDF2 authentication and persisted cooldown handling
- role-based access control for `admin`, `operator`, and `viewer`
- document registration and transfer
- lease handling and optimistic conflict checks
- append-only audit history with verification
- local workstation operational logging
- admin user management with password reset
- admin summary reporting
- backup through SQLite's backup API
- GUI smoke verification
- folder-based workstation deployment bundle

## Primary Runtime Entry Points

Main GUI:

```powershell
python projects/xdts/main.py
```

Explicit first-admin initialization:

```powershell
python projects/xdts/main.py --initialize-admin --username <admin_name>
```

CLI audit verification:

```powershell
python projects/xdts/main.py --verify-audit --username <admin_name>
```

## Deployment Entry Points

Build the workstation bundle:

```powershell
powershell -ExecutionPolicy Bypass -File projects/xdts/tools/build_workstation_bundle.ps1
```

Bundle launcher scripts:
- `projects/xdts/deploy/launch_xdts.cmd`
- `projects/xdts/deploy/initialize_admin.cmd`
- `projects/xdts/deploy/verify_audit.cmd`
- `projects/xdts/deploy/xdts_runtime.template.cmd`

## Verification Evidence

Automated verification used during the current delivery cycle:
- `python -m compileall projects/xdts`
- `python -m unittest discover -s projects/xdts/tests -v`
- `powershell -ExecutionPolicy Bypass -File projects/xdts/tools/build_workstation_bundle.ps1`

Current automated coverage includes:
- authentication and cooldown
- role enforcement
- duplicate validation
- lease conflicts and lease expiry
- audit-chain compatibility and tamper detection
- backup smoke coverage
- admin reporting snapshot behavior
- GUI role-visibility smoke checks
- GUI user-management password-mismatch validation

Manual verification reference:
- `projects/xdts/docs/review/xdts_gui_smoke_checklist.md`

## Primary Operating Documents

- status tracker: `projects/xdts/docs/review/implementation_plan_03_status.md`
- rollout plan: `projects/xdts/docs/rollout/xdts_rollout_plan.md`
- deployment guide: `projects/xdts/docs/rollout/xdts_deployment_guide.md`
- admin guide: `projects/xdts/docs/rollout/xdts_admin_guide.md`
- user guide: `projects/xdts/docs/rollout/xdts_user_guide.md`
- operator failure guide: `projects/xdts/docs/rollout/xdts_operator_failure_guide.md`
- release notes: `projects/xdts/docs/rollout/xdts_release_notes_first_release.md`

## Delivery Status

For the current first-release interpretation of `implementation_plan-03`:
- no open implementation-plan items remain

This does not mean all future work is closed. It means the accepted first-release package is implemented.

## Follow-On Items Outside First Release

- decide whether the current GUI verification level is sufficient for release or whether broader end-to-end coverage is needed later
- decide whether the department needs MSI packaging, executable bundling, or another managed installer flow
- expand reporting only if the department needs analytics beyond the current operational summary
