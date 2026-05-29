# scripts/

Tooling for getting this repo's `skills/` and `commands/` into the places your agents read from:

- `sync_skills.py` — push/pull skills between this repo and a Databricks workspace.
- `link_skills.py` — symlink skills into a local agent skills directory (Claude Code, Codex).
- `compile_cursor.py` — compile `SKILL.md` files into Cursor `.mdc` rule files.
- `link_commands.py` — symlink `commands/*.md` into a local agent commands directory (Claude Code, Cursor).
- `sync_all.py` — run every local step (and optionally the workspace sync) in one go.

All read targets from `skills-sync.toml` at the repo root.

## `sync_skills.py`

Reconciles each skill folder between this repo and a workspace, per skill, in either direction. Never deletes implicitly.

### Setup (one-time)

```bash
cp skills-sync.example.toml skills-sync.toml
# edit skills-sync.toml — add your profile + remote skills path
```

`skills-sync.toml` is gitignored. Each user keeps their own targets.

### Daily use

```bash
# Dry-run — print what would happen
python3 scripts/sync_skills.py plan --workspace dev

# Execute — prompts interactively on conflict
python3 scripts/sync_skills.py apply --workspace dev
```

### Per-skill actions

For each skill present on either side, the tool picks one of:

| State | Meaning | Action |
| --- | --- | --- |
| `local-only` | In repo, not in workspace | PUSH |
| `remote-only` | In workspace, not in repo | PULL |
| `identical` | Hashes match | SKIP |
| `local-ahead` | State says workspace == last sync; only local changed | PUSH |
| `remote-ahead` | State says local == last sync; only workspace changed | PULL |
| `diverged` | Both changed vs. last sync | CONFLICT — prompt |
| `unknown` | No state entry; hashes differ — can't infer direction | CONFLICT — prompt |
| `unknown-match` | No state entry; hashes match — adopt as baseline | SKIP |
| `no-pull` | Remote SKILL.md has `no_pull: true` | SKIP — stays in workspace |

**Never deletes.** A skill missing on one side is a new addition to propagate, not a deletion to mirror.

### State (`.skills-sync-state.json`)

Gitignored, per-user, lives at the repo root. Tracks the last-synced hash per skill per workspace target. This is what lets the tool tell "clean push" from "clean pull" from "real conflict."

If the file is missing or corrupt, the tool degrades safely:

- Skills whose local/remote hashes match → silently baselined.
- Skills whose hashes differ → surfaced as a soft conflict; you decide.

So losing the state file is never catastrophic — at worst you'll be re-prompted on the skills that are actually divergent.

### Stateless mode

```bash
python3 scripts/sync_skills.py apply --workspace dev --stateless
```

Ignores the state file entirely. Any hash mismatch is treated as a conflict. Simpler mental model; noisier on routine work.

### Conflict resolution

On `apply`, each conflict prompts:

```
  CONFLICT: hello-world  (diverged)
    push / pull / skip / diff >
```

- `push` overwrites the workspace with the local copy.
- `pull` overwrites the local copy with the workspace.
- `skip` leaves both alone.
- `diff` shows a unified diff (remote vs. local), then re-prompts.

For non-interactive use:

```bash
--push-all          # resolve every conflict by pushing
--pull-all          # resolve every conflict by pulling
--skip-conflicts    # leave every conflict untouched
```

### Requirements

- Python 3.11+ (for `tomllib`)
- Databricks CLI v0.200+ on `PATH`, authenticated profiles in `~/.databrickscfg`
- `diff` (used only when you select `diff` at the prompt)

---

## Harness targeting — restricting which targets a skill syncs to

By default every skill is included at every target (workspace sync, claude-code link, codex link, cursor compile). Add a `harnesses` field to a skill's `SKILL.md` frontmatter to restrict this:

```yaml
---
name: my-workspace-skill
description: Does something specific to Databricks notebooks
harnesses: [databricks]
---
```

Valid values: `databricks`, `claude-code`, `codex`, `cursor`. Use a comma-separated inline list. **Omit the field entirely** to keep the default (sync everywhere).

| harnesses value | Databricks Genie Code | Claude Code | Codex | Cursor |
| --- | :---: | :---: | :---: | :---: |
| _(absent)_ | ✓ | ✓ | ✓ | ✓ |
| `[databricks]` | ✓ | — | — | — |
| `[claude-code, codex, cursor]` | — | ✓ | ✓ | ✓ |
| `[claude-code]` | — | ✓ | — | — |

Skills excluded from a target are silently omitted — they won't appear in `status` output for that target, and won't be linked, compiled, or synced there. The per-target `skills` allowlist in `skills-sync.toml` applies on top of this (a skill must pass both filters to be included).

### Keeping a skill workspace-only (`no_pull: true`)

For skills that originate in the workspace and should never be pulled into the local repo, add `no_pull: true` to the skill's `SKILL.md` frontmatter **in the workspace**:

```yaml
---
name: my-workspace-skill
description: Developed directly in the workspace; not tracked locally
no_pull: true
---
```

`sync_skills.py` reads this field from the remote `SKILL.md` during plan building. Skills with `no_pull: true` are shown as `no-pull` in the plan and always `SKIP`ped — they stay in the workspace and are never copied into the local repo.

## `link_skills.py`

Symlinks each skill folder in `skills/` into a configured local directory — typically your agent's skills dir. Useful when you want edits in this repo to live-update in the agent without copying or re-syncing.

### Targets

Defined in `skills-sync.toml` under `[link_targets.<name>]`. Path semantics:

- `~` expands to your home directory.
- An absolute path (`/Workspace/...` or `/Users/...`) is used as-is.
- A **relative** path resolves against the current working directory at invocation time. This is how project-scoped targets work: `path = ".claude/skills"` means "the `.claude/skills` of whichever project I'm `cd`'d into when I run the script."

Configured targets in `skills-sync.toml`:

| Name | Where | Scope |
| --- | --- | --- |
| `claude-code-user` | `~/.claude/skills` | global (every Claude Code session) |
| `claude-code-project` | `.claude/skills` (relative) | project (run from inside the project) |
| `codex-user` | `~/.codex/skills` | global (every Codex session) |
| `codex-project` | `.codex/skills` (relative) | project (run from inside the project) |

Add more as needed. Cursor uses a different rules format (`.mdc` files in a flat directory) — use `compile_cursor.py` instead of symlinking. Continue is not currently supported.

> **Claude Code caveat:** Claude Code ignores `~/.claude/skills/` entirely when a project has its own `.claude/skills/` directory. Linking the same skill at both levels also causes both to appear in the skill picker (known bug). Use the allowlist (see below) to keep user-level and project-level sets distinct.

### Usage

```bash
# What's the state of each skill at this target?
python3 scripts/link_skills.py status --target claude-code-user

# Symlink every skill into the target (dry-run first if you want)
python3 scripts/link_skills.py link --target claude-code-user --dry-run
python3 scripts/link_skills.py link --target claude-code-user

# Just one skill
python3 scripts/link_skills.py link --target claude-code-user --skill hello-world

# Project-level: cd into the project first
cd ~/repos/my-project
python3 ~/repos/agent-skills-template/scripts/link_skills.py link --target claude-code-project

# Remove our symlinks (leaves anything else alone)
python3 scripts/link_skills.py unlink --target claude-code-user
```

### Skills allowlist

Each `[link_targets.<name>]` block in `skills-sync.toml` accepts an optional `skills` list. When present, only those skill names are operated on for that target — others are silently ignored. Omit the key to operate on all skills (default).

```toml
[link_targets.claude-code-user]
path = "~/.claude/skills"
skills = ["universal-skill"]   # only this skill is linked here

[link_targets.claude-code-project]
path = ".claude/skills"
# no skills key → all skills linked
```

The `--skill` CLI flag applies on top of the allowlist as a further one-off filter.

### Per-skill state

| State | Meaning | `link` action |
| --- | --- | --- |
| `missing` | Nothing at the destination | create symlink |
| `linked` | Symlink already points back to this repo | skip (idempotent) |
| `conflict-symlink` | A symlink at the destination points elsewhere | skip unless `--force` |
| `conflict-real` | A real file or directory at the destination | refuse — remove it manually first |

`--force` will replace a foreign symlink. It will **not** delete a real directory; that's a manual operation by design.

### When to use `link_skills.py` vs. plain `ln -s` or `rsync`

- **`link_skills.py`** — the right default. Idempotent, conflict-aware, target-driven, and gives you a consistent CLI across machines / harnesses.
- **`ln -s` by hand** — fine for a one-off symlink of a single skill.
- **`rsync`** — when you want a *copy* (not a symlink), e.g. for read-only distribution.

## `compile_cursor.py`

Cursor reads `.mdc` files from a flat directory (`~/.cursor/rules/` or `.cursor/rules/`). SKILL.md subdirectories can't be symlinked in — they have to be compiled. This script reads each `SKILL.md`, extracts the frontmatter, and writes a `<skill-name>.mdc` with Cursor-compatible frontmatter.

### Targets

Defined in `skills-sync.toml` under `[cursor_targets.<name>]`. Same path semantics as `link_skills.py` — `~` expands, relative paths resolve against CWD.

Configured targets in `skills-sync.toml`:

| Name | Where | Scope |
| --- | --- | --- |
| `cursor-user` | `~/.cursor/rules` | global (every Cursor project) |
| `cursor-project` | `.cursor/rules` (relative) | project (run from inside the project) |

The `skills` allowlist works the same way as for `link_skills.py`.

### Usage

```bash
# Check state of each skill at a target
python3 scripts/compile_cursor.py status --target cursor-user

# Compile (idempotent)
python3 scripts/compile_cursor.py compile --target cursor-user

# Dry-run
python3 scripts/compile_cursor.py compile --target cursor-user --dry-run

# Just one skill
python3 scripts/compile_cursor.py compile --target cursor-user --skill virt-graph

# Project-level: cd into the project first
cd ~/repos/my-project
python3 ~/repos/agent-skills-template/scripts/compile_cursor.py compile --target cursor-project

# Remove generated .mdc files (leaves foreign files alone)
python3 scripts/compile_cursor.py clean --target cursor-user
```

### Output format

Each `SKILL.md` compiles to:

```
---
description: "<SKILL.md description field>"
alwaysApply: false
# skills-repo:generated
---

<SKILL.md body verbatim>
```

`alwaysApply: false` makes the rule agent-requested — Cursor's AI decides when to inject it based on the description. Generated files are marked with `# skills-repo:generated` so `status` and `clean` can identify them.

### Per-skill states

| State | Meaning | `compile` action |
| --- | --- | --- |
| `missing` | No `.mdc` at the destination | write it |
| `current` | `.mdc` matches expected output | skip (idempotent) |
| `stale` | `.mdc` was generated by us but content differs | overwrite |
| `foreign` | A `.mdc` exists but was not generated by this script | skip — report conflict |

**Re-compile after edits.** Unlike symlinks, compiled files don't update automatically. After editing a `SKILL.md`, run `compile` again. Use `status` to find stale files.

### Requirements

- Python 3.11+ (for `tomllib`)

---

## `link_commands.py`

Symlinks each `commands/<name>.md` file into a configured agent commands directory, so they become slash commands (`/<name>`). Same conflict-safety model as `link_skills.py`, but the symlinks point to files (commands are single `.md` files, not folders).

### Targets

Defined in `skills-sync.toml` under `[command_targets.<name>]`. Same path semantics as the other tools — `~` expands, relative paths resolve against CWD. Each block accepts an optional `commands` allowlist (by stem, without `.md`).

| Name | Where | Scope |
| --- | --- | --- |
| `claude-code-user` | `~/.claude/commands` | global |
| `claude-code-project` | `.claude/commands` (relative) | project |
| `cursor-user` | `~/.cursor/commands` | global (Cursor v1.6+) |
| `cursor-project` | `.cursor/commands` (relative) | project (Cursor v1.6+) |

> Codex deprecated custom prompts (`~/.codex/prompts/`) in favour of skills, so there is no Codex command target.

### Usage

```bash
# State of each command at a target
python3 scripts/link_commands.py status --target claude-code-project

# Symlink every command (dry-run first if you want)
python3 scripts/link_commands.py link --target claude-code-project --dry-run
python3 scripts/link_commands.py link --target claude-code-project

# Just one command (by stem, without .md)
python3 scripts/link_commands.py link --target claude-code-project --command hello-world

# Remove our symlinks (leaves anything else alone)
python3 scripts/link_commands.py unlink --target claude-code-project
```

### Per-command state

| State | Meaning | `link` action |
| --- | --- | --- |
| `missing` | Nothing at the destination | create symlink |
| `linked` | Symlink already points back to this repo | skip (idempotent) |
| `conflict-symlink` | A symlink at the destination points elsewhere | skip unless `--force` |
| `conflict-real` | A real file at the destination | refuse — remove it manually first |

The `commands` allowlist and the `--command` flag combine the same way the skills allowlist and `--skill` flag do for `link_skills.py`.

---

## `sync_all.py`

Orchestrator: runs every local distribution step in sequence so you don't have to invoke each tool by hand. Run it from the target project directory.

```bash
# All local steps for the current project (dry-run first)
python3 scripts/sync_all.py --dry-run
python3 scripts/sync_all.py
```

Steps run by default (all project-scoped):

| Step | Tool | Destination |
| --- | --- | --- |
| claude | `link_skills.py` | `.claude/skills/` |
| claude-commands | `link_commands.py` | `.claude/commands/` |
| codex | `link_skills.py` | `.codex/skills/` |
| cursor | `compile_cursor.py` | `.cursor/rules/` |
| cursor-commands | `link_commands.py` | `.cursor/commands/` |

The Databricks workspace sync is **opt-in** — it only runs when you pass `--include-db` (or `--workspace NAME`, which implies it). Without a name, the first workspace in `skills-sync.toml` is used.

### Flags

| Flag | Effect |
| --- | --- |
| `--dry-run` / `-n` | Preview without making changes |
| `--force` / `-f` | Replace foreign symlinks (passed to the link tools) |
| `--skip-claude` / `--skip-claude-commands` / `--skip-codex` / `--skip-cursor` / `--skip-cursor-commands` | Skip individual local steps |
| `--include-db` / `--db` | Include the workspace sync step |
| `--workspace NAME` / `-w` | Workspace target (implies `--include-db`) |
| `--interactive` / `-i` | Prompt before each step; pass DB conflicts through to `sync_skills.py` interactively |

Non-interactive DB sync uses `--skip-conflicts` (local is being published, not merged), so a divergent workspace skill is never clobbered silently — re-run `sync_skills.py apply` directly to resolve those.
