# databricks-skills-template

A template for managing agent skills as a git repo, with bi-directional sync to a Databricks workspace. Fork or clone this, add your own skills under `skills/`, and use the included tool to keep your repo and a workspace in sync — per skill, in either direction, without ever deleting implicitly.

## Why use this

- **One pattern for two destinations.** The same `skills/` folder layout is what an agent (e.g. Claude Code, Genie Code) loads from. Copy it to a local skills directory; sync it to a Databricks workspace. Same source of truth.
- **Collaboration via git.** Branches, PRs, code review — skills are just files, treat them like code.
- **Workspace edits aren't lost.** A skill authored directly in the workspace is pulled into the repo on next sync, not overwritten. Real conflicts prompt you to decide.
- **Per-user state.** The sync lockfile is gitignored, so multiple people can fork this template and each sync to their own workspace without stepping on each other.

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
│   ├── README.md             # Sync tool usage, state model, recovery semantics
│   └── sync_skills.py        # Push/pull skills to/from a Databricks workspace
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

## Syncing skills to a local agent (e.g. Claude Code)

The `skills/` directory mirrors the agent's skills directory, so a plain copy works:

```bash
# Mirror all skills
rsync -av skills/ ~/.claude/skills/

# Symlink a single skill (live updates as you edit the repo)
ln -s "$PWD/skills/hello-world" ~/.claude/skills/hello-world
```

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
