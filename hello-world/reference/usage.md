# hello-world — usage reference

Extended notes for the `hello-world` skill.

## Examples

```bash
# Default greeting
python3 hello.py
# → Hello, world!

# Custom name
python3 hello.py --name "Xavier"
# → Hello, Xavier!

# Load template from the asset file
python3 hello.py --from-asset --name "Xavier"
# → G'day, Xavier!
```

## Anatomy of a skill in this repo

A skill folder is self-contained:

| Path | Purpose |
| --- | --- |
| `SKILL.md` | YAML frontmatter (`name`, `description`) + human/agent-readable instructions. The `description` is what Claude uses to decide whether to invoke the skill. |
| `*.py` (or other code) | Executable logic the skill can shell out to. |
| `reference/` | Longer-form docs the skill points the agent at when needed. Keep `SKILL.md` short; put depth here. |
| `assets/` | Static files (templates, sample data, images) the skill loads at runtime. |

## Writing the frontmatter

Keep `description` specific — include the trigger phrases a user is likely to say. The agent matches against it when deciding which skill to load.
