# Document templates

Replace placeholders with actual information. Use `[]` for absent relationships and relative Markdown links for populated relationships. Record timestamps with a timezone. Keep the status current and append history entries.

## Contents

- ADR
- Implementation evidence
- Rejection or replacement rationale evidence

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
<Why this fits the constraints. Link supporting facts and label assumptions.>

## Alternatives considered
| Alternative | Benefits | Costs / limitations | Reason not selected |
| --- | --- | --- | --- |
| <actual alternative; include the status quo when viable> | ... | ... | ... |

<If no viable alternative was found, explain why. Do not invent options.>

## Consequences
### Positive
- <concrete benefit>

### Negative
- <cost, risk, operational burden, or limitation>

## Reconsideration triggers
| Observation / threshold | Evidence source | Why to reconsider |
| --- | --- | --- |
| <measurable condition or event> | <metric, evaluation, requirement, or dependency change> | ... |

<Triggers start investigation and discussion; they do not bypass approval.>

## Model choice
<Include only when selecting or committing to a neural model; otherwise remove.>

| Aspect | Decision and basis |
| --- | --- |
| Approach and alternatives | <build/host, buy/API, or prompt a general model; why alternatives were not selected> |
| Coupling | <prompts, output schemas, evaluation datasets, infrastructure, latency budgets> |
| Operating cost | <cost basis and volume where it becomes unacceptable; label estimates> |
| Switching cost | <data, code, evaluation, migration and operations work required> |
| Reopening observation | <specific reconsideration trigger above> |

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

When replacing an ADR, add `replaced_by` and decision-change evidence to the old ADR, and `replaces` to the new ADR. At approval of the replacement, use `superseded` for a previously approved ADR and `rejected` for a never-approved proposal. When completing an ADR, add implementation evidence. In both cases append the old and new statuses, reason, date, and links to history. Do not rewrite an approved solution.

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

## Rejection or replacement rationale evidence

```markdown
---
id: EVID-0002
kind: decision-change-rationale
created: <ISO date>
---

# EVID-0002: Reason for changing ADR-0001

## Relationships
- proves: [ADR-0001](../adr/ADR-0001-short-slug.md) - reason for rejection or replacement
- replacement: [ADR-0002](../adr/ADR-0002-short-slug.md)

## Basis
<Facts, constraints, or user decision causing the earlier decision to be rejected or superseded.
Separate observed facts from assumptions; include supporting evidence when available.>

## Replacement approval
<Date, explicit user response, and approved version of ADR-0002.>

## Implementation state
<Code actually in operation. The replacement is approved, but its implementation
and verification require separate implementation evidence.>
```
