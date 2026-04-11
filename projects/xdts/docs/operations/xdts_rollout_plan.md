# XDTS Rollout And Migration Plan

## Purpose
This document defines how XDTS review remediations will be introduced without breaking shared-database use, operator workflows, or audit expectations.

## Scope
This rollout plan covers:
- remediation release sequencing
- shared SQLite migration handling
- operator communication and training
- pilot and production rollout gates
- rollback expectations

This document assumes the remediation work described in:
- `projects/xdts/docs/review/xdts_completed_phase_walkthrough.md`
- `projects/xdts/docs/review/implementation_plan_03_status.md`

## Release Strategy

### Release Model
Use a staged rollout rather than replacing all XDTS clients at once.

Stages:
1. Development remediation build
2. Migration validation build against copied test databases
3. Pilot rollout to a small operator/admin group
4. Full deployment to the department

### Why Staged Rollout Is Required
- The database is shared across clients.
- The remediation changes touch authentication, authorization, audit verification, and operational logging.
- A single incorrect rollout could lock out users or invalidate trust in the audit trail.

## Product Decisions Locked For Rollout

### Initial Admin Provisioning
Initial admin setup will not happen automatically in the GUI.

Chosen model:
- explicit admin provisioning command
- no hard-coded bootstrap password
- no credential display in the GUI

### Audit Hash Compatibility
Audit hash remediation must preserve verification of already-written history rows.

Chosen model:
- audit hash versioning
- migration without rewriting historical audit rows
- mixed-version verification support during the transition period

## Deployment Preconditions

Before pilot rollout:
- review remediation code is merged
- automated tests for auth, permissions, duplicate validation, leases, and audit verification are passing
- migration behavior has been tested on a copied database
- operator-facing documentation has been updated
- backup and restore procedure has been rehearsed

Before full rollout:
- pilot issues are closed
- admin provisioning procedure has been validated by a non-developer operator
- support contacts and escalation path are documented

## Migration Strategy

### Database Principles
- Never upgrade the production shared database before taking a verified backup.
- Never rewrite historical audit rows to fit the new hash format.
- Prefer additive schema changes over destructive rewrites.

### Expected Migration Work
- add metadata needed for schema and audit version tracking
- add any new columns required for audit-version compatibility
- preserve existing history rows as written
- mark new rows with the new audit hash version

### Migration Validation
For each migration rehearsal:
1. Copy the target database to a test location.
2. Run the migration on the copied database.
3. Run audit verification.
4. Confirm login, document listing, document transfer, and history viewing still work.
5. Confirm duplicate-entry and lockout flows return correct messages.

### Mixed-Client Risk
Do not allow old and new client builds to write to the same shared database after the audit/version migration point unless compatibility has been explicitly validated.

Operational rule:
- once the production database is migrated, deploy only the approved remediation build to all active users

## Rollout Waves

### Wave 1: Internal Validation
Audience:
- developer
- reviewer

Goals:
- confirm remediation behavior
- confirm logs and user messages
- confirm docs are accurate
- run the GUI smoke checklist: `projects/xdts/docs/review/xdts_gui_smoke_checklist.md`

Exit criteria:
- automated tests pass
- migration rehearsal succeeds
- no open critical defects

### Wave 2: Pilot
Audience:
- one admin
- one or two operators
- optional viewer if available

Goals:
- validate real workflow fit
- validate first-run admin provisioning SOP
- validate support messaging for lockout, duplicate entry, and database-unavailable scenarios

Exit criteria:
- pilot users can complete their normal tasks
- no unexplained access regressions
- no audit verification failures
- feedback is incorporated into docs and UI text

### Wave 3: Full Department Rollout
Audience:
- all XDTS users

Goals:
- transition all active clients to the remediation build
- remove legacy operating assumptions from team guidance

Exit criteria:
- all supported clients are on the approved version
- admin provisioning and backup procedures are documented
- support team acknowledges handoff

## User And Operator Documentation Deliverables

The following documents must be updated or created before full rollout:
- initial admin provisioning procedure: `projects/xdts/docs/user/xdts_admin_guide.md`
- user account creation and role assignment procedure: `projects/xdts/docs/user/xdts_admin_guide.md`
- password reset procedure: `projects/xdts/docs/user/xdts_admin_guide.md`
- login lockout troubleshooting guide
- duplicate document/duplicate username message guidance
- database unavailable and retry guidance
- backup and restore runbook: `projects/xdts/docs/user/xdts_admin_guide.md`
- audit verification SOP: `projects/xdts/docs/user/xdts_admin_guide.md`
- release notes summarizing changed behavior: `projects/xdts/docs/operations/xdts_release_notes_first_release.md`
- operator failure guide: `projects/xdts/docs/operations/xdts_operator_failure_guide.md`
- user workflow guide: `projects/xdts/docs/user/xdts_user_guide.md`
- deployment guide: `projects/xdts/docs/operations/xdts_deployment_guide.md`

## Communication Plan

### Pre-Rollout Communication
Share:
- what is changing
- why it is changing
- what users need to do
- who to contact if they are blocked

### Rollout-Day Communication
Share:
- rollout start time
- expected downtime or usage freeze window if required
- confirmation when the migration and deployment are complete

### Post-Rollout Communication
Share:
- summary of changes
- known limitations
- support contact path

## Go/No-Go Checklist
- backup created and verified
- remediation build signed off
- migration rehearsal completed successfully
- pilot complete
- operator docs published
- rollback owner assigned
- support contact path active

If any item above is incomplete, do not proceed with full rollout.

## Rollback Strategy

### Rollback Goal
Restore service quickly without corrupting the shared database or losing confidence in the audit trail.

### Rollback Rules
- If migration fails before production cutover completes, restore from the verified backup.
- If post-rollout defects are client-side only, prefer redeploying a corrected client over rolling back the database.
- If audit verification fails unexpectedly after rollout, stop write activity and investigate before resuming operations.

### Rollback Caveat
If a migration introduces additive schema changes and new writes are accepted, rollback must be evaluated carefully against compatibility and audit continuity. Database rollback is not a default action after users resume writing.

## Success Metrics
- no privileged credential exposure in production
- no false "database unavailable" messages for duplicate-entry validation cases
- admin, operator, and viewer permissions behave as documented
- audit verification passes before and after rollout
- support documentation is sufficient for operators to complete setup without developer intervention

## Ownership
Recommended owners:
- engineering owner: remediation implementation and migration logic
- product/documentation owner: user messaging, SOPs, release notes
- operational owner: backup, deployment window, rollback readiness
