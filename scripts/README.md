# scripts/

Tooling for keeping the repo's `skills/` directory in sync with a Databricks workspace.

## `sync_skills.py`

Reconciles each skill folder between this repo and a workspace, per skill, in either direction. Never deletes implicitly.

### Setup (one-time)

```bash
cp config/workspaces.example.toml config/workspaces.toml
# edit config/workspaces.toml — add your profile + remote skills path
```

`config/workspaces.toml` is gitignored. Each user keeps their own targets.

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
