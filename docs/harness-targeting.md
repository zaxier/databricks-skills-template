# Harness targeting

By default every skill goes to every destination. Two frontmatter fields plus a per-target allowlist let you control where each skill lands.

## `harnesses:` — restrict a skill to specific destinations

Add a `harnesses:` field to a `SKILL.md` to limit it:

```yaml
---
name: my-workspace-skill
description: Does something specific to Databricks notebooks
harnesses: [databricks]
---
```

Valid values: `databricks`, `claude-code`, `codex`, `cursor`. Omit the field to include the skill everywhere.

| `harnesses` value | Databricks | Claude Code | Codex | Cursor |
| --- | :---: | :---: | :---: | :---: |
| _(absent)_ | ✓ | ✓ | ✓ | ✓ |
| `[databricks]` | ✓ | — | — | — |
| `[claude-code, codex, cursor]` | — | ✓ | ✓ | ✓ |
| `[claude-code]` | — | ✓ | — | — |
| `[codex]` | — | — | ✓ | — |

Each tool matches a skill's `harnesses` against the harness the target represents (`link_skills.py` derives it from the target name, e.g. `codex-user` → `codex`, or from an explicit `harness` key). Skills excluded from a target are silently omitted — they won't appear in that target's `status` output, and won't be linked, compiled, or synced there.

## `skills` allowlist — per target

Each `[link_targets.<name>]` / `[cursor_targets.<name>]` block in `skills-sync.toml` accepts an optional `skills` list. When set, only those skills are operated on for that target. It applies **on top of** `harnesses` — a skill must pass both filters to be included. (`[command_targets.<name>]` blocks have an equivalent `commands` allowlist.)

```toml
[link_targets.claude-code-user]
path = "~/.claude/skills"
skills = ["my-universal-skill"]   # only this skill linked here

[link_targets.claude-code-project]
path = ".claude/skills"
# no skills key → all skills linked
```

## `no_pull: true` — keep a skill workspace-only

For skills authored directly in a Databricks workspace that should never be pulled into the repo, add `no_pull: true` to the skill's `SKILL.md` frontmatter **in the workspace**. `sync_skills.py` reads it during plan building, marks the skill `no-pull`, and always skips it — it stays in the workspace and is never copied locally.

```yaml
---
name: workspace-only-skill
description: Developed directly in the workspace; not tracked in the repo
no_pull: true
---
```

See [`scripts/README.md`](../scripts/README.md) for how these interact with each tool's state model.
