# XDTS Administrator Guide

## Purpose
This guide defines the first-release administrative procedures for XDTS.

## Admin Responsibilities

Administrators are responsible for:
- initial admin provisioning
- user account creation and role assignment
- password reset for active accounts
- backup execution and validation
- audit verification
- operational escalation when failures cannot be resolved by normal retry guidance

## Initial Admin Provisioning

Use this procedure only when the shared XDTS database has no active admin account.

Command:

```powershell
python projects/xdts/main.py --initialize-admin --username <admin_name>
```

Procedure:
1. Run the command on an approved workstation.
2. Enter the initial admin password when prompted.
3. Confirm the password when prompted.
4. Verify the console reports that the initial admin account was created.
5. Log in through the GUI using the new credentials.

Rules:
- do not create the initial admin by editing the database directly
- do not store a hard-coded bootstrap password in code or documentation
- do not repeat initialization after an active admin already exists

## Creating User Accounts

Available only to logged-in admins.

Steps:
1. Log in with an admin account.
2. Select `Manage Users`.
3. Review the current active-user list.
4. Enter the new username.
5. Enter a non-empty password.
6. Select the correct role.
7. Select `Create User`.

Validation rules:
- username is required
- password is required
- username must be unique
- role must be one of `admin`, `operator`, or `viewer`

To avoid mistyped account setup:
- enter the password carefully
- confirm the password when the dialog requests it
- if an account is created with the wrong password, use the reset-password workflow below

## Resetting A User Password

Available only to logged-in admins.

Steps:
1. Log in with an admin account.
2. Select `Manage Users`.
3. Select the target user in the active-user list.
4. Select `Reset Password`.
5. Enter the new password.
6. Confirm the new password.
7. Select `Reset Password`.

Expected result:
- the target user can authenticate with the new password
- failed-attempt and cooldown state for that user are cleared

## Role Assignment Guidance

Use these roles intentionally:

- `admin`: for trusted staff who manage accounts, backups, audit checks, and reporting
- `operator`: for staff who register and transfer documents as part of normal work
- `viewer`: for read-only access to the dashboard and history

Do not assign `admin` unless the user needs administrative authority.

## Backup Procedure

Available only to logged-in admins.

GUI steps:
1. Log in as admin.
2. Select `Backup`.
3. Confirm the success message and record the backup path.

Expected result:
- XDTS writes a timestamped SQLite backup file into the configured backup directory
- a local workstation log entry is written for backup success or failure

Operational notes:
- do not back up the live database by copying `xdts.db` directly while it is in use
- use the built-in backup flow or an approved external process based on SQLite backup behavior

## Restore Procedure

Use this procedure only when recovery from a verified backup is required and the rollback owner has approved it.

Procedure:
1. Stop XDTS client write activity against the affected shared database.
2. Confirm which backup file is the approved restore source.
3. Preserve the current production database file before changing anything.
4. Replace the affected database with the approved backup copy during the controlled recovery window.
5. Start XDTS again on one approved workstation.
6. Log in as admin.
7. Confirm document listing, history viewing, and audit verification succeed.
8. Re-open XDTS to normal users only after validation completes.

Do not:
- restore an unverified backup
- overwrite the active database while users are still writing to it
- resume normal operations before audit verification and a basic workflow check complete

## Audit Verification Procedure

Available only to logged-in admins.

GUI steps:
1. Log in as admin.
2. Select `Verify Audit`.
3. Review the result message.

CLI alternative:

```powershell
python projects/xdts/main.py --verify-audit --username <admin_name>
```

Expected result:
- successful verification reports that the audit chain verified successfully
- failed verification identifies the first broken history row

If verification fails:
1. stop write activity
2. preserve the current database
3. collect the local workstation log
4. follow `../operations/xdts_operator_failure_guide.md`

## Reporting

Available only to logged-in admins.

Steps:
1. Log in as admin.
2. Select `Reports`.
3. Review the summary totals and grouped counts.

Current report contents:
- total document count
- active user count
- active lease count
- document totals by status
- active users by role
- history totals by action type

This report is intended as a first-release operational summary, not a full analytics module.

## Recommended First-Release Checks

After deployment or a major change:
1. confirm at least one admin can log in
2. confirm user creation works
3. confirm document registration works
4. confirm transfer and history viewing work
5. run audit verification
6. create and inspect a backup

## Escalation Inputs

When escalating an XDTS issue, collect:
- UTC timestamp
- workstation name
- user role and username if relevant
- exact message shown in the UI
- recent workstation log lines
- whether the issue occurred during login, registration, transfer, backup, or audit verification
