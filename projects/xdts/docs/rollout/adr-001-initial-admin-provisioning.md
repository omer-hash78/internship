# ADR-001: Initial Admin Provisioning

## Status
Accepted

## Context
The current XDTS implementation creates a fixed bootstrap admin account and exposes the credentials in the GUI. That is not acceptable for a shared-database desktop application used by a documentation department.

The team needs a first-use model that:
- avoids hard-coded secrets
- works with a shared SQLite database
- is explainable in operator documentation
- is supportable without external services

## Decision
XDTS will not auto-create or display a privileged bootstrap account in the GUI.

Initial admin creation will be an explicit operator action performed through a dedicated setup command, for example:
- `python projects/xdts/main.py --initialize-admin`

Expected behavior:
- the command is available only when no active admin account exists
- the operator enters the username and password intentionally
- the command writes the admin account directly to the target shared database
- the GUI login screen never reveals credentials

## Rationale

### Why This Option
- It removes the hard-coded password risk completely.
- It avoids race conditions where multiple first-run clients compete to create the first admin.
- It fits a controlled department deployment better than an ad hoc GUI-first setup flow.
- It is easy to document as a standard operating procedure.

### Why Not Auto-Generated One-Time Credentials
- Generated credentials still require secure display and storage rules.
- In a shared desktop environment, the handoff path is harder to control and explain.
- It adds operational complexity without enough product value for this use case.

### Why Not GUI First-Run Setup
- Any client pointed at the shared database could become the setup client.
- That creates ambiguity in ownership and timing during rollout.
- It is harder to govern in operational documentation.

## Consequences

### Positive
- no privileged credential disclosure in the product UI
- clearer operator ownership of first-use setup
- easier release notes and provisioning documentation

### Negative
- one more operational step before first productive use
- setup command and related documentation must be maintained carefully

## Product Implications
- The login screen should show neutral guidance only.
- If no admin exists, the application should provide a safe message directing the operator to the provisioning procedure.
- Release notes and onboarding docs must describe the setup command and required permissions.

## Engineering Implications
- remove hard-coded bootstrap account creation
- add guarded admin provisioning command flow
- ensure service authorization always checks persisted user state

## Documentation Deliverables
- initial admin provisioning SOP
- install/setup instructions
- troubleshooting guidance for "no admin configured" state
