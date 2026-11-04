# ADR Development Skill

[![README views](https://hits.sh/github.com/7architect/adr-development-skill.svg?label=views&color=007ec6)](https://hits.sh/github.com/7architect/adr-development-skill/)

<!-- Counts badge requests, not unique visitors or GitHub's native traffic statistics. -->

A development workflow for Codex and Claude Code that keeps architecture decisions, implementation, and proof of completion connected.

Start with a domain and a problem. A dedicated domain architect investigates the repository and proposes a solution in an Architecture Decision Record (ADR). You approve the decision before a separate implementation agent starts work. The architect then runs the checks independently and records whether the result meets every acceptance criterion.

The deliverable is working code together with a traceable explanation of what was decided, why it was approved, which version was checked, and what the checks demonstrated.

## Why this workflow

Agent-driven projects can lose the reasoning behind their code as conversations grow or sessions change. A solution can drift during implementation, acceptance criteria can move, and a claim of completion can become difficult to reproduce.

This workflow puts those decisions in the repository:

- Record the problem, solution, rationale, and acceptance criteria before implementation.
- Require explicit approval before turning a proposal into work.
- Preserve approved solutions and criteria. Changing either requires a new ADR.
- Separate implementation from independent verification.
- Keep every decision and evidence document, including rejected proposals, superseded decisions, and failed checks.

ADRs are the project's decision history. Evidence connects that history to a specific version of the implementation and reproducible verification results.

## Responsibilities

| Role | Responsibility |
| --- | --- |
| User | Select the domain, explain the problem, approve ADRs, resolve conflicts, and authorize correction cycles |
| Coordinator | Run the initial conflict check, manage the conversation, and pass documents and constraints between agents |
| Domain architect | Investigate the problem, propose decisions, maintain their relationships, independently run checks, and complete verified ADRs |
| Implementer | Implement approved ADRs within their scope and prepare reproducible evidence |

One architect stays focused on the selected domain for the session. The domain can describe business behavior or a technical concern. For example, it can be payments, document processing, storage, or orchestration.

## A graph of decisions and evidence

Documents are never deleted. New decisions can depend on, extend, or replace previous ADRs. Evidence documents explain either why a proposal was rejected, why a decision was superseded, or how its implementation was verified.

For example:

1. `ADR-0001` defines an approach to retrying document processing. Its verification evidence records the checked version and results.
2. A new requirement exposes a conflict with that decision. The architect asks you how to resolve it before preparing a replacement.
3. You approve `ADR-0002`. It links to `ADR-0001` through `replaces`, and the old ADR becomes `superseded` with a linked replacement rationale.
4. The old implementation's evidence remains available. The new ADR stays open until its own implementation passes independent verification.

Approving a replacement does not mean the replacement is already implemented. Completing an ADR requires evidence of its own.

## When to use it

Use this workflow when the reasoning behind a change matters: architecture changes, domain behavior, cross-component work, and decisions that later contributors need to understand.

It adds documentation and approval steps. Account for that overhead when choosing it for small, routine changes. The approval rules are part of the workflow even when the implementation looks straightforward.

## How it works

1. Run the bundled conflict checker before any other workflow step.
2. Ask for the architect's focus domain. The domain can be business-oriented, such as payments, or technical, such as storage or orchestration.
3. Create a separate architect for that domain for the entire session. The architect asks which problem to solve.
4. Investigate the code, existing ADRs, evidence, and constraints before drafting a decision.
5. Write an ADR with the problem, proposed solution, rationale, and measurable acceptance criteria.
6. Request explicit user approval for that ADR or an enumerated set of ADRs.
7. Have a separate implementation agent implement the approved decision after every dependency is completed.
8. Have the architect independently execute checks against every acceptance criterion.
9. Complete the ADR only when every criterion passes and the evidence document is linked.

The main agent coordinates the conversation and handoffs. The architect owns decisions and independent verification. The implementer owns implementation and its supporting evidence.

## Installation

Requires Python 3.9 or newer, access to the project files, and an agent environment that supports separate agents and command execution. Git is needed for the installation commands below. The Python conflict checker uses only the standard library.

Clone the repository:

```sh
git clone https://github.com/7architect/adr-development-skill.git
cd adr-development-skill
```

Copy the skill into one of these locations. Run the commands from the cloned repository. Use a fresh destination when installing; review an existing installation before replacing it.

### Codex

For your user account:

```sh
mkdir -p "$HOME/.agents/skills"
cp -R develop-with-adr "$HOME/.agents/skills/develop-with-adr"
```

For a single project, copy `develop-with-adr` into that project's `.agents/skills/` directory.

Invoke with:

```text
$develop-with-adr
```

### Claude Code

For your user account:

```sh
mkdir -p "$HOME/.claude/skills"
cp -R develop-with-adr "$HOME/.claude/skills/develop-with-adr"
```

For a single project, copy `develop-with-adr` into that project's `.claude/skills/` directory.

Invoke with:

```text
/develop-with-adr
```

See the official [Codex skills documentation](https://developers.openai.com/codex/skills/) and [Claude Code skills documentation](https://code.claude.com/docs/en/skills) for environment-specific discovery rules. The same skill files are used in both environments. Verify that separate agents and verification tools are available in your installation.

## Example

```text
Use develop-with-adr.
Domain: document processing and orchestration.
Problem: interrupted document runs can repeat external writes.
Investigate the repository and existing ADRs, then propose a decision for discussion.
```

Providing the domain and problem in the initial request avoids redundant questions. It does not approve an implementation.

## ADR statuses

| Status | Meaning | Who authorizes the transition |
| --- | --- | --- |
| `accepted-for-discussion` | Investigated proposal ready for discussion | Architect |
| `accepted-for-work` | Specific ADR explicitly approved for implementation | User |
| `completed` | Every criterion independently verified, with linked evidence | Architect |
| `rejected` | Never-approved proposal declined in favor of a newly approved ADR, with linked rationale | User approval of the replacement |
| `superseded` | Previously approved decision replaced by a newly approved ADR, with linked rationale | User approval of the replacement |

An approved batch does not bypass dependencies. An ADR cannot enter implementation until all ADRs it depends on are completed.

After approval, the solution description and acceptance criteria are immutable. Changes require a new ADR and new approval. Current status and relationship links may be updated while appending history.

When a replacement is approved for work, a previously approved ADR immediately becomes `superseded`, including one that was completed. A never-approved proposal becomes `rejected` instead. Preserve its previous completion, version, and evidence. Record that the replacement may still be awaiting implementation.

Do not reject or supersede a decision without a new approved one. Preserve legacy rejection entries and interpret them through their history instead of silently rewriting them. If a proposed decision conflicts with a current ADR, ask the user to resolve the conflict before preparing the new ADR.

## Decision quality

Every ADR includes explicit alternatives with reasons for not selecting them, positive and negative consequences, and observable reconsideration triggers. Do not invent alternatives or neutral consequences to fill a template.

Acceptance criteria establish whether the implementation works now. Reconsideration triggers describe when a previously suitable decision needs another look. Record an observation or threshold and its evidence source. Reaching it starts investigation and user discussion, not an automatic replacement.

For neural-model decisions, also record the approach and alternatives, coupling to prompts/schemas/evaluations/infrastructure, operating cost and unacceptable volume, and actual switching cost. Label estimates and unknown measurements. Omit this section for unrelated decisions.

See the [worked ADR example](develop-with-adr/references/example-adr.md). Its facts and figures are hypothetical and do not claim successful implementation or verification.

## Evidence and correction cycles

Implementation evidence must include:

- Results for every acceptance criterion.
- Commands and instructions for reproducing the checks.
- The verified commit or exact code version. For uncommitted changes, include a saved diff and file hashes.
- Checks actually executed by the architect, with their results and log references.

If implementation fails verification while the ADR remains valid, request user permission before fixing it. After permission, the implementer applies corrections and the architect verifies again. Another failed verification requires permission for the next correction cycle.

If implementation requires changing the decision or criteria, stop affected work and return the issue to the architect. Independent approved work may continue.

## Document history

Write project documents in:

| Path | Contents |
| --- | --- |
| `docs/adr/ADR-0001-short-slug.md` | Problem, solution, rationale, acceptance criteria, approval, relationships, and history |
| `docs/evidence/EVID-0001-short-slug.md` | Implementation verification or rejection rationale |

Never delete ADRs or evidence documents, reuse their IDs, or overwrite previous verification results. Append history and retain both successful and failed attempts.

Maintain explicit relative links and their reverse relationships:

| Relationship | Reverse relationship |
| --- | --- |
| `replaces` | `replaced_by` |
| `depends_on` | `required_by` |
| `extends` | `extended_by` |
| `evidence` | `proves` |

The registry records the graph; generated Markdown provides the human-readable history, and DOT/GraphML provide viewer files. No separate graph database is required. Templates are in [references/templates.md](develop-with-adr/references/templates.md).

## Deterministic ADR generation and graph files

The agent supplies researched content as JSON arguments to a Python generator. The script fixes document structure and section order, assigns IDs, records history and updates relationships. It never asks an LLM to lay out the ADR or diagram.

```sh
python3 /path/to/develop-with-adr/scripts/adr.py --project /path/to/project create --input decision.json
python3 /path/to/develop-with-adr/scripts/adr.py --project /path/to/project link --id ADR-0002 --relation depends_on --target ADR-0001
python3 /path/to/develop-with-adr/scripts/adr.py --project /path/to/project sync
```

Supply real investigated content using the [input example](develop-with-adr/references/adr-input.example.json). See the [full command reference](develop-with-adr/references/generator.md) for draft updates, explicit approvals, replacement decisions, completion evidence and recovery.

| File | Purpose |
| --- | --- |
| `docs/adr/registry.json` | Canonical records, history, fingerprints and relationships |
| `docs/adr/ADR-0001-short-slug.md` | Generated ADR following the fixed template |
| `docs/adr/graph.dot` | Graphviz DOT diagram with document links |
| `docs/adr/graph.graphml` | GraphML interchange graph with yEd labels |

Every successful mutation refreshes both graph files, including inactive decisions and attached evidence. Open DOT with a Graphviz-compatible viewer or GraphML with a compatible graph editor such as yEd. With Graphviz installed, render an image using:

```sh
dot -Tsvg docs/adr/graph.dot -o docs/adr/graph.svg
```

The script requires Python 3.9 or newer and no third-party Python packages. Viewers are optional. SVG rendering is separate from graph generation.

Missing fields, unknown arguments, duplicate criterion IDs, broken links, dependency/replacement cycles, changed approved content and altered evidence are rejected. Existing unmanaged ADRs require explicit migration; the generator does not parse or overwrite legacy prose.

The script validates structured receipts, not the truth of decisions, user consent or actual check execution. Each output file is written atomically, but the set of files is not one filesystem transaction. The registry commits first; `sync --recover` restores projections after an interrupted write once the registry has been inspected.

Run regression tests from the skill directory:

```sh
python3 -m unittest discover -s tests -v
```

## Conflicting skills

The workflow excludes `grill-me` and `spec-first`, including naming variants such as `Grill Me` and `spec_first`.

Its mandatory first step runs:

```sh
python3 /path/to/develop-with-adr/scripts/check_conflicting_skills.py \
  --project /path/to/project
```

The coordinating agent supplies every available session skill name using repeated `--available-skill` arguments. This also covers cloud-only skills. Add nonstandard skill directories or nested symlink targets with `--root`.

```sh
python3 /path/to/develop-with-adr/scripts/check_conflicting_skills.py \
  --project /path/to/project \
  --available-skill 'plugin:grill-me' \
  --available-skill 'spec-first' \
  --root /path/to/additional/skills
```

| Exit code | Meaning |
| --- | --- |
| `0` | No conflicts found in the inspected scope |
| `1` | Conflicts found |
| `2` | Scan incomplete; inspect the reported errors |

The checker returns JSON and does not change skill files or global settings. The coordinator disables conflicting skills for the current workflow, warns the user before continuing, and passes the exclusions to both agents. Global installation remains unchanged.

Discovery covers local skill directories and supplied catalog names. Nested directory symlinks are not traversed automatically. An incomplete scan must be reported as incomplete.

## Included files

| File | Purpose |
| --- | --- |
| [SKILL.md](develop-with-adr/SKILL.md) | Workflow instructions and approval rules |
| [templates.md](develop-with-adr/references/templates.md) | ADR and evidence templates |
| [example-adr.md](develop-with-adr/references/example-adr.md) | Worked hypothetical ADR with alternatives, consequences, model choice and triggers |
| [portability.md](develop-with-adr/references/portability.md) | Agent handoffs and environment requirements |
| [adr.py](develop-with-adr/scripts/adr.py) | Deterministic ADR generator and graph updater |
| [generator.md](develop-with-adr/references/generator.md) | CLI commands and input contract |
| [check_conflicting_skills.py](develop-with-adr/scripts/check_conflicting_skills.py) | Read-only conflict discovery |
| [openai.yaml](develop-with-adr/agents/openai.yaml) | Codex interface metadata |
| [icon.svg](develop-with-adr/assets/icon.svg) | Skill icon |

## Scope and limitations

The skill follows the [Agent Skills format](https://agentskills.io/specification). Its approval gates and role boundaries are agent instructions, not an external permission-enforcement system. Separate agents are required for the intended workflow; one agent switching roles does not satisfy independent verification.

The conflict checker and workflow scenarios have been checked. A complete end-to-end run in both Codex and Claude Code has not yet been verified.

## License

This project uses the custom [ADR Development Skill No-Resale License](LICENSE).

- You may use and modify the skill for free, including in commercial work.
- You may redistribute the skill and modified copies free of charge, with the license and existing copyright notices.
- You may not sell the skill or copies of it, or charge for access to the skill itself.
- You may charge for products and services created with the skill. Using it does not impose this license on your code, ADRs, or other output.

Because it restricts resale, this is a source-available license, not an OSI-approved open-source license. The full license is also included in the installable [skill folder](develop-with-adr/LICENSE).
