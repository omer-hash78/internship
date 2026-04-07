# ADR-002: Audit Hash Versioning And Migration Compatibility

## Status
Accepted

## Context
The current audit chain uses an ambiguous pipe-delimited payload. That format should be replaced, but XDTS may already have databases containing history rows written with the old hash strategy.

The team needs an audit remediation approach that:
- strengthens tamper evidence
- does not silently rewrite history
- remains explainable to auditors and operators
- supports controlled migration on a shared SQLite database

## Decision
XDTS will introduce explicit audit hash versioning and will not rewrite existing history rows during migration.

Chosen approach:
- legacy rows remain valid under audit hash version 1
- new rows use a canonical structured payload under audit hash version 2
- verification logic supports both versions
- migration adds metadata needed to identify or infer which version applies

## Rationale

### Why This Option
- Rewriting old history rows would undermine confidence in the append-only audit trail.
- Versioning preserves traceability while allowing the format to improve.
- Operators and reviewers can explain the transition clearly: old rows were written under one approved algorithm, new rows under another.

### Why Not Recompute All Existing Hashes
- It changes historical evidence after the fact.
- It complicates trust claims around tamper detection.
- It creates unnecessary migration risk.

### Why Not Keep The Existing Format
- The current payload encoding is ambiguous.
- The remediation effort would not fully close the review finding.

## Consequences

### Positive
- stronger future audit records
- compatibility with existing written data
- clearer audit verification behavior during transition

### Negative
- verification code becomes slightly more complex
- migration and documentation must explain two supported versions

## Product Implications
- Audit verification output should indicate the first failing row and the version being verified when useful.
- Release notes should state that audit verification now supports both legacy and current history rows.

## Engineering Implications
- add audit hash version tracking
- use canonical serialization for new rows
- update migration and verification logic
- add tamper tests for both versions and mixed-version chains

## Documentation Deliverables
- migration note describing audit hash versioning
- audit verification SOP update
- release note entry for compatibility behavior
