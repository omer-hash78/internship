# XDTS User Guide

## Purpose
This guide explains how XDTS is used in normal day-to-day work after the first-release remediation build.

## Roles

- `admin`: can manage users, register documents, transfer documents, view history, run audit verification, create backups, and view reports
- `operator`: can register documents, transfer documents, and view history
- `viewer`: can refresh the dashboard and view history only

If the visible actions in the application do not match your assigned role, contact the XDTS administrator.

## Starting The Application

Run the desktop client:

```powershell
python projects/xdts/main.py
```

If the login page says no active admin account is configured, stop normal use and follow the admin setup procedure in `xdts_admin_guide.md`.

## Logging In

1. Enter your assigned username.
2. Enter your password.
3. Select `Login`.

If login fails:
- verify the username is correct
- verify the password is correct
- do not keep retrying if you are unsure of the password

After 5 failed attempts, the account is locked for 1 hour.

## Dashboard

The main dashboard shows:
- document number
- title
- current status
- current holder
- state version
- active lease information
- last update timestamp in `UTC+03:00`

Use `Refresh` whenever you need the latest shared-database state.

## Viewing History

1. Select a document in the dashboard.
2. Select `View History`.

The history view shows:
- timestamp in `UTC+03:00`
- actor username
- action type
- state version
- reason
- workstation name

If no document is selected, XDTS will block the action.

## Registering A Document

Available to:
- `admin`
- `operator`

Steps:
1. Select `Add Document`.
2. Enter the document number.
3. Enter the title.
4. Enter the description.
5. Choose the initial status.
6. Choose the current holder.
7. Select `Create`.

Rules:
- document number is required
- title is required
- document number must be unique

Expected result:
- the document appears in the dashboard
- the action is written to history as `DOCUMENT_REGISTERED`

## Transferring A Document

Available to:
- `admin`
- `operator`

Steps:
1. Select a document in the dashboard.
2. Select `Transfer`.
3. Choose the new holder.
4. Choose the new status if the state should change.
5. Enter a non-empty transfer reason.
6. Select `Transfer`.

Rules:
- a valid lease is required
- the document must still be on the same state version that was loaded
- the reason field is mandatory

Expected result:
- the document holder or status changes
- the state version increments
- the transfer is written to history as `DOCUMENT_TRANSFERRED`

## Common Messages

### `Document changed since it was loaded. Refresh and retry.`
- another user changed the document first
- refresh the dashboard and confirm the latest state before retrying

### `Document is currently leased ...`
- another user or workstation is currently editing the document
- wait for the lease to expire or the other user to finish

### `Document lease expired. Reopen transfer and retry.`
- the transfer dialog stayed open too long
- reopen the transfer flow from the dashboard

### `Document number already exists.`
- the requested identifier is already in use
- correct the value before retrying

### Password reset
- if an account was created with the wrong password, contact an XDTS admin
- admins can reset active-user passwords from `Manage Users`

### `Database unavailable. Please retry.`
- the shared database path may be unreachable
- retry once after a short delay, then escalate with the workstation log if it continues

## Good Operating Habits

- refresh before starting a sensitive action if the dashboard has been open for a while
- complete transfers promptly after opening them
- use specific transfer reasons that explain why custody changed
- do not edit the SQLite database file directly
- do not rely on stale dashboard data during shared use
