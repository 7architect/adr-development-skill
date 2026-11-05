# ADR generator and integrity checks

## Contents

- Input contract
- Drafts and imports
- Independent design review and approval
- Verification attempts and corrections
- Read-only checks and CI
- Transactions, recovery and outputs

## Input contract

Requires Python 3.9 or newer, using only the standard library. Replace `SKILL` and `PROJECT` below with actual absolute paths. Run the skill conflict checker before the workflow.

`scripts/adr.py` is the executable ADR template. Agents supply researched content as JSON, never manual ADR Markdown or graph syntax. Required fields:

| Field | Type |
| --- | --- |
| `title`, `domain`, `problem`, `solution`, `rationale` | Nonempty text |
| `alternatives` | Objects with `option`, `benefits`, `costs`, `reason` |
| `positive`, `negative` | Nonempty text lists |
| `triggers` | Nonempty objects with `observation`, `evidence`, `reason` |
| `criteria` | Nonempty objects with unique stable `id` such as `AC-01`, and `text` |

If `alternatives` is empty, supply `no_alternatives` explaining why. Otherwise omit it. For neural-model decisions supply `model` with all five text fields: `approach`, `coupling`, `operating_cost`, `switching_cost`, `reopening_observation`. Omit it for unrelated decisions. The agent determines model relevance; the script cannot infer it from prose.

Unknown fields, duplicate JSON keys, invalid IDs and missing content are rejected. Text is escaped to prevent Markdown/HTML injection. Create document links through the relationship commands. `--input -` reads standard input. Use the [input example](adr-input.example.json) for structure only; its facts are hypothetical. Keep lengthy text in JSON files instead of shell interpolation.

## Drafts and imports

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" create --input decision.json --author architect-agent --slug stable-retries
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" update --id ADR-0001 --input revised.json --author architect-agent --reason "Clarified failure behavior"
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" link --id ADR-0002 --relation depends_on --target ADR-0001
```

Use actual agent identities. `--slug` is optional. `update` takes the complete draft, not a patch. Each revision or author change invalidates previous approving reviews. Approved content and dependencies cannot be rewritten. Reverse links are generated. Supported explicit link relations are `depends_on` and `extends`; replacement edges are recorded on approval. There is no delete or unlink command.

To import a historical ADR, investigate the original and prepare a mapping to the input contract:

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" import --id ADR-0007 --source docs/adr/ADR-0007-old.md --reported-status completed --note "Mapped from the retained historical file; original approvals not established" --input mapped.json --author current-architect-agent
```

Import preserves the original bytes, filename and checksum. A normalized wrapper is generated under `docs/adr/imported/`. Its canonical status is `accepted-for-discussion`, regardless of the reported historical status. Historical approval/completion is not invented. The index and graph distinguish the source from the new proposal. The current mapping architect is not asserted to be the historical author.

Do not edit or delete the source after importing. It is protected by checksum and CI baseline checks. Generated outputs cannot be import sources. Import remaining legacy ADRs one at a time; ordinary mutations and `check` refuse unknown root-level `ADR-*.md` files until they are imported. Other legacy filenames are imported only when explicitly selected, not inferred automatically. Existing managed v1 registries remain readable; run `sync` to initialize the new index before enabling CI.

## Independent design review and approval

The coordinator must ask a separate read-only reviewer who did not write the proposal to inspect the ADR, requirements, relevant code and intended replacements. Give that reviewer the complete context. Require a concrete input-to-outcome walkthrough, including relevant partial failures, retries, concurrent calls, migration and rollback. Review the decisions rather than wording or document length. Do not implement changes during review.

Prepare an actual review receipt:

```json
{
  "architect": "actual-proposal-author-agent",
  "reviewer": "actual-separate-reviewer-agent",
  "verdict": "Approve",
  "findings": [],
  "walkthroughs": ["Actual request/failure scenario inspected and its conclusion"],
  "limitations": "What remains unverified, or none with a basis"
}
```

Verdicts are `Approve`, `Request changes`, or `Blocked`. Each finding has nonempty `severity` (`blocker` or `important`), `location`, `problem`, `impact`, `evidence`, and `correction`. `Approve` cannot contain unresolved findings. Reviewers must have distinct identifiers from the author. This checks declarations, not authenticated agent identity.

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" review --id ADR-0001 --input actual-review.json --evidence docs/evidence/EVID-0001-design-review.md
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" approve --id ADR-0001 --approval "Actual explicit user approval of the reviewed version"
```

`review` writes an immutable `REVIEW-ADR-0001-0001.json`. Its fingerprint binds the content, author, draft revision and current outgoing non-replacement links. Approval requires the latest matching `Approve` review plus actual explicit user approval. A reviewer verdict does not substitute for the user's approval. Grandfathered v1 approvals are not retroactively invented or relabeled as reviewed.

For replacements, add repeated `--replace ADR-0000` arguments and `--rationale docs/evidence/EVID-0002-replacement.md` to `approve`. Previously approved old ADRs become `superseded`; never-approved proposals become `rejected`. Keep old completion evidence. A replacement is not automatically implemented. Approval still does not authorize implementation before dependencies complete.

## Verification attempts and corrections

The architect must actually run checks independently from the implementer. Prepare a receipt:

```json
{
  "verified_version": "actual verified commit or exact version",
  "architect": "actual independent architect identifier",
  "results": [
    {
      "criterion": "AC-01",
      "command": "Actual command or reproducible steps; state if blocked/not run",
      "result": "Actual observed result or precise blocker",
      "outcome": "passed"
    }
  ]
}
```

Cover every criterion exactly once. Outcomes are `passed`, `failed`, `blocked`, or `not-verified`. Never label an unexecuted check as passed.

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" verify --id ADR-0001 --verification actual-checks.json --evidence docs/evidence/EVID-0003-verification.md
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" complete --id ADR-0001 --attempt ATTEMPT-ADR-0001-0001
```

Every valid `verify` receipt creates a separate immutable `ATTEMPT-ADR-0001-0001.json`, including failures. Exit 0 means the attempt was recorded, not that the tests passed. Read the receipt/outcome; only a latest all-passing attempt and completed dependencies permit `complete`. `--attempt` is optional, but if supplied must identify the latest attempt. The old `complete --verification ... --evidence ...` form is replaced by these two steps.

After a failed or blocked attempt, obtain user permission before fixing or starting the next correction cycle:

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" authorize-fix --id ADR-0001 --approval "Actual explicit permission" --scope "Concrete authorized corrections"
```

Then the implementer fixes, and the architect independently checks again and records another `verify`. Each new failed attempt needs new permission. Preserve earlier receipts and evidence. Use a new Markdown evidence file for each attempt instead of editing attached evidence.

## Read-only checks and CI

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" check
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" check --base-ref BASE_COMMIT_SHA
```

`check` creates or changes no files, including in an empty project. It detects stale/missing Markdown, index, graphs and attempt/review receipts, altered evidence or imported sources, missing references, cycles, invalid status/receipt structure and pending transactions. An empty project without a registry is valid if it has no unmanaged ADR files.

With `--base-ref`, it also rejects deletion of historical records/relationships, rewritten history/evidence/attempts/reviews, changes to approved content/metadata/dependencies, invalid status regression, and changes to imported-source descriptors even when checksums were manually recomputed. Resolve the baseline to a real Git commit; compare with the PR base or prior push, not the same commit being checked. No baseline means no cross-commit immutability proof.

Copy and commit the generator into the consuming project, then install the GitHub Actions workflow:

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" install-ci --script-path .agents/skills/develop-with-adr/scripts/adr.py
```

The path must exist inside the project. Commit that script, `.github/workflows/adr-check.yml`, registry and generated files. Default workflow path collisions with differing content are rejected. The workflow uses read-only repository permissions, full Git history and the PR base/prior push SHA. An empty or all-zero baseline is skipped for an initial push. CI cannot use files installed only in someone's home directory.

CI validates artifacts. It does not authenticate the supplied user/reviewer identities or establish that commands in receipts were actually executed. Branch protection and workflow integrity remain repository settings.

## Transactions, recovery and outputs

| Output | Purpose |
| --- | --- |
| `docs/adr/registry.json` | Canonical decisions, history, receipts, checksums and typed edges |
| `docs/adr/ADR-0001-slug.md` | Generated ADR |
| `docs/adr/imported/ADR-0007-slug.md` | Imported proposal wrapper; original source stays untouched |
| `docs/adr/INDEX.md` | Current authority, implementation verification, blockers and pending replacement notes |
| `docs/adr/graph.dot`, `graph.graphml` | Full graph including retired ADRs, evidence, reviews, attempts and imported sources |
| `docs/evidence/REVIEW-ADR-0001-0001.json` | Immutable design-review receipt |
| `docs/evidence/ATTEMPT-ADR-0001-0001.json` | Immutable verification attempt |

Every successful mutation refreshes the index and graphs. `sync` regenerates projections without adding history. DOT opens in Graphviz viewers; GraphML includes yEd labels. Apply a layout in yEd. `dot -Tsvg docs/adr/graph.dot -o docs/adr/graph.svg` separately renders an SVG; the generator does not refresh that image.

The transaction journal `docs/adr/.transaction.json` is durably written before projections, with target-state and before/after checksums. The registry commits last. A crash may leave some files updated, but the journal allows replay to finish consistently. File-by-file publication is not a filesystem-wide atomic snapshot.

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" recover
```

A mutating command automatically finishes a pending transaction first and returns `recovered: true` without applying the newly requested mutation. Inspect the recovered result before issuing another command; this prevents duplicate creation on retries. `recover` is idempotent. `check` never recovers or repairs files; it reports the pending operation instead.

Recovery refuses files changed outside the transaction since interruption, changed evidence, imported sources or a registry that no longer matches the journal's before/after checksums. Do not delete the journal to bypass an error. Resolve the discrepancy from preserved history.

Process-level advisory locks release on exit/crash. The small `.generator.lock` file remains; do not delete it while a writer is active. Do not set `ADR_TEST_INTERRUPT_*` environment variables in normal use; they exist only for deterministic crash tests.

After inspecting the canonical registry, `sync --recover` explicitly restores manually altered or missing projections. This is distinct from pending-transaction replay and does not bypass evidence/source integrity checks or the CI baseline.

Commit the registry, projections and receipts together. Do not hand-edit the registry to forge approval, review or execution. Success prints JSON and exits 0; validation/I/O/lock errors print JSON to stderr and exit 2. Argument-parsing errors use standard CLI diagnostics. Failed validation precedes the journal commit; an interrupted commit leaves a recoverable journal rather than an invitation to rerun the mutation blindly.
