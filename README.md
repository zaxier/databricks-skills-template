# public-skills

A collection of agent skills. The `skills/` directory mirrors the shape of the destination skills directory your AI agent loads from, so syncing is a one-step copy in either direction.

## Layout

```
public-skills/
├── README.md
├── scripts/                  # (future) sync tooling — sync-to-claude, sync-to-databricks
└── skills/
    └── <skill-name>/
        ├── SKILL.md          # Frontmatter + instructions
        ├── scripts/          # Executable logic (Python, shell, ...)
        ├── references/       # Longer-form docs the skill references
        └── assets/           # Static files (templates, sample data, images)
```

## Syncing skills to a destination

Because `skills/` mirrors the destination, syncing all skills is one command. The destination is whatever directory your agent reads skills from — for example a local Claude Code skills dir, or a `skills/` folder inside a Databricks workspace.

```bash
# Sync everything (mirror — adds/updates; --delete also removes stale skills)
rsync -av --delete public-skills/skills/ <dest>/skills/

# Sync a single skill
rsync -av public-skills/skills/hello-world/ <dest>/skills/hello-world/
```

For a Databricks workspace, replace `rsync` with `databricks workspace import-dir` (or the equivalent CLI/API call) against `/Workspace/.../skills/`.

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
