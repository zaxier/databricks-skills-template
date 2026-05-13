# scripts/

Tooling for getting this repo's `skills/` directory into the places your agents read from:

- `sync_skills.py` — push/pull skills between this repo and a Databricks workspace.
- `link_skills.py` — symlink skills into a local agent skills directory (Claude Code, Rovo Dev, etc.).

Both read targets from `skills-sync.toml` at the repo root.

## `sync_skills.py`

Reconciles each skill folder between this repo and a workspace, per skill, in either direction. Never deletes implicitly.

### Setup (one-time)

```bash
cp skills-sync.example.toml skills-sync.toml
# edit skills-sync.toml — add your profile + remote skills path
```

`skills-sync.toml` is gitignored. Each user keeps their own targets.

### Daily use

```bash
# Dry-run — print what would happen
python3 scripts/sync_skills.py plan --workspace dev

# Execute — prompts interactively on conflict
python3 scripts/sync_skills.py apply --workspace dev
```

### Per-skill actions

For each skill present on either side, the tool picks one of:

| State | Meaning | Action |
| --- | --- | --- |
| `local-only` | In repo, not in workspace | PUSH |
| `remote-only` | In workspace, not in repo | PULL |
| `identical` | Hashes match | SKIP |
| `local-ahead` | State says workspace == last sync; only local changed | PUSH |
| `remote-ahead` | State says local == last sync; only workspace changed | PULL |
| `diverged` | Both changed vs. last sync | CONFLICT — prompt |
| `unknown` | No state entry; hashes differ — can't infer direction | CONFLICT — prompt |
| `unknown-match` | No state entry; hashes match — adopt as baseline | SKIP |

**Never deletes.** A skill missing on one side is a new addition to propagate, not a deletion to mirror.

### State (`.skills-sync-state.json`)

Gitignored, per-user, lives at the repo root. Tracks the last-synced hash per skill per workspace target. This is what lets the tool tell "clean push" from "clean pull" from "real conflict."

If the file is missing or corrupt, the tool degrades safely:

- Skills whose local/remote hashes match → silently baselined.
- Skills whose hashes differ → surfaced as a soft conflict; you decide.

So losing the state file is never catastrophic — at worst you'll be re-prompted on the skills that are actually divergent.

### Stateless mode

```bash
python3 scripts/sync_skills.py apply --workspace dev --stateless
```

Ignores the state file entirely. Any hash mismatch is treated as a conflict. Simpler mental model; noisier on routine work.

### Conflict resolution

On `apply`, each conflict prompts:

```
  CONFLICT: hello-world  (diverged)
    push / pull / skip / diff >
```

- `push` overwrites the workspace with the local copy.
- `pull` overwrites the local copy with the workspace.
- `skip` leaves both alone.
- `diff` shows a unified diff (remote vs. local), then re-prompts.

For non-interactive use:

```bash
--push-all          # resolve every conflict by pushing
--pull-all          # resolve every conflict by pulling
--skip-conflicts    # leave every conflict untouched
```

### Requirements

- Python 3.11+ (for `tomllib`)
- Databricks CLI v0.200+ on `PATH`, authenticated profiles in `~/.databrickscfg`
- `diff` (used only when you select `diff` at the prompt)

## `link_skills.py`

Symlinks each skill folder in `skills/` into a configured local directory — typically your agent's skills dir. Useful when you want edits in this repo to live-update in the agent without copying or re-syncing.

### Targets

Defined in `skills-sync.toml` under `[link_targets.<name>]`. Path semantics:

- `~` expands to your home directory.
- An absolute path (`/Workspace/...` or `/Users/...`) is used as-is.
- A **relative** path resolves against the current working directory at invocation time. This is how project-scoped targets work: `path = ".claude/skills"` means "the `.claude/skills` of whichever project I'm `cd`'d into when I run the script."

Pre-populated targets in `skills-sync.example.toml`:

| Name | Where | Scope |
| --- | --- | --- |
| `claude-code-user` | `~/.claude/skills` | global (every Claude Code session) |
| `claude-code-project` | `.claude/skills` (relative) | project (run from inside the project) |
| `rovo-dev-user` | `~/.rovodev/skills` | global |

Add more as needed. Cursor / Continue use their own rules format and are **not** compatible — symlinking SKILL.md folders into them won't work.

### Usage

```bash
# What's the state of each skill at this target?
python3 scripts/link_skills.py status --target claude-code-user

# Symlink every skill into the target (dry-run first if you want)
python3 scripts/link_skills.py link --target claude-code-user --dry-run
python3 scripts/link_skills.py link --target claude-code-user

# Just one skill
python3 scripts/link_skills.py link --target claude-code-user --skill hello-world

# Project-level: cd into the project first
cd ~/repos/my-project
python3 ~/repos/databricks-skills-template/scripts/link_skills.py link --target claude-code-project

# Remove our symlinks (leaves anything else alone)
python3 scripts/link_skills.py unlink --target claude-code-user
```

### Per-skill state

| State | Meaning | `link` action |
| --- | --- | --- |
| `missing` | Nothing at the destination | create symlink |
| `linked` | Symlink already points back to this repo | skip (idempotent) |
| `conflict-symlink` | A symlink at the destination points elsewhere | skip unless `--force` |
| `conflict-real` | A real file or directory at the destination | refuse — remove it manually first |

`--force` will replace a foreign symlink. It will **not** delete a real directory; that's a manual operation by design.

### When to use `link_skills.py` vs. plain `ln -s` or `rsync`

- **`link_skills.py`** — the right default. Idempotent, conflict-aware, target-driven, and gives you a consistent CLI across machines / harnesses.
- **`ln -s` by hand** — fine for a one-off symlink of a single skill.
- **`rsync`** — when you want a *copy* (not a symlink), e.g. for read-only distribution.
