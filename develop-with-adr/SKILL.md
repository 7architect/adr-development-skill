---
name: develop-with-adr
description: "Develop software through a separate domain architect and implementation agent, ADRs, and a graph of evidence. Use for ADR-driven development, architecture decisions requiring explicit user approval, implementation, and independent verification. Supports business and technical domains in Codex and Claude Code."
license: "ADR Development Skill No-Resale License; see LICENSE"
---

# Develop with ADRs

## Mandatory first step: conflict check

Before asking for the domain, creating agents, investigating code, or making changes, run the bundled read-only script:

```sh
python3 <absolute-skill-directory>/scripts/check_conflicting_skills.py --project <repository-path>
```

Resolve placeholders to actual paths and quote paths as needed. Pass every name in the session's available-skill catalog with a repeated `--available-skill` argument, including cloud-only and plugin-qualified names. Add nonstandard skill directories with `--root`; explicitly add targets of relevant nested directory symlinks. The script discovers local skill files and catalog entries without loading their instructions or changing installations.

- Treat `grill-me` and `spec-first` as conflicting skills, including case, space, underscore, and hyphen variants such as `Grill Me` or `spec_first`.
- Exit 0 means no conflicts found in the inspected scope. Exit 1 means conflicts were found, not script failure. Exit 2 means discovery was incomplete: report the errors and coverage limitation, resolve them where possible, and rerun. Never claim all skills were checked when coverage is incomplete.
- For any matches, disable their use within this workflow and warn the user in their language before continuing: name the detected skills and explain that they are disabled for the current workflow only. Do not imply global uninstallation or account-setting changes. No additional approval is required for these workflow exclusions.
- Do not invoke the excluded skills, follow their instructions, or delegate work to them. Apply the exclusion to the coordinator, architect, and implementer; pass the exclusion list at every agent handoff. Use this workflow's own clarification and approval steps.
- The script detects conflicts; the coordinating agent enforces the exclusions. Also exclude either skill if the session catalog reveals it even when its files are not accessible. If the script cannot run, report that limitation and apply known exclusions without claiming a successful scan.
- Rerun after resuming a session or changes to available skills. Never delete, rename, or globally disable installed skills as part of this check.

## Deterministic ADR documents and graph

- Before creating or changing ADRs, read [generator instructions](references/generator.md) and the [input example](references/adr-input.example.json). Use `scripts/adr.py` for every new ADR, draft update, relationship, approval, completion, and graph refresh. Do not compose ADR Markdown or graph syntax manually.
- Supply researched content through a JSON input file with the exact required fields. The script fixes section order, validates arguments, assigns IDs, escapes text, records history and generates Markdown plus DOT and GraphML. The script does not invent the problem, solution, measurements or evidence.
- Invoke `python3 <skill>/scripts/adr.py --project <repository> create --input <decision.json>` after the architect investigates and clarifies the problem. Use `update` for an unapproved draft, `link` for typed links, `approve` only after actual explicit user approval, and `complete` only after the architect actually executes all checks.
- Use `approve --replace ... --rationale ...` to record replacement approval and update old ADR statuses and backlinks together. Never simulate user consent or independent verification by filling a receipt with invented values.
- Every successful change rebuilds `docs/adr/graph.dot` and `docs/adr/graph.graphml` from canonical `docs/adr/registry.json`. Run `sync` to refresh graphs without adding history. Preserve the registry with the documents.
- Stop on invalid inputs, unknown legacy ADR files, cycles, changed approved bodies, altered evidence or manual projection edits. Do not delete history to resolve an error. Use `sync --recover` only after inspecting the canonical registry and explicitly choosing to restore generated projections.
- A script receipt validates structure and coverage, not actual user consent or execution. Keep all human approval and independent verification rules below.

## Entry and roles

1. Before starting the workflow, ask for the domain on which the architect should focus. Accept business or technical domains. Reuse an explicitly supplied domain without asking again.
2. Create a separate architect agent for the selected domain for the entire session. Provide these rules, the domain, repository path, and known context. Have the architect ask the user which problem to solve; the main agent may relay the question and answer. If the problem is already provided, ask only for missing information.
3. Have the main agent coordinate dialogue, documents, and context handoffs. Have the architect investigate, design, maintain ADRs, and independently verify results. Have a separate implementation agent implement approved decisions and prepare evidence. Do not combine architect and implementer roles.
4. Use the environment's native separate-agent capabilities: subagents in Codex and available agent/task capabilities in Claude Code. Do not invent APIs or present a single agent switching roles as independent verification. If separate agents are unavailable, explain the limitation and ask the user to choose a suitable environment. Investigation may continue, but implementation under this workflow must not begin.
5. After context loss, restore state from documents and code. If a new architect must be created, do not claim the original agent survived; restore its domain and responsibilities.

## Investigation and decision

- Have the architect read project instructions, code, related ADRs, and evidence, and clarify the problem and constraints. Do not create an ADR before investigating the code and clarifying the problem. If no code exists yet, record that fact and investigate available materials.
- Identify conflicts with current decisions. First present the conflict to the user and request a decision; only after the response prepare a new ADR. Permission to prepare a replacement is not approval to implement it.
- Generate an ADR in `docs/adr/` with `scripts/adr.py create`; the [templates](references/templates.md) describe its fixed structure. Include a brief problem statement, proposed solution, rationale, and verifiable acceptance criteria with stable IDs. Set the initial status to `accepted-for-discussion`.
- Require explicit alternatives with reasons for not choosing them, positive and negative consequences, and observable reconsideration triggers in every ADR. Do not invent options or neutral consequences to fill a template. If no viable alternative exists, explain the investigation and constraints.
- Distinguish acceptance criteria (proof the implementation works now) from reconsideration triggers (observations that may invalidate the choice later). Each trigger states a signal, threshold or event, and evidence source. A review date alone is insufficient. A trigger reopens investigation and user discussion; it never authorizes changes automatically.
- For decisions selecting a neural model (LLM, OCR, embeddings, or similar), require a model-choice section: build/host, buy/API, or prompt a general model; alternatives; coupling to prompts, schemas, evaluations and infrastructure; operating cost and unacceptable volume; switching cost; and the observation that reopens the decision. Label estimates and unknown measurements. Omit this section for unrelated decisions.
- Read the [worked example](references/example-adr.md) to calibrate depth. Its facts and figures are hypothetical, not project evidence.
- Separate independent decisions into separate ADRs and explicitly record dependencies. Do not introduce dependency or replacement cycles.
- Present the specific ADR or an enumerated set of ADRs for explicit user approval to implement. Do not infer approval from silence, a general request to build something, or permission to investigate.
- Record the user's response, date, and approved document version. Set `accepted-for-work` only after explicit approval. Allow explicit approval of an enumerated set of ADRs.

## Implementation

- Begin implementing an ADR only after all ADRs it depends on are completed, even if the entire set is already approved.
- Give the implementer the ADR, criteria, dependencies, and constraints. Require implementation within the approved decision's scope.
- If implementation is impossible or the decision or criteria need to change, stop affected work and return the issue to the architect. Independent approved work may continue.
- Never change the solution description or acceptance criteria after approval. Record changes in a new ADR with separate approval.
- Have the implementer prepare evidence in `docs/evidence/`: results for every criterion, commands and reproduction instructions, and the verified commit or exact code version. Do not substitute a future commit for the tested version. For uncommitted changes, include a saved diff and identifiers or hashes of the checked files.

## Independent verification and completion

- Have the architect personally run checks and compare actual results against every acceptance criterion. The implementer's report and code inspection do not replace execution.
- Preserve commands, environment, results, log links, and the verified version in the evidence. Honestly mark checks that were not run, were blocked, or failed. Do not complete an ADR with unverified or unmet criteria.
- If implementation fails verification but the ADR remains valid, first present the results and concrete correction scope to the user and request permission. Do not delegate or perform fixes before the response. After permission, have the implementer fix the issue and the architect verify again. Another failed verification requires fresh permission for the next correction cycle.
- If the failure requires a new architecture decision, return to investigation and the new-ADR procedure.
- Allow only the architect to set `completed` after successful independent verification of every criterion. Require a link to the evidence document. No additional user approval is needed to complete the ADR.

## Statuses and history preservation

Use exactly five canonical `status` values. The Russian labels below identify their original meanings; preserve existing project history rather than silently rewriting legacy documents.

| Status | Original label | Condition |
| --- | --- | --- |
| `accepted-for-discussion` | принято к обсуждению | Investigated proposal awaiting discussion or approval |
| `accepted-for-work` | принято к работе | User explicitly approved the specific ADR |
| `completed` | завершен | Architect independently verified all criteria; evidence is linked |
| `rejected` | отклонено | Never-approved proposal declined in favor of a new approved ADR, with linked rationale |
| `superseded` | заменен | Previously approved decision replaced by a new approved ADR, with linked rationale |

- Never delete ADRs or evidence documents or reuse their IDs. Before approval, allow draft refinement while recording substantial changes.
- After approval, keep all approved decision content immutable, including the solution, rationale, alternatives, consequences, triggers, model-choice details, and criteria. Allow current status and link updates with appended history entries. Preserve earlier entries, evidence, and verification results. Do not overwrite a failed check with a passing result.
- When the user explicitly approves a replacement for work, mark the old ADR `superseded` if it was previously approved (`accepted-for-work` or `completed`), or `rejected` if it was never approved. Link it to the replacement and a separate decision-change rationale document. This explains the change; it does not prove the replacement implementation works.
- Preserve previous completion, its date, version, and evidence. Explicitly record that the replacement may not yet be implemented. Rejecting or superseding a document does not itself remove working code.
- Do not reject or supersede an ADR without a new approved decision. If the user has not chosen a replacement, retain the current status and append a discussion entry. Do not invent a replacement merely to enable a status transition.
- Preserve legacy `rejected` records that meant replacement; interpret their history and replacement links without silently rewriting old statuses.
- If a dependency is rejected or superseded, pause affected work and have the architect assess the impact. Do not silently rewire approved decisions.

## Document graph

- Read the [templates](references/templates.md) for field meanings and the [portability guidance](references/portability.md) in a new environment. The generator is authoritative for ADR rendering; use the evidence templates for the separate evidence documents.
- Store ADRs as `docs/adr/ADR-0001-short-slug.md` and evidence as `docs/evidence/EVID-0001-short-slug.md`. Choose the next unused number with existing history in mind; do not renumber old documents.
- Use explicit relative Markdown links and relationship types: `replaces` / `replaced_by`, `depends_on` / `required_by`, `extends` / `extended_by`, and `evidence` / `proves`. Maintain backlinks and identify whether evidence proves implementation or the reason for rejection/replacement.
- Keep ADR records and relationships in `docs/adr/registry.json` as the canonical state. ADR Markdown, DOT and GraphML are generated projections; evidence remains in `docs/evidence/` and is linked with hashes. No graph database is required. At handoffs run `sync` to check references, backlinks, cycles, evidence integrity and projection consistency.
- At the end of each step, report the ADR status, result, document links, and the specific decision needed if waiting for the user. Do not describe merely approved or implemented-but-unverified work as completed.
