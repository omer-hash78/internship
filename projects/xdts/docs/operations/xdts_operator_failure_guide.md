# XDTS Operator Failure Guide

## Purpose
This guide explains the most important XDTS failure states that operators may encounter after the remediation rollout and how to respond to them safely.

## Principles
- Do not retry blindly if the same failure repeats.
- Do not edit the SQLite database file manually.
- Prefer documented recovery steps over ad hoc fixes.
- If audit verification fails, stop write activity until the issue is understood.
- Keep workstation logs and backups local; do not redirect them into the shared database folder.
- Treat the audit chain as tamper-evident, not tamper-proof; filesystem protection around the shared database still matters.

## Common Failure States

### 1. No Active Admin Account Is Configured
What users see:
- the login screen indicates that no active admin account is configured

What it means:
- the shared database does not currently contain an active admin account

What to do:
1. Run the approved initialization procedure.
2. Use the guarded provisioning command:
   `python projects/xdts/main.py --initialize-admin --username <admin_name>`
3. Store the chosen credentials according to department policy.
4. Retry normal login after initialization completes.

Do not:
- add a user directly in the database file
- modify application code to restore a bootstrap password

### 2. Database Unavailable. Please Retry.
What users see:
- `Database unavailable. Please retry.`

What it usually means:
- the shared database path is temporarily unreachable
- the file may be unavailable on the network share
- the database may be opened in a way the application cannot use safely

What to do:
1. Confirm the network location is reachable.
2. Confirm the database file path is correct for the deployed client.
3. Wait briefly and retry once.
4. If the problem continues, check the local XDTS log on the workstation for the operation name and failure context.
5. Escalate with the log excerpt and timestamp.

Do not:
- copy over the active database file while users are working
- assume a duplicate-entry validation problem is the same as a network outage

### 3. Database Is Busy. Please Retry.
What users see:
- `Database is busy. Please retry.`

What it means:
- SQLite encountered a lock and the operation did not complete inside the busy timeout

What to do:
1. Wait a few seconds.
2. Retry the same operation once.
3. If it repeats, ask other users whether a long-running operation is in progress.
4. Review the workstation log for `database_lock_failure`.

### 4. Document Is Currently Leased
What users see:
- the transfer or edit-related action reports that another user/workstation currently holds the lease

What it means:
- another user is actively working on the document
- or a short-lived lease has not expired yet

What to do:
1. Wait until the lease expires or the other user finishes.
2. Wait for the dashboard to refresh automatically or use `Refresh` if needed.
3. If the lease appears stale, verify the timestamp in the UI or logs before escalating.

### 5. Document Changed Since It Was Loaded
What users see:
- `Document changed since it was loaded. Refresh and retry.`

What it means:
- another write changed the document state before the current transfer completed

What to do:
1. Refresh the dashboard.
2. Review the current holder, status, and lease state.
3. Re-run the action only after confirming the latest state is still valid.

### 6. Username Already Exists / Document Number Already Exists
What users see:
- `Username already exists.`
- `Document number already exists.`

What it means:
- the request violated a uniqueness rule

What to do:
1. Search existing users or documents first.
2. Correct the requested username or document number.
3. Retry only with the corrected value.

Do not:
- treat this as a database outage
- create near-duplicate identifiers without checking naming rules

### 7. Account Locked Until <timestamp>
What users see:
- `Account locked until <timestamp>.`

What it means:
- the login cooldown threshold was reached after repeated failed login attempts

What to do:
1. Stop retrying with the same unknown password.
2. Confirm the correct username is being used.
3. Wait until the cooldown expires or follow the department credential recovery process.
4. Review the local log for recent authentication failures if investigation is needed.

### 8. Audit Verification Failed
What users see:
- audit verification reports the first broken history row

What it means:
- the history chain did not verify cleanly
- the issue could be caused by tampering, corruption, or an implementation defect

What to do:
1. Stop write activity against the affected database until the issue is reviewed.
2. Preserve the current database state.
3. Collect the verification output and workstation log.
4. Escalate immediately to the engineering/operations owner.

Do not:
- delete history rows
- recompute hashes manually
- continue normal write activity before review

## Where To Look For Evidence
- local workstation log file: `projects/xdts/logs/xdts.log` or the deployed workstation log directory
- runtime privacy/refresh settings: `deploy\xdts_runtime.cmd`
- key logged fields:
  - `operation`
  - `actor`
  - `document_id`
  - `workstation`
  - `error_type`
  - `user_message`

## Escalation Package
When escalating, include:
- timestamp in `UTC+03:00` if available
- workstation name
- exact error message shown to the user
- last action attempted
- relevant log lines from the workstation
