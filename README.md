# public-skills

A collection of agent skills. The `skills/` directory mirrors the shape of the destination skills directory your AI agent loads from, so syncing is a one-step copy in either direction.

## Layout

```
public-skills/
├── README.md
├── scripts/
│   ├── README.md             # Sync tool usage
│   └── sync_skills.py        # Push/pull skills to/from a Databricks workspace
├── config/
│   └── workspaces.example.toml   # Copy to workspaces.toml (gitignored)
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
cp config/workspaces.example.toml config/workspaces.toml
# edit config/workspaces.toml

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

When you don't want to clone the whole repo:

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/zaxier/public-skills.git /tmp/public-skills
cd /tmp/public-skills
git sparse-checkout set skills/hello-world
cp -r skills/hello-world <dest>/skills/
```

## Adding a new skill

1. Create a new folder under `skills/`: `mkdir -p skills/my-skill/{scripts,references,assets}`
2. Add a `SKILL.md` with YAML frontmatter (`name`, `description`)
3. Add any scripts, references, or assets the skill needs
4. Open a PR
