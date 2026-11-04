# Worked ADR example

This is a fictional proposal. Requirements, figures, identifiers and constraints are illustrative. No repository investigation, benchmark, approval, implementation or verification is claimed. Replace them with actual project evidence before drafting a real ADR.

## ADR-0001: Keep specialist OCR inference inside the customer environment

- status: accepted-for-discussion
- domain: printed document OCR
- created: 2026-11-05

### Problem

Hypothetical requirements: extract printed Russian and English text from images in an isolated customer network. Images cannot leave that network. The project is assumed to have an OCR recognizer behind an internal adapter. Handwriting and table reconstruction are outside scope.

Verify the existing adapter, deployed model, hardware and restrictions in the actual repository. These assumptions are not evidence.

### Proposed solution

Retain the existing specialist recognizer and run inference locally. Pin the exact model artifact, preprocessing version and runtime image in the release manifest. Return text, coordinates and confidence through the internal adapter.

Before real approval, identify inspected code paths and actual artifact versions. This example deliberately provides no fabricated paths, hashes or benchmark results.

### Rationale

Local inference fits the isolation restriction. Retaining the recognizer limits migration work if it passes the required quality checks. Meeting those checks remains unproven until implementation evidence exists.

### Alternatives considered

| Alternative | Benefit | Cost / limitation | Reason not selected |
| --- | --- | --- | --- |
| External OCR API | Provider operates inference | Requires document transfer and networking | Conflicts with the stated isolation restriction |
| Local general vision-language model | Broader extraction capabilities | New runtime, evaluations and output normalization | No demonstrated need for broader tasks in this release |
| Train a new recognizer | Control over training | Labeling, training and maintenance effort | No measured shortfall currently justifies training |

### Consequences

Positive:
- Images remain within the customer network.
- Downstream consumers can keep the adapter contract.

Negative:
- The team owns packaging, runtime compatibility and operational support.
- Scan and font variation require a representative evaluation corpus.
- Offline environments require reproducible artifact distribution and upgrade procedures.

### Reconsideration triggers

| Observation / threshold | Evidence source | Reason to reconsider |
| --- | --- | --- |
| Character error rate exceeds 2% on a newly approved representative corpus | Versioned evaluation report | The recognizer may no longer fit supported inputs |
| Measured local cost exceeds $100 per 100,000 pages | Resource usage and cost report | Serving economics need comparison |
| User approves handwriting support | Approved requirement change | The scope exceeds printed text |

Thresholds are hypothetical. Observing a trigger starts investigation and discussion; it does not authorize changes or rewrite approved criteria.

### Model choice

| Aspect | Decision and basis |
| --- | --- |
| Approach | Host the existing specialist recognizer; API, general-model and training alternatives are compared above |
| Coupling | Preprocessing, coordinate conventions, confidence calibration, pinned runtime and evaluation corpus |
| Operating cost | Hypothetical budget: $100 per 100,000 pages. Actual cost is unknown until CPU/GPU time, utilization and hardware pricing are measured. At measured unit cost C, volume V exceeds the agreed monthly budget B when C times V exceeds B |
| Switching cost | Repackage the model, adapt preprocessing and confidence handling, re-run evaluations, verify compatibility and prepare rollback. Effort is not yet estimated |
| Reopening observation | Error-rate, cost or handwriting triggers above |

### Acceptance criteria

- AC-01: Character error rate is at most 2% on the pinned corpus; report Russian and English separately with sample counts and the scoring command.
- AC-02: A full run succeeds with external networking blocked; record the setup and observed network behavior.
- AC-03: Responses satisfy the versioned adapter contract for normal pages, empty input and recognition failures, demonstrated by contract checks.
- AC-04: Evidence identifies the exact code/model/runtime versions, reproduction commands and checks independently executed by the architect for AC-01 through AC-03.

Criteria test the current implementation. Triggers describe observations that could challenge the decision later, often under changed inputs or requirements.

### Relationships

- replaces: []
- replaced_by: []
- depends_on: []
- required_by: []
- extends: []
- extended_by: []
- evidence: []

### Approval

Not received. This example cannot authorize implementation.

### History

- 2026-11-05: Illustrative proposal created. No criteria are marked passed and no implementation evidence exists.
