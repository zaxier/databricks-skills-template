# Usage

How to distribute the skills and commands in this repo to each destination. For the authoritative per-flag reference (state model, conflict resolution, recovery), see [`scripts/README.md`](../scripts/README.md).

## Prerequisites

- **Python 3.11+** (for `tomllib` in the standard library). Required by every script.
- **[Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/install) v0.200+** on `PATH`, with an authenticated profile in `~/.databrickscfg` — only needed for `sync_skills.py` (workspace sync). The local link/compile tools don't need it.

## Layout

```
.
├── README.md
├── docs/                     # This guide + harness-targeting reference
├── scripts/
│   ├── README.md             # Full tool reference: flags, state model, conflicts
│   ├── sync_skills.py        # Push/pull skills to/from a Databricks workspace
│   ├── link_skills.py        # Symlink skills into Claude Code / Codex
│   ├── compile_cursor.py     # Compile SKILL.md → Cursor .mdc rule files
│   ├── link_commands.py      # Symlink commands into Claude Code / Cursor
│   └── sync_all.py           # Run every local step (and optionally DB) at once
├── skills-sync.example.toml  # Copy to skills-sync.toml (gitignored)
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md          # Frontmatter + instructions
│       ├── scripts/          # Executable logic (Python, shell, ...)
│       ├── references/       # Longer-form docs the skill references
│       └── assets/           # Static files (templates, sample data, images)
└── commands/
    └── <name>.md             # A single file → a /<name> slash command
```

## One command for everything local

`sync_all.py` runs all the local steps for the project you're in:

```bash
python3 scripts/sync_all.py --dry-run   # preview
python3 scripts/sync_all.py             # apply
```

That links skills into `.claude/skills/` and `.codex/skills/`, compiles Cursor rules into `.cursor/rules/`, and links commands into `.claude/commands/` and `.cursor/commands/`. The Databricks workspace sync is **opt-in** — add `--include-db` (or `--workspace NAME`). Every flag is documented in [`scripts/README.md`](../scripts/README.md).

Prefer to run the tools individually? Read on.

## Skills → Claude Code / Codex

`link_skills.py` symlinks each skill folder into a configured target. Edits in this repo take effect immediately — no copy step.

```bash
python3 scripts/link_skills.py status --target claude-code-user
python3 scripts/link_skills.py link   --target claude-code-user

# Project-level: cd into your project, then use a relative-path target
cd ~/repos/my-project
python3 ~/repos/databricks-skills-template/scripts/link_skills.py link --target claude-code-project

python3 scripts/link_skills.py unlink --target claude-code-user
```

Targets are defined in `skills-sync.toml`. Pre-populated ones cover Claude Code (user + project), Codex (user + project), and Rovo Dev.

> **Claude Code caveat:** Claude Code ignores `~/.claude/skills/` when a project has its own `.claude/skills/`. Use the per-target `skills` allowlist to keep user-level and project-level sets distinct.

## Skills → Cursor rules

Cursor reads `.mdc` files from a flat directory — it can't load `SKILL.md` subdirectories. `compile_cursor.py` compiles each `SKILL.md` into a `<skill-name>.mdc` with Cursor-compatible frontmatter (`alwaysApply: false`, so the rule is agent-requested).

```bash
python3 scripts/compile_cursor.py status  --target cursor-user
python3 scripts/compile_cursor.py compile --target cursor-user
python3 scripts/compile_cursor.py clean   --target cursor-user   # remove generated files
```

Generated files carry an internal marker so `status`/`clean` never touch hand-written Cursor rules. **Unlike symlinks, compiled files don't auto-update** — re-run `compile` after editing a `SKILL.md` (`status` shows `stale` files).

## Commands → slash commands

A command is a single `.md` file that becomes a `/<name>` slash command. `link_commands.py` symlinks `commands/*.md` into an agent's commands directory.

```bash
python3 scripts/link_commands.py status --target claude-code-project
python3 scripts/link_commands.py link   --target claude-code-project
```

Pre-populated command targets cover Claude Code and Cursor (v1.6+), user and project level. Codex deprecated custom prompts in favour of skills, so it has no command target.

## Skills → Databricks workspace

Reconciles each skill folder between this repo and a workspace, per skill, in either direction. Never deletes implicitly; prompts on real conflicts.

```bash
python3 scripts/sync_skills.py plan  --workspace dev   # dry-run
python3 scripts/sync_skills.py apply --workspace dev   # interactive on conflict
```

See [`scripts/README.md`](../scripts/README.md) for the full state model (lockfile vs. stateless), conflict resolution, and recovery from lost/corrupt state.

## Adding a new skill

1. `mkdir -p skills/my-skill/{scripts,references,assets}`
2. Add a `SKILL.md` with YAML frontmatter (`name`, `description`, optional `harnesses`).
3. Add any scripts, references, or assets the skill needs.
4. Commit, push, and re-distribute. Symlinked targets pick it up automatically; re-run `compile_cursor.py` for Cursor.

## Adding a new command

1. Add `commands/my-command.md` with frontmatter (`description`, optional `argument-hint`). Use `$ARGUMENTS` for passed-in args.
2. `python3 scripts/link_commands.py link --target claude-code-project` (or run `sync_all.py`).

## Pulling a single skill via sparse checkout

When you want one skill out of a colleague's repo without cloning the whole thing:

```bash
git clone --depth 1 --filter=blob:none --sparse <repo-url> /tmp/skills-repo
cd /tmp/skills-repo
git sparse-checkout set skills/<skill-name>
cp -r skills/<skill-name> <dest>/skills/
```
