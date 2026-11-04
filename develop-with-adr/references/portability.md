# Portability between Codex and Claude Code

Use the same folder containing `SKILL.md` and `references/` in both environments. The `agents/openai.yaml` file contains only Codex UI metadata; the workflow must not depend on it. For portable installation, name the folder `develop-with-adr` to match the skill name. A platform-managed installation may assign its own internal folder name.

For local Codex, place the folder in the skills directory supported by that installation. For Claude Code, use the project's `.claude/skills/develop-with-adr/` or the user's `~/.claude/skills/develop-with-adr/`. Do not install into other environments without a user request. Verify actual skill and separate-agent support in the target installation; the presence of a file does not prove agent capabilities are available.

Explicitly pass document paths and facts to agents. Do not assume a subagent automatically inherits the skill, dialogue, permissions, or tools. Have each agent read the required files. Route approval requests through the main user conversation and bind the response to a specific ADR and version.

Keep the architect separate from the implementer and have the architect personally execute checks. If the architect's tools cannot perform verification, report the blocker and leave the ADR incomplete. Do not replace independent verification with implementer self-verification.
