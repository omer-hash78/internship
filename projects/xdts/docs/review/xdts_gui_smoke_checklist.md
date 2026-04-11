# XDTS GUI Smoke Checklist

This checklist is the repeatable GUI verification script for the current first-release XDTS build.

## Scope

Use this checklist after:
- major GUI changes
- role/permission changes
- rollout candidate builds
- backup or audit workflow changes

## Preconditions

1. Start with a test database, not the production shared database.
2. Ensure one admin account exists.
3. Ensure at least one operator and one viewer account exist.
4. Ensure at least one document exists for history and transfer checks.

## Launch And Login

1. Run `python projects/xdts/main.py`.
2. Confirm the login form renders.
3. Log in as `admin`.
4. Log out.
5. Log in as `operator`.
6. Log out.
7. Log in as `viewer`.

Expected result:
- login succeeds for valid users
- logout returns to the login screen

## Role Visibility

### Admin
Confirm the dashboard shows:
- `Refresh`
- `View History`
- `Add Document`
- `Transfer`
- `Manage Users`
- `Reports`
- `Verify Audit`
- `Backup`

### Operator
Confirm the dashboard shows:
- `Refresh`
- `View History`
- `Add Document`
- `Transfer`

Confirm the dashboard does not show:
- `Manage Users`
- `Reports`
- `Verify Audit`
- `Backup`

### Viewer
Confirm the dashboard shows:
- `Refresh`
- `View History`

Confirm the dashboard does not show:
- `Add Document`
- `Transfer`
- `Manage Users`
- `Reports`
- `Verify Audit`
- `Backup`

## User Management

Logged in as admin:
1. Open `Manage Users`.
2. Confirm the active-user list renders.
3. Attempt to create a user with mismatched password and confirmation.
4. Confirm XDTS blocks the request.
5. Create a valid viewer account.
6. Select that account and run `Reset Password`.
7. Confirm the reset dialog requires matching passwords.

Expected result:
- mismatched passwords are rejected before create/reset
- valid creation succeeds
- password reset succeeds for the selected account

## Reporting

Logged in as admin:
1. Open `Reports`.
2. Confirm the summary section renders.
3. Confirm grouped tables render for document status, user roles, and history actions.

## Document Workflow

Logged in as admin or operator:
1. Create a document.
2. Confirm it appears in the dashboard.
3. Open history for the new document.
4. Confirm the registration event is visible.
5. Transfer the document with a non-empty reason.
6. Confirm the dashboard updates holder, status, and version.
7. Re-open history and confirm the transfer event is visible.

## Admin Operations

Logged in as admin:
1. Run `Verify Audit`.
2. Confirm success output is shown.
3. Run `Backup`.
4. Confirm the backup success dialog shows a file path.

## Failure Messaging

Confirm these paths are still understandable:
- duplicate document number
- invalid login
- lockout after repeated failed login attempts
- lease conflict
- stale-version conflict
- database unavailable

## Exit Criteria

- no missing role-based actions
- no unauthorized actions exposed to the wrong role
- user-management dialogs validate passwords correctly
- core document workflow completes successfully
- backup and audit flows complete successfully
