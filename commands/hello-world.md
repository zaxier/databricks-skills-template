---
description: Example slash command — runs the hello-world skill's script and reports the greeting.
argument-hint: "[--name NAME] [--from-asset]"
---

Run the `hello-world` example command. The user passed these arguments: `$ARGUMENTS`

Steps:

1. From the repo (or project) root, run the hello-world skill's script,
   forwarding any arguments the user supplied:

   ```bash
   python3 skills/hello-world/scripts/hello.py $ARGUMENTS
   ```

2. Report the greeting it prints back to the user in one line.

This file is a worked example of a **command** — a single `.md` file that
becomes a slash command (`/hello-world`) when linked into an agent's
commands directory by `scripts/link_commands.py`. Use it as a scaffold:
copy it, rename it, and point it at whatever you want the command to do.
Delete it once you have your own.
