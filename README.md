# databricks-skills-template

A template for managing agent skills as a git repo, with bi-directional sync to a Databricks workspace. Fork or clone this, add your own skills under `skills/`, and use the included tool to keep your repo and a workspace in sync — per skill, in either direction, without ever deleting implicitly.

## Why use this

- **One pattern for two destinations.** The same `skills/` folder layout is what an agent (e.g. Claude Code, Genie Code) loads from. Copy it to a local skills directory; sync it to a Databricks workspace. Same source of truth.
- **Collaboration via git.** Branches, PRs, code review — skills are just files, treat them like code.
- **Workspace edits aren't lost.** A skill authored directly in the workspace is pulled into the repo on next sync, not overwritten. Real conflicts prompt you to decide.
- **Per-user state.** The sync lockfile is gitignored, so multiple people can fork this template and each sync to their own workspace without stepping on each other.

## Prerequisites

- **Python 3.11+** (for `tomllib` in the standard library).
- **[Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/install) v0.200+** on `PATH`, with an authenticated profile in `~/.databrickscfg`. Required for `sync_skills.py`; not needed for `link_skills.py`.

## How to use this template

1. Click **Use this template** on GitHub (or fork it).
2. Clone your new repo locally.
3. Copy the workspace config: `cp skills-sync.example.toml skills-sync.toml` and edit it for your Databricks profile and target path.
4. Add skills under `skills/<skill-name>/`. The included `hello-world` is a worked example you can keep, rename, or delete.
5. Sync: `python3 scripts/sync_skills.py plan --workspace <name>` then `apply`.

## Layout

```
.
├── README.md
├── scripts/
│   ├── README.md             # Tool usage, state model, recovery semantics
│   ├── sync_skills.py        # Push/pull skills to/from a Databricks workspace
│   └── link_skills.py        # Symlink skills into a local agent skills dir
├── skills-sync.example.toml  # Copy to skills-sync.toml (gitignored)
└── skills/
    └── <skill-name>/
        ├── SKILL.md          # Frontmatter + instructions
        ├── scripts/          # Executable logic (Python, shell, ...)
        ├── references/       # Longer-form docs the skill references
        └── assets/           # Static files (templates, sample data, images)
```

## Syncing skills to a Databricks workspace

Reconciles each skill folder between this repo and a workspace, per skill, in either direction. Never deletes implicitly; prompts on real conflicts.

```bash
# One-time setup
cp skills-sync.example.toml skills-sync.toml
# edit skills-sync.toml

# Dry-run
python3 scripts/sync_skills.py plan --workspace dev

# Execute (interactive on conflict)
python3 scripts/sync_skills.py apply --workspace dev
```

See [scripts/README.md](scripts/README.md) for the full state model (lockfile vs. stateless), conflict resolution, and recovery from lost/corrupt state.

## Syncing skills to a local agent (Claude Code, Rovo Dev, etc.)

The `skills/` directory mirrors the agent's skills directory. Use `link_skills.py` to symlink each skill into a configured target — edits in this repo take effect immediately, no copy step.

```bash
# Edit skills-sync.toml — pre-populated targets cover Claude Code (user + project) and Rovo Dev

# See what would happen
python3 scripts/link_skills.py status --target claude-code-user

# Link every skill
python3 scripts/link_skills.py link --target claude-code-user

# Project-level: cd into your project, then link with a relative-path target
cd ~/repos/my-project
python3 ~/repos/databricks-skills-template/scripts/link_skills.py link --target claude-code-project
```

See [scripts/README.md](scripts/README.md) for target semantics, conflict handling, and harness compatibility (Cursor / Continue use a different rules format and are not supported).

## Pulling a single skill via sparse checkout

When you want one skill out of a colleague's repo without cloning the whole thing:

```bash
git clone --depth 1 --filter=blob:none --sparse \
  <repo-url> /tmp/skills-repo
cd /tmp/skills-repo
git sparse-checkout set skills/<skill-name>
cp -r skills/<skill-name> <dest>/skills/
```

## Adding a new skill

1. Create a new folder under `skills/`: `mkdir -p skills/my-skill/{scripts,references,assets}`
2. Add a `SKILL.md` with YAML frontmatter (`name`, `description`)
3. Add any scripts, references, or assets the skill needs
4. Commit, push, sync.
