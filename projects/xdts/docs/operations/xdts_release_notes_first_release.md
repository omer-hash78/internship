# XDTS First Release Notes

## Scope
These notes summarize the current first-release XDTS build after remediation and completion of the main functional workflows.

## Included Capabilities

- shared-network SQLite operation using conservative rollback-journal settings
- PBKDF2 password hashing with persisted failed-login tracking and cooldown
- role-based access control for `admin`, `operator`, and `viewer`
- document registration
- document transfer with mandatory reason
- document lease handling and optimistic version conflict checks
- append-only audit history with verification
- local workstation operational logging
- database backup through SQLite backup API
- admin user management with password reset
- admin summary reporting
- workstation deployment bundle with launcher scripts and configuration template

## Important Behavior Changes

- XDTS does not expose a bootstrap admin password in the GUI
- initial admin setup must be done explicitly with `--initialize-admin`
- duplicate username and duplicate document-number failures are treated as validation errors, not database outages
- audit verification supports mixed legacy and current audit hash versions
- viewer permissions are restricted to dashboard refresh and history access

## Known First-Release Limitations

- GUI-level automated testing is still limited
- reporting is operational summary reporting, not ad hoc analytics
- deployment is currently a folder-based bundle, not a managed installer or packaged executable

## Core Commands

Start the GUI:

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
