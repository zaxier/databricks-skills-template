---
name: hello-world
description: Placeholder skill that prints a greeting. Use as a template when creating new skills in this repo. Triggers on phrases like "run hello-world" or "test skill scaffold".
---

# hello-world

A minimal skill used as a scaffold/template for new skills in this repo.

## What it does

Runs `hello.py`, which prints a greeting to stdout. Use this as a reference for how to wire up a script, a reference doc, and an asset inside a skill folder.

## How to use

Run the script directly:

```bash
python3 hello.py
python3 hello.py --name "Xavier"
```

## Files

- `hello.py` — the executable script
- `reference/usage.md` — extended notes and examples
- `assets/greeting.txt` — sample text asset loaded by the script when `--from-asset` is passed

See [reference/usage.md](reference/usage.md) for more.
