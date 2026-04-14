# XDTS Completed Phase Walkthrough

Archived document:
- this file is kept for remediation-history reference only
- the active documentation entry points are `../review/xdts_first_release_handoff.md` and `../review/xdts_system_walkthrough.md`

## Purpose
This walkthrough explains what was implemented in completed XDTS remediation phases, why each change was made, and how the pieces fit together.

This document covers:
- Phase 0: product decisions and rollout baseline
- Phase 1: security and trust-boundary fixes
- Phase 2: error semantics correction
- Phase 3: audit trail hardening
- Phase 4: operational logging improvements
- Phase 5: role-boundary cleanup
- Phase 6: test expansion

## Phase 0 Walkthrough

### Goal
Remove ambiguity before code changes begin.

### What Was Added
- rollout plan for staged deployment, migration validation, pilot rollout, and rollback handling
- initial admin provisioning decision record
- audit hash versioning decision record
- updated review plan with explicit phase tracking

### Why It Matters
The remediation work changes authentication and audit behavior on a shared SQLite database. Those changes are not safe to ship without a clear rollout model and explicit product decisions.

### Output Documents
- `projects/xdts/docs/operations/xdts_rollout_plan.md`

## Phase 1 Walkthrough

### Goal
Remove the unsafe bootstrap-admin design and stop trusting stale in-memory authorization state.

### What Changed

#### 1. Bootstrap credential exposure was removed
The application no longer creates a fixed `admin / ChangeMe123!` account automatically.

Before:
- service startup seeded a hard-coded admin account
- login UI displayed the credentials

After:
- no admin account is created implicitly
- the GUI shows neutral guidance only
- if no admin exists, the operator is directed to the explicit initialization procedure

#### 2. Initial admin provisioning became explicit
The CLI now supports guarded first-admin creation with:
- `python projects/xdts/main.py --initialize-admin --username <name>`

Behavior:
- initialization is allowed only when no active admin exists
- the operator provides the password interactively
- the first admin is written intentionally to the target database

#### 3. CLI audit verification now authenticates a real user
The previous implementation fabricated an admin session for `--verify-audit`.

That was replaced with:
- real username input
- real password prompt
- normal service authentication before audit verification

#### 4. Authorization now checks persisted user state
Service-layer permission checks now re-read the current user from the database.

This closes the gap where:
- a role could be downgraded in the database
- but an old in-memory `SessionUser` still kept elevated access

### Primary Files
- `projects/xdts/main.py`
- `projects/xdts/ui/gui.py`
- `projects/xdts/services/__init__.py`

## Phase 2 Walkthrough

### Goal
Correct the boundary between user validation errors and real infrastructure failures.

### What Changed

#### 1. Integrity errors now stay distinguishable
The database layer now preserves SQLite integrity/constraint violations as their own error category instead of collapsing them into generic availability failures.

#### 2. Duplicate-entry cases now surface as validation errors
The service layer now translates duplicate-key failures into user-meaningful validation messages such as:
- `Username already exists.`
- `Document number already exists.`

### Why It Matters
Before this change, ordinary business-rule violations could appear to users as:
- `Database unavailable. Please retry.`

That was both misleading and operationally harmful, especially in a shared-network deployment where genuine availability failures also matter.

### Primary Files
- `projects/xdts/core/database.py`
- `projects/xdts/services/__init__.py`
- `projects/xdts/tests/test_services.py`

## Phase 3 Walkthrough

### Goal
Strengthen the audit chain without rewriting historical evidence.

### What Changed

#### 1. Audit hash versioning was introduced
History rows now support explicit audit-hash versions:
- version 1 for legacy rows
- version 2 for new canonical rows

#### 2. New audit hashes use canonical structured serialization
New history records no longer hash a pipe-delimited payload.

Instead:
- the hash input is built from a structured payload
- the payload is serialized deterministically
- the result is less ambiguous and more defensible

#### 3. Verification supports mixed-version chains
Audit verification now:
- recalculates legacy rows with the old method
- recalculates new rows with the canonical method
- validates the whole chain in order

This allows migration forward without rewriting older audit rows.

#### 4. Tamper detection is test-covered
The verification suite now includes:
- mixed legacy/current chain coverage
- deliberate tamper detection coverage

### Why It Matters
The audit trail is central to XDTS. A stronger future format is useful only if the system can still explain and verify already-written records.

### Primary Files
- `projects/xdts/core/database.py`
- `projects/xdts/services/__init__.py`
- `projects/xdts/tests/test_services.py`

## Phase 4 Walkthrough

### Goal
Make workstation logs useful for operators investigating shared-database failures and multi-user workflow issues.

### What Changed

#### 1. Service-boundary failure logging was standardized
Database failures are now logged with operation context before user-facing exceptions are returned.

Logged context now includes fields such as:
- operation
- actor
- actor_id
- document_id
- workstation
- error_type
- user_message

#### 2. Lock, availability, lease, and state conflicts are logged separately
The service layer now distinguishes:
- `database_unavailable`
- `database_lock_failure`
- `database_operation_failed`
- `lease_conflict`
- `state_conflict`

That separation makes the workstation logs more useful during support and post-incident review.

#### 3. Startup and shutdown are logged explicitly
The application entry point now records startup and shutdown events so the local log has clearer session boundaries.

#### 4. Operator failure guidance was documented
An operator-facing guide was added for:
- no-admin-configured state
- database unavailable failures
- database lock/busy conditions
- lease conflicts
- stale state conflicts
- duplicate-entry validation messages
- lockout handling
- audit verification failures

### Why It Matters
Before this phase, many failures either were not logged with enough context or were scattered across inconsistent message styles. In a shared-network SQLite deployment, failure interpretation is part of the product, not just a debugging detail.

### Primary Files
- `projects/xdts/services/__init__.py`
- `projects/xdts/main.py`
- `projects/xdts/tests/test_services.py`
- `projects/xdts/docs/operations/xdts_operator_failure_guide.md`

## Phase 5 Walkthrough

### Goal
Bring role behavior closer to the approved XDTS permission model in both the service layer and the GUI.

### What Changed

#### 1. `viewer` no longer enumerates users
The service-layer `list_users()` operation is now limited to:
- `admin`
- `operator`

That keeps `viewer` aligned with the intended read-only dashboard/history role.

#### 2. GUI actions now match role affordances more closely
The dashboard no longer shows the same action set to every user.

Current behavior:
- `viewer`: refresh and history only
- `operator`: refresh, history, add document, transfer
- `admin`: all of the above plus audit verification and backup

#### 3. GUI handlers now reject out-of-role access earlier
The transfer, backup, and audit actions now fail fast in the UI if triggered outside their allowed roles.

### Why It Matters
Service-level enforcement is mandatory, but the GUI should not advertise actions that a given role cannot actually perform. Hiding those controls reduces operator confusion and narrows accidental misuse.

### Primary Files
- `projects/xdts/services/__init__.py`
- `projects/xdts/ui/gui.py`
- `projects/xdts/tests/test_services.py`

## Phase 6 Walkthrough

### Goal
Close the highest-value automated test gaps called out in the remediation plan.

### What Changed

#### 1. Authentication and cooldown coverage expanded
The suite now verifies that:
- repeated failed logins increment failure tracking
- cooldown activates after five failed attempts
- correct credentials still remain blocked until cooldown expires

#### 2. Lease behavior coverage expanded
The suite now covers:
- lease conflicts between users
- expired lease rejection during transfer attempts

#### 3. Permission coverage expanded
The suite now verifies:
- operator access to user lookup where required
- viewer rejection from user enumeration
- persisted role changes overriding stale session assumptions

#### 4. Backup coverage expanded
The suite now confirms:
- backup creation succeeds
- the returned backup path exists on disk

### Why It Matters
These tests move more of the remediation risk out of manual validation and into repeatable automated checks.

### Primary Files
- `projects/xdts/tests/test_services.py`

## Verification Performed
- `python -m compileall projects/xdts`
- `python -m unittest discover -s projects/xdts/tests -v`

Current automated coverage includes:
- explicit admin initialization
- authenticated audit verification
- persisted-role authorization checks
- duplicate username validation
- duplicate document-number validation
- mixed-version audit verification
- tamper detection
- database-unavailable logging context
- lease-conflict logging context
- cooldown enforcement after repeated failed login
- lease-expiry rejection
- viewer/operator permission checks
- backup creation smoke coverage

## Remaining Work
Open phases:
- No open phases remain in the current remediation plan

## Recommended Reader Order
1. Read `../review/xdts_first_release_handoff.md` for the active package summary.
2. Read `../review/xdts_system_walkthrough.md` for the active current-system explanation.
3. Read `../operations/xdts_rollout_plan.md` for deployment expectations.
4. Read this walkthrough only if you need remediation history.
