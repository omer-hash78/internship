# XDTS Review Remediation Plan

## Purpose
This document converts the current XDTS code review findings into an execution plan. The goal is to close the highest-risk gaps first, then harden the implementation so it matches the shared-network SQLite design in `implementation_plan-03`.

## Scope
This review plan covers:
- security defects
- authorization and trust-boundary issues
- audit trail integrity design
- database error handling and operational logging
- rollout and migration planning
- product and operational documentation deliverables
- missing test coverage around critical flows

This plan does not expand the feature scope beyond the approved XDTS implementation plan.

## Companion Documents
- `projects/xdts/docs/rollout/xdts_rollout_plan.md`
- `projects/xdts/docs/review/xdts_completed_phase_walkthrough.md`
- `projects/xdts/docs/rollout/adr-001-initial-admin-provisioning.md`
- `projects/xdts/docs/rollout/adr-002-audit-hash-versioning.md`
- `projects/xdts/docs/rollout/xdts_operator_failure_guide.md`

## Phase Status
- Phase 0: Completed
- Phase 1: Completed
- Phase 2: Completed
- Phase 3: Completed
- Phase 4: Completed
- Phase 5: Completed
- Phase 6: Completed

## Implemented Work Log

### Completed
- Phase 0: product decisions and rollout baseline documents created
- Phase 1: bootstrap credential exposure removed, explicit admin initialization introduced, CLI admin impersonation removed, and service authorization bound to persisted user state
- Phase 2: duplicate-entry and constraint failures now surface as validation errors instead of database-unavailable failures
- Phase 3: audit hash versioning added, new history rows now use canonical hashing, and verification supports both legacy and current audit rows with tamper tests
- Phase 4: service-boundary operational logging now records context-rich database, lease, conflict, backup, startup, and shutdown events, and operator failure guidance was added
- Phase 5: role boundaries now align better with the approved model by keeping `viewer` read-only and limiting GUI actions to the roles that can actually use them
- Phase 6: automated coverage now includes duplicate-entry validation, cooldown enforcement, lease conflict and expiry, permission checks, audit tamper detection, mixed-version verification, and backup smoke coverage

### Remaining
- No open phases remain in this remediation plan

## Review Findings To Address

### 1. Bootstrap admin credentials are unsafe
- The system seeds a fixed `admin / ChangeMe123!` account.
- The login screen displays the seeded credentials.
- This creates a predictable privileged account and leaks credentials to anyone with GUI access.

### 2. Validation failures are reported as database outages
- Duplicate usernames and duplicate document numbers are currently translated into `AvailabilityError`.
- This hides normal business-rule violations behind incorrect operational messaging.

### 3. Authorization trusts in-memory session state too much
- Service authorization currently trusts `SessionUser.role` without re-checking the backing database state.
- The audit CLI path fabricates an admin session instead of authenticating a real actor.

### 4. Audit-chain serialization is ambiguous
- The audit hash payload is currently built by joining fields with `|`.
- This is not a canonical encoding and weakens tamper-evidence guarantees.

### 5. Database/network failures are under-logged
- Failure translation exists, but many failure paths do not log the operation, actor, document, or context.
- This conflicts with the local operational logging goals from the implementation plan.

### 6. Permission boundaries are broader than intended
- `viewer` can currently call `list_users()`.
- That exceeds the approved read-only dashboard/history role boundary.

### 7. Critical test coverage is still thin
- Current tests do not cover duplicate inserts, lock/cooldown behavior, lease expiry, audit-chain break detection, or permission regressions.

## Execution Order

### Phase 0: Product Decisions And Rollout Baseline
Priority: Critical

Tasks:
- Approve the initial admin provisioning model.
- Approve the audit hash compatibility model.
- Define rollout stages, migration guardrails, and rollback rules.
- Define required operator and end-user documentation updates.

Definition of done:
- product decisions are recorded in approved decision documents
- rollout plan exists and includes migration and rollback guidance
- documentation deliverables are named and assigned
- Phase 1 implementation work is not blocked by unresolved product choices

### Phase 1: Security And Trust Boundary Fixes
Priority: Critical

Tasks:
- Remove credential display from the GUI.
- Replace fixed bootstrap credentials with the approved explicit admin provisioning flow.
- Add a guarded initialization command for first admin creation and document its operational use.
- Rework service authorization so each privileged action validates the active user record from the database.
- Remove fabricated admin sessions from CLI paths.

Definition of done:
- No hard-coded privileged password remains in the codebase.
- No UI surface reveals privileged credentials.
- Admin-only actions require a real persisted admin account.
- Disabled or role-changed users lose access without restarting the app.
- provisioning behavior is documented for operators

### Phase 2: Correct Error Semantics
Priority: High

Tasks:
- Stop collapsing all `sqlite3` exceptions into generic database-unavailable errors.
- Preserve integrity/constraint failures so services can translate them into validation messages.
- Distinguish:
  - constraint violations
  - lock/busy conditions
  - database unavailable or path/network failures
  - unexpected database failures
- Add targeted user-facing messages for duplicate usernames, duplicate document numbers, and stale document updates.

Definition of done:
- Duplicate user/document creation returns validation errors, not availability errors.
- Lock errors and network/path failures are still surfaced clearly.
- Unit tests cover each error class.

### Phase 3: Audit Trail Hardening
Priority: High

Tasks:
- Replace the pipe-delimited hash payload with a canonical serialized structure.
- Use a deterministic representation for every field included in the audit hash.
- Review whether the chain should include the history row id or another sequence anchor.
- Expand audit verification to report clearer break diagnostics.

Definition of done:
- Hash computation is canonical and deterministic.
- Verification can detect both chain-link mismatch and record-content mismatch.
- Tests cover successful verification and deliberate tamper detection.
- compatibility with already-written history rows is explicitly handled

### Phase 4: Operational Logging Improvements
Priority: Medium

Tasks:
- Log database/network failures at the service boundary with context.
- Include actor, workstation, operation name, and document id when available.
- Log lock conflicts and lease conflicts separately from availability failures.
- Review startup/shutdown, backup, auth, and audit verification logging for completeness.

Definition of done:
- Important failure paths leave a useful local-machine log record.
- Logs support post-incident reconstruction without exposing raw stack traces to end users.
- operator guidance exists for common failure states

### Phase 5: Role Boundary Cleanup
Priority: Medium

Tasks:
- Restrict `list_users()` to the minimum roles that actually need it.
- Review all service methods for least-privilege alignment with the plan.
- Confirm GUI control visibility matches service-layer authorization.

Definition of done:
- `viewer` permissions are limited to dashboard/history use cases.
- Service-layer authorization is stricter than or equal to GUI affordances.

### Phase 6: Test Expansion
Priority: Medium

Tasks:
- Add tests for duplicate usernames and duplicate document numbers.
- Add cooldown tests after five failed attempts.
- Add lease-conflict and lease-expiry tests.
- Add permission tests for `admin`, `operator`, and `viewer`.
- Add audit-chain tamper tests.
- Add backup-path smoke coverage.

Definition of done:
- Core risk areas from the review are covered by automated tests.
- Tests fail before regression reaches the GUI layer.

## Documentation Deliverables
- initial admin provisioning SOP
- user and role management procedure
- login lockout troubleshooting guide
- duplicate-entry validation guidance
- database unavailable and retry guidance
- backup and restore runbook
- audit verification SOP
- remediation release notes

## Recommended File Targets
- `projects/xdts/services.py`
- `projects/xdts/database.py`
- `projects/xdts/gui.py`
- `projects/xdts/main.py`
- `projects/xdts/tests/test_services.py`

## Suggested Delivery Strategy
1. Finalize product decisions and rollout rules first.
2. Fix security and authorization next.
3. Fix exception taxonomy and validation handling after trust boundaries are corrected.
4. Harden the audit chain with explicit compatibility handling before production rollout.
5. Add tests and documentation updates immediately after each remediation slice, not as a final pass.

## Traceability Expectations
Each completed remediation item should identify:
- the review finding it closes
- the code changes that implement it
- the tests that verify it
- the operator or user documentation updated alongside it

## Acceptance Criteria
- The implementation no longer exposes default privileged credentials.
- Service authorization depends on persisted user state, not only cached session data.
- Constraint violations, lock conditions, and database-unavailable conditions are clearly separated.
- The audit-chain format is canonical and tamper verification is test-covered.
- Operational logs contain enough context to investigate failures on shared-network deployments.
- Role boundaries match the approved XDTS design.
- rollout, migration, and rollback guidance exist for shared-database deployment.
- operator and user-facing documentation is updated for changed behavior.

## Notes
- This plan is intentionally remediation-focused.
- Feature expansion should wait until the trust, audit, and failure-handling foundations are corrected.
