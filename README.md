# public-skills

A collection of agent skills. Each skill lives in its own top-level folder and can be cloned into a local skills directory used by your AI coding agent.

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

Skills are discovered from whatever directory your agent loads them from (commonly a user-level `~/.../skills/` or a project-level `.../skills/`). Drop a skill folder into that directory and the agent should pick it up.

Clone a single skill via sparse checkout:

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/zaxier/public-skills.git /tmp/public-skills
cd /tmp/public-skills && git sparse-checkout set hello-world
cp -r hello-world <your-skills-dir>/
```

Or clone the whole repo and symlink the skills you want:

```bash
git clone https://github.com/zaxier/public-skills.git ~/code/public-skills
ln -s ~/code/public-skills/hello-world <your-skills-dir>/hello-world
```

## Adding a new skill

1. Create a new folder at the repo root: `mkdir my-skill`
2. Add a `SKILL.md` with YAML frontmatter (`name`, `description`)
3. Add any scripts, `reference/`, or `assets/` the skill needs
4. Open a PR
