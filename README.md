# public-skills

A collection of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills. Each skill lives in its own top-level folder and can be cloned into a local skills directory.

## Layout

```
public-skills/
├── README.md
└── <skill-name>/
    ├── SKILL.md          # Frontmatter + instructions
    ├── *.py              # Optional scripts
    ├── reference/        # Reference docs the skill can pull in
    └── assets/           # Static assets (templates, images, data)
```

## Installing a skill

Skills are discovered from `~/.claude/skills/` (user-level) or `.claude/skills/` (project-level).

Clone an individual skill into your skills directory:

```bash
# User-level
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/zaxier/public-skills.git /tmp/public-skills
cd /tmp/public-skills && git sparse-checkout set hello-world
cp -r hello-world ~/.claude/skills/
```

Or clone the whole repo and symlink the skills you want:

```bash
git clone https://github.com/zaxier/public-skills.git ~/code/public-skills
ln -s ~/code/public-skills/hello-world ~/.claude/skills/hello-world
```

## Adding a new skill

1. Create a new folder at the repo root: `mkdir my-skill`
2. Add a `SKILL.md` with YAML frontmatter (`name`, `description`)
3. Add any scripts, `reference/`, or `assets/` the skill needs
4. Open a PR
