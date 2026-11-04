# Deterministic ADR generator

## Contents

- Contract and input
- Commands
- State and graphs
- Boundaries and recovery

## Contract and input

Use Python 3.9 or newer. The script uses only the standard library. Replace `SKILL` and `PROJECT` below with actual absolute paths. Run the conflict checker before entering the development workflow, as required by SKILL.md.

The renderer in `scripts/adr.py` is the executable ADR template. Agents supply decision content as JSON; they must not invent Markdown layouts, status edits or graph syntax. `references/templates.md` documents the same section order. JSON must have exactly these required fields:

| Field | Type |
| --- | --- |
| `title`, `domain`, `problem`, `solution`, `rationale` | Nonempty text |
| `alternatives` | List of objects with `option`, `benefits`, `costs`, `reason`, all nonempty text |
| `positive`, `negative` | Nonempty lists of nonempty text |
| `triggers` | Nonempty list of objects with `observation`, `evidence`, `reason` |
| `criteria` | Nonempty list of objects with unique `id` matching `AC-01` and nonempty `text` |

Optional fields:

- `no_alternatives`: required nonempty explanation only when `alternatives` is empty; forbidden when alternatives exist.
- `model`: when the decision selects a neural model, an object with all five nonempty fields: `approach`, `coupling`, `operating_cost`, `switching_cost`, `reopening_observation`. Omit for unrelated decisions. The agent determines whether model selection is in scope; the script cannot infer this from prose.

Unknown fields, duplicate JSON keys, missing fields, invalid criterion IDs and empty required sections are rejected. Text arguments are rendered as escaped plain text to prevent injected Markdown headings, links or HTML from changing the template. Put real document relationships through the link commands. This means prose fields cannot contain Markdown formatting or manually authored document links.

Use [adr-input.example.json](adr-input.example.json) only as a structural example. Its content is hypothetical. Prepare real values from investigation. `--input -` reads JSON from standard input. Keep lengthy text in JSON files instead of interpolating it into shell command strings.

## Commands

### Create a proposal

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" create --input decision.json --slug stable-retry-keys
```

Generates the next free managed ADR ID with `accepted-for-discussion` status. `--slug` is optional and accepts lowercase letters, digits and single hyphens. Other languages can appear in titles and content.

### Refine an unapproved draft

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" update --id ADR-0001 --input revised-decision.json --reason "Clarified failure behavior after investigation"
```

The input is the complete decision payload, not a patch. Approved decision content cannot be rewritten. The filename remains stable if the title changes.

### Add a relationship

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" link --id ADR-0002 --relation depends_on --target ADR-0001
```

Supported direct relationships are `depends_on` and `extends`; reverse links are generated automatically. Replacement edges are created only by approval of a replacement. Links must reference existing managed records. Dependency and replacement cycles and self-links are rejected. Approved dependencies cannot be changed. There is no unlink/delete operation; resolve changed dependencies through a new ADR.

### Record actual user approval

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" approve --id ADR-0001 --approval "Actual explicit user response and the reviewed version/message reference"
```

The script fingerprints approved content and records the receipt. Passing a string does not obtain permission: the coordinator must first receive real explicit user approval. Approval does not bypass waiting for completed dependencies before implementation.

To approve a replacement, first create its proposal and a real Markdown rationale in `docs/evidence/`, then run:

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" approve --id ADR-0002 --approval "Actual user approval of ADR-0002" --replace ADR-0001 --rationale docs/evidence/EVID-0002-replacement.md
```

Repeat `--replace` for multiple old ADRs. Previously approved decisions become `superseded`; never-approved proposals become `rejected`. Both receive replacement links, rationale links and appended history. Existing completion evidence is retained. A replacement is not automatically completed.

### Record architect verification and complete

After the architect actually runs every check, create an existing evidence document under `docs/evidence/` and a verification receipt JSON with this shape:

```json
{
  "verified_version": "actual verified commit or exact version",
  "architect": "actual independent architect identifier",
  "results": [
    {
      "criterion": "AC-01",
      "command": "actual command or reproducible check steps",
      "result": "actual observed result",
      "outcome": "passed"
    }
  ]
}
```

Include every criterion exactly once. Failed or unverified criteria cannot complete an ADR.

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" complete --id ADR-0001 --verification actual-checks.json --evidence docs/evidence/EVID-0001-verification.md
```

The script checks the receipt structure, coverage, passed outcomes, dependency completion, evidence existence and hashes. It does not execute arbitrary commands from JSON, authenticate the architect or establish the truth of supplied results. Independent execution remains the architect's responsibility.

### Rebuild graphs

```sh
python3 "$SKILL/scripts/adr.py" --project "$PROJECT" sync
```

Every successful mutation already refreshes all Markdown projections and both graphs. `sync` regenerates them from the current registry, verifies evidence and detects manual edits. Repeated syncs do not change timestamps or history.

## State and graphs

| Output | Purpose |
| --- | --- |
| `docs/adr/registry.json` | Canonical records, content fingerprints, status, history, evidence hashes and typed edges |
| `docs/adr/ADR-0001-short-slug.md` | Generated human-readable ADR |
| `docs/adr/graph.dot` | Graphviz DOT directed graph with labels and document URLs |
| `docs/adr/graph.graphml` | GraphML interchange graph with node properties and yEd labels |

Graphs include all managed ADRs, including rejected and superseded records, plus attached evidence nodes. Historical events remain in each ADR and the registry. An evidence node has a stable internal ID derived from its path; the original evidence filename is preserved. Reverse relationship links appear in ADR documents; graph edges show only the canonical direction to avoid drawing every relationship twice.

Open `.dot` in a Graphviz-compatible viewer. With Graphviz installed:

```sh
dot -Tsvg "$PROJECT/docs/adr/graph.dot" -o "$PROJECT/docs/adr/graph.svg"
```

Open `.graphml` in a compatible graph editor such as yEd, then apply a layout. Coordinates are not precomputed. Graphviz and yEd are optional viewers and are not needed to generate either file. SVG conversion is a separate rendering step and is not refreshed by the generator.

## Boundaries and recovery

- Commit the registry, generated Markdown and graph files together in the project. Do not hand-edit them or feed a modified registry to bypass approvals.
- Pre-existing unmanaged `ADR-*.md` files cause an error. Migrate them explicitly after reviewing history and approvals; this version does not parse or silently overwrite legacy prose. Do not delete old documents to get past this check.
- Evidence files must exist inside `docs/evidence/` and use Markdown-safe paths without spaces or link delimiters. Attached evidence is hashed. Later edits cause a validation error; preserve it and create a new evidence document instead.
- A project-local exclusive lock prevents concurrent writers. An existing lock is an error. Remove a stale lock only after confirming no writer is running.
- Each file is replaced atomically. The canonical registry commits first; a process or disk failure can leave projections incomplete. This is recoverable, not a multi-file atomic transaction.
- After checking that the registry contains the intended state, use `sync --recover` to explicitly regenerate missing or changed projections. This overwrites manual ADR projection edits from the registry. It does not bypass evidence-integrity validation.
- The generator preserves approved bodies and appends history, but it cannot prove the factual quality of a decision, user consent, or actual test execution. These remain workflow responsibilities.
- Success prints JSON and exits 0. Validation, I/O or lock errors print JSON to stderr and exit 2. Failed validation occurs before committing state. Projection write errors may happen after the registry commits; inspect the state before retrying a mutation.
