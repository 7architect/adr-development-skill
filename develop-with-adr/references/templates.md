# Document templates

Replace placeholders with actual information. Use `[]` for absent relationships and relative Markdown links for populated relationships. Record timestamps with a timezone. Keep the status current and append history entries.

## ADR

```markdown
---
id: ADR-0001
status: accepted-for-discussion
domain: <selected domain>
created: <ISO date>
---

# ADR-0001: <decision title>

## Problem
<Brief observed problem, context, and constraints. Link code and supporting facts.>

## Proposed solution
<Scope, behavior, and required changes.>

## Rationale
<Why this solves the problem; material alternatives and tradeoffs.>

## Acceptance criteria
- AC-01: <observable outcome and verification method>
- AC-02: <observable outcome and verification method>

## Relationships
- replaces: []
- replaced_by: []
- depends_on: []
- required_by: []
- extends: []
- extended_by: []
- evidence: []

## Approval
<Not received / date, exact user response, message link if available,
and approved version of the solution body and criteria. Preserve the approved text
in repository history or provide a verifiable hash of that text. Do not invent chat links.>

## History
- <timestamp>: Created after investigation; accepted-for-discussion.
```

When replacing an ADR, add `replaced_by` and rejection evidence to the old ADR, and `replaces` to the new ADR. When completing an ADR, add implementation evidence. In both cases append the old and new statuses, reason, date, and links to history. Do not rewrite an approved solution.

## Implementation evidence

```markdown
---
id: EVID-0001
kind: verification
created: <ISO date>
---

# EVID-0001: Verification of ADR-0001

## Relationships
- proves: [ADR-0001](../adr/ADR-0001-short-slug.md)

## Verified version
<Repository and commit/exact version; for a dirty working tree, include the base
commit, a link to the saved diff, and hashes of the checked files.>

## Environment and reproduction
<Dependencies, configuration without secrets, required data, and command sequence.>

## Implementer results
| Criterion | Command / steps | Expected result | Actual result | Log |
| --- | --- | --- | --- | --- |
| AC-01 | ... | ... | ... | ... |

## Independent architect verification
<Date, verified version, and commands actually executed by the architect.>

| Criterion | Command / steps | Actual result | Outcome | Log |
| --- | --- | --- | --- | --- |
| AC-01 | ... | ... | passed / failed / not verified | ... |

## Conclusion
<Complete ADR / permission to fix required / new decision required.>

## Verification history
<Append subsequent attempts, preserving earlier results and versions.>
```

## Rejection rationale evidence

```markdown
---
id: EVID-0002
kind: rejection-rationale
created: <ISO date>
---

# EVID-0002: Reason for rejecting ADR-0001

## Relationships
- proves: [ADR-0001](../adr/ADR-0001-short-slug.md) - reason for rejection
- replacement: [ADR-0002](../adr/ADR-0002-short-slug.md)

## Basis
<Facts, constraints, or user decision causing the earlier decision to be rejected.
Separate observed facts from assumptions; include supporting evidence when available.>

## Replacement approval
<Date, explicit user response, and approved version of ADR-0002.>

## Implementation state
<Code actually in operation. The replacement is approved, but its implementation
and verification require separate implementation evidence.>
```
