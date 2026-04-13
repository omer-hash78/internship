# XDTS First Release Handoff

## Purpose

This document is the handoff summary for the completed first-release XDTS package.

It is intended to give the next reviewer, operator, or maintainer a short, reliable entry point for:

- current release scope
- runtime and deployment entry points
- verification evidence used for the delivery
- primary operating documents
- follow-on items that remain outside first-release scope

## Release Scope

The current XDTS first release includes:

- shared-network SQLite operation with conservative connection settings
- PBKDF2 authentication with persisted failed-login cooldown handling
- role-based access control for `admin`, `operator`, and `viewer`
- document registration and transfer with holder-based restrictions
- lease-based edit coordination with optimistic version conflict checks
- append-only audit history with verification
- history entries that show transfer targets inline
- local workstation operational logging with an admin log viewer
- admin user management with password reset and user deactivation
- admin summary reporting
- backup through SQLite's backup API
- GUI smoke verification coverage
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

Source deployment templates:

- `projects/xdts/deploy/launch_xdts.cmd`
- `projects/xdts/deploy/initialize_admin.cmd`
- `projects/xdts/deploy/verify_audit.cmd`
- `projects/xdts/deploy/xdts_runtime.template.cmd`

Built workstation bundle output:

- `projects/xdts/dist/xdts-workstation`

Operational notes:

- distribute the built bundle from `dist`
- configure `xdts_runtime.cmd` inside each copied workstation bundle
- point all active workstations at the same shared production `xdts.db`
- keep logs and backups local to each workstation

## Verification Evidence

Automated verification used during the current delivery cycle:

- `python -m compileall projects/xdts`
- `python -m unittest discover -s projects/xdts/tests -v`
- `powershell -ExecutionPolicy Bypass -File projects/xdts/tools/build_workstation_bundle.ps1`

Current automated coverage includes:

- authentication and cooldown handling
- role enforcement and authorization boundaries
- duplicate validation for users and documents
- lease conflict and lease expiry behavior
- transfer restrictions tied to document holder ownership
- audit-chain compatibility and tamper detection
- backup smoke coverage
- admin reporting snapshot behavior
- GUI role-visibility checks
- GUI user-management validation and deactivation flow
- GUI history rendering for inline transfer target visibility

Manual verification should follow:

- `projects/xdts/docs/operations/xdts_deployment_guide.md`
- `projects/xdts/docs/user/xdts_admin_guide.md`
- `projects/xdts/docs/user/xdts_user_guide.md`

## Primary Operating Documents

- system walkthrough: `projects/xdts/docs/review/xdts_system_walkthrough.md`
- rollout plan: `projects/xdts/docs/operations/xdts_rollout_plan.md`
- deployment guide: `projects/xdts/docs/operations/xdts_deployment_guide.md`
- admin guide: `projects/xdts/docs/user/xdts_admin_guide.md`
- user guide: `projects/xdts/docs/user/xdts_user_guide.md`
- operator failure guide: `projects/xdts/docs/operations/xdts_operator_failure_guide.md`
- release notes: `projects/xdts/docs/operations/xdts_release_notes_first_release.md`
- archive index: `projects/xdts/docs/archive/README.md`

## Delivery Status

For the current first-release interpretation of `implementation_plan-03`:

- no open accepted implementation items remain in the first-release package

That does not mean all future work is closed. It means the agreed first-release scope has been implemented and verified to the current release standard.

## Follow-On Items Outside First Release

- decide whether the current GUI and smoke-test level is sufficient or whether broader end-to-end automation is needed later
- decide whether the deployment model should remain a folder-based bundle or move to MSI, executable packaging, or another managed installer flow
- expand reporting only if the department needs analytics beyond the current operational summary
