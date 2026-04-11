# XDTS System Walkthrough

## Purpose
This document explains the completed XDTS first-release system as a whole.

It focuses on:
- what is implemented
- how the major files fit together
- how the runtime, database, GUI, and operational flows work
- how administrators and operators are expected to use the system

This is the best single document to read if you want to understand the current implemented XDTS package end to end.

## 1. What XDTS Is

XDTS is a desktop application for tracking document custody and document movement in a shared operational environment.

At a system level, it answers:
- who acted
- what they did
- which document they touched
- when they did it
- from which workstation the action occurred

The current first release implements:
- Tkinter desktop GUI
- SQLite database on a shared network path
- local workstation logging
- role-based access control
- document registration and transfer
- append-only audit history
- audit-chain verification
- lease-based multi-user coordination
- backup using SQLite's backup API
- admin user management and operational reporting

## 2. High-Level Architecture

The runtime is intentionally split into a few focused modules.

### `main.py`
This is the application entry point.

It is responsible for:
- reading command-line arguments
- building the workstation logger
- creating the database manager
- constructing the service layer
- launching the GUI
- supporting the CLI-only admin initialization flow
- supporting the CLI-only audit verification flow

### `gui.py`
This is the Tkinter presentation layer.

It is responsible for:
- login screen
- dashboard rendering
- role-based action visibility
- document registration dialog
- transfer dialog
- history viewer
- admin user-management dialog
- admin reporting dialog
- user-facing error presentation

The GUI does not make final permission decisions. It hides or blocks actions early for usability, but the real authorization boundary remains in the service layer.

### `services.py`
This is the business logic layer.

It is responsible for:
- authentication
- cooldown and failed-login handling
- role checks
- user creation and password reset
- document registration
- document transfer
- lease acquisition and release
- optimistic conflict checking
- history retrieval
- audit verification
- backup orchestration
- reporting
- translation of low-level database failures into product-level errors

This file is the main policy engine of XDTS.

### `database.py`
This is the database and persistence layer.

It is responsible for:
- SQLite connection configuration
- schema creation
- runtime migrations
- transaction helpers
- audit hash generation
- history insertion
- audit-chain verification
- lease cleanup
- backup execution
- error classification

### `auth.py`
This file handles password hashing and verification using the standard library only.

It uses:
- random per-user salts
- `hashlib.pbkdf2_hmac`
- stored algorithm and iteration metadata

### `logger.py`
This file builds the local rotating workstation log.

It provides:
- UTC timestamps
- rotating file output
- workstation-local log storage

## 3. Runtime Modes

XDTS runs in three main modes.

### GUI mode

```powershell
python projects/xdts/main.py
```

This is the normal day-to-day operating mode.

### Initial admin provisioning mode

```powershell
python projects/xdts/main.py --initialize-admin --username <admin_name>
```

This is used only when the target database has no active admin account.

It is intentionally outside the GUI so the system does not rely on a default bootstrap password.

### Audit verification mode

```powershell
python projects/xdts/main.py --verify-audit --username <admin_name>
```

This performs authenticated CLI audit verification.

The CLI path authenticates a real user rather than fabricating an admin session.

## 4. Database Model

The current schema is centered on four tables.

### `users`
Stores:
- username
- password hash and salt
- password algorithm metadata
- password iteration count
- role
- failed-attempt count
- cooldown-until timestamp
- active/inactive state
- creation timestamp

### `documents`
Stores:
- document number
- title
- description
- current status
- current holder
- creator
- optimistic locking version
- created and updated timestamps

### `history`
Stores append-only audit events with:
- document id
- actor user id
- action type
- previous state
- new state
- state version
- workstation name
- optional IP address
- reason
- UTC timestamp
- previous chain hash
- current record hash
- audit hash version

### `document_leases`
Stores short-lived edit leases with:
- document id
- user id
- workstation name
- lease start timestamp
- lease expiry timestamp

## 5. Shared SQLite Strategy

The implementation assumes the database file is on a shared network location.

Because of that, the database layer is conservative by design.

Current behavior includes:
- rollback-journal mode instead of WAL
- foreign keys enabled
- busy timeout configured
- explicit transactions for writes
- short write scopes
- lock failures surfaced as retryable availability-style errors

This is not a general-purpose high-concurrency database design. It is a pragmatic shared-SQLite desktop design aimed at predictable operator behavior.

## 6. Authentication And User State

### Passwords
Passwords are never stored directly.

Each user gets:
- a random salt
- a PBKDF2-derived hash
- stored algorithm metadata
- stored iteration metadata

### Failed login tracking
Each failed login increments the user’s failed-attempt count.

After 5 failed attempts:
- the account is locked
- the cooldown lasts 1 hour
- the cooldown state is stored in the database

That means the lockout survives application restarts.

### Active-user enforcement
Service authorization checks do not trust the session object alone.

Before permission-sensitive actions, XDTS re-reads the user from the database and confirms:
- the account is still active
- the current persisted role is still authorized

That prevents stale in-memory privilege from surviving an admin-side role change.

## 7. Roles And Permissions

The first release supports three roles.

### `admin`
Can:
- manage users
- reset passwords
- register documents
- transfer documents
- view history
- verify the audit chain
- create backups
- view reports

### `operator`
Can:
- register documents
- transfer documents
- view history
- list users when needed for holder selection

### `viewer`
Can:
- refresh the dashboard
- view history

Cannot:
- transfer documents
- register documents
- list users
- access admin tools

## 8. Login And Startup Flow

The normal runtime sequence is:

1. `main.py` parses arguments.
2. `logger.py` creates or reuses the local rotating log.
3. `database.py` initializes schema and runtime migrations.
4. `services.py` is constructed.
5. `gui.py` launches the login screen.

On the login screen:
- the system checks whether an active admin exists
- if not, the UI gives neutral guidance to use the explicit admin initialization command
- no credential disclosure is shown

When a user logs in:
1. expired leases are cleaned
2. the user is looked up
3. cooldown is checked
4. password verification is performed
5. failed-attempt state is reset on success
6. a `SessionUser` is returned to the GUI

## 9. Dashboard And GUI Behavior

After successful login, the dashboard is built from the current user role.

### Shared dashboard behavior
All roles get:
- `Refresh`
- `View History`

### Operator/admin actions
`admin` and `operator` also get:
- `Add Document`
- `Transfer`

### Admin-only actions
`admin` also gets:
- `Manage Users`
- `Reports`
- `Verify Audit`
- `Backup`

The dashboard table shows:
- document number
- title
- status
- current holder
- version
- active lease summary
- updated timestamp

Refresh re-queries the database rather than relying on cached local state.

## 10. User Management

User management is implemented as an admin-only GUI flow backed by service-layer authorization.

### Create user
The admin dialog allows:
- viewing active users
- creating new accounts

Creation requires:
- username
- password
- password confirmation
- valid role

The GUI blocks mismatched password confirmation before calling the service layer.
The service layer independently validates:
- username required
- password required
- role validity
- uniqueness of username

### Reset password
Admins can select an active user and run password reset.

Password reset:
- requires a selected user
- requires a new password plus confirmation in the GUI
- re-hashes the password in the service layer
- clears failed-attempt and cooldown state

## 11. Document Registration Flow

Document registration is available to `admin` and `operator`.

The registration flow is:

1. GUI opens the add-document dialog.
2. GUI loads eligible active users for holder selection.
3. The service validates required fields and status.
4. A document row is inserted with version `1`.
5. A matching `DOCUMENT_REGISTERED` history record is inserted in the same transaction.

This pairing is important: state change and audit record are committed together.

## 12. Document Transfer Flow

Document transfer is the most concurrency-sensitive path in the system.

The transfer sequence is:

1. The user selects a document.
2. The GUI asks the service to acquire a lease.
3. The transfer dialog opens.
4. The user chooses the new holder, optional new status, and a required reason.
5. On submit, the service starts a transaction.
6. Expired leases are cleaned.
7. The current document row is re-read.
8. The expected version is compared to the live version.
9. The target holder is validated.
10. The active lease is checked again.
11. The document is updated with the new holder/status/version.
12. A `DOCUMENT_TRANSFERRED` history row is written.
13. The lease is deleted.

If the dialog is closed without completing the transfer, the GUI attempts to release the lease.

## 13. Lease Model And Conflict Handling

XDTS uses leases plus optimistic locking.

These solve different problems.

### Lease
The lease is a short-lived indicator that a user/workstation is actively editing a document.

It helps:
- reduce simultaneous editing
- show who currently holds the edit window
- block obvious collisions early

### Optimistic version check
The document version check prevents stale overwrites.

Even if a lease existed earlier, the service still verifies that:
- the document version currently in the database
- matches the version the user originally opened

If not, the service raises a conflict and blocks the write.

### Why both exist
Leases improve coordination.
Version checks protect correctness.

The system intentionally uses both.

## 14. Audit History And Tamper Evidence

Every state-changing document action writes a history record.

The history system has two major protection layers.

### Append-only enforcement
The database defines triggers that reject:
- `UPDATE` on `history`
- `DELETE` on `history`

So the application and the database both treat history as append-only.

### Hash-chained records
Each history row stores:
- the previous record hash
- its own record hash

The current record hash is computed from:
- the current row content
- the previous chain hash

That creates a tamper-evident chain.

### Audit hash versioning
The system supports:
- legacy version 1 hashes
- current version 2 canonical hashes

Verification walks the full chain in order and recalculates each row using the appropriate versioned algorithm.

That means the system can preserve and verify older rows without rewriting them.

## 15. Reporting

Admins can open the reporting dialog from the dashboard.

The current reporting surface is intentionally lightweight.

It provides:
- total document count
- active user count
- active lease count
- documents grouped by status
- active users grouped by role
- history grouped by action type

The service computes the report inside a single read transaction so the summary is taken from one consistent snapshot.

This is operational reporting, not a general analytics module.

## 16. Backup Behavior

Backup is admin-only.

The system does not back up the live database by copying the SQLite file directly.

Instead:
- `database.py` uses SQLite’s backup API
- backups are written to timestamped `.db` files
- the backup result is logged locally

That approach is safer than raw file copying while the database is in use.

## 17. Logging And Failure Handling

Logs are stored locally on each workstation, not on the shared database location.

The logger uses:
- UTC timestamps
- rotating files
- a fixed application log name

The service layer logs:
- startup and shutdown context
- successful logins
- failed logins and lockouts
- lease conflicts
- stale-state conflicts
- database unavailable conditions
- database lock conditions
- backup activity
- audit verification results

Database failures are translated into user-facing categories instead of raw SQLite exceptions.

Important user-facing classes include:
- validation errors
- authentication errors
- lease errors
- conflict errors
- availability errors

## 18. Verification And Test Coverage

The current verification stack has three layers.

### Static/load verification

```powershell
python -m compileall projects/xdts
```

This checks import and syntax viability across the project.

### Automated unit and smoke tests

```powershell
python -m unittest discover -s projects/xdts/tests -v
```

Current coverage includes:
- admin initialization
- authentication and cooldown
- duplicate validation
- role enforcement
- password reset
- document registration and transfer
- lease conflicts and lease expiry
- audit compatibility and tamper detection
- reporting snapshot consistency
- backup creation
- GUI role visibility smoke checks
- GUI validation smoke checks

### Manual GUI smoke checklist
The manual validation script is:
- `projects/xdts/docs/review/xdts_gui_smoke_checklist.md`

This is the repeatable operator-facing GUI verification reference for release candidates and rollout builds.

## 19. Deployment Model

The current first-release deployment model is a folder-based workstation bundle.

That model includes:
- application Python files
- launch scripts
- runtime configuration template
- rollout and operating documentation

Deployment artifacts now live under:
- `projects/xdts/deploy`
- `projects/xdts/tools`

### Launchers
The deployment folder provides:
- `launch_xdts.cmd`
- `initialize_admin.cmd`
- `verify_audit.cmd`
- `xdts_runtime.template.cmd`

### Bundle builder
The PowerShell bundling script is:

```powershell
powershell -ExecutionPolicy Bypass -File projects/xdts/tools/build_workstation_bundle.ps1
```

This produces a workstation bundle under `projects/xdts/dist/xdts-workstation`.

### Deployment guidance
Operational deployment instructions are documented in:
- `projects/xdts/docs/operations/xdts_deployment_guide.md`

The current deployment model is deliberately simple.
It does not yet include:
- MSI packaging
- executable bundling
- auto-updates

## 20. How The Documentation Set Fits Together

The current XDTS documentation set has distinct roles.

### Review/completion documents
- `xdts_first_release_handoff.md`: top-level handoff summary
- `xdts_system_walkthrough.md`: full current-system explanation
- `xdts_gui_smoke_checklist.md`: repeatable GUI smoke script

### Archived historical documents
- `docs/archive/implementation_plan_03_status.md`: old completion tracker
- `docs/archive/xdts_completed_phase_walkthrough.md`: remediation history and rationale

### Rollout and operations documents
- `xdts_rollout_plan.md`: rollout sequencing and gates
- `xdts_deployment_guide.md`: workstation deployment procedure
- `xdts_operator_failure_guide.md`: failure handling
- `xdts_release_notes_first_release.md`: first-release summary

### User-facing documents
- `xdts_admin_guide.md`: admin procedures
- `xdts_user_guide.md`: normal user workflow

## 21. Current State

For the current first-release interpretation of the implementation plan:
- the implemented system is complete
- the repo contains runtime code, test coverage, rollout guidance, and deployment artifacts

The main remaining work is not missing first-release functionality.
It is future scope choice, such as:
- richer end-to-end UI testing
- managed installer packaging
- broader reporting

## Recommended Reading Order

1. Read `xdts_first_release_handoff.md` for the short package summary.
2. Read this document for the complete current-system explanation.
3. Read `xdts_deployment_guide.md`, `xdts_admin_guide.md`, and `xdts_user_guide.md` for operating procedures.
4. Read `docs/archive/README.md` if you need historical implementation background.
