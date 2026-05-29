#!/usr/bin/env python3
"""Sync `skills/` between this repo and a Databricks workspace.

Subcommands:
  plan   — print what would happen; never writes.
  apply  — execute; prompts interactively on conflict.

Per-skill states:
  local-only      → PUSH   (create in workspace)
  remote-only     → PULL   (copy into repo; commit yourself)
  identical       → SKIP
  local-ahead     → PUSH   (state says workspace == last sync; only local changed)
  remote-ahead    → PULL   (state says local == last sync; only workspace changed)
  diverged        → CONFLICT (both changed vs. last sync — prompt)
  unknown         → SOFT CONFLICT (no state entry; hashes differ — prompt)
  unknown-match   → SKIP + baseline (no state entry but hashes match; adopt)
  no-pull         → SKIP   (remote SKILL.md has no_pull: true — stays in workspace)

State (.skills-sync-state.json) is per-user, per-machine, gitignored. Use
--stateless to ignore it entirely (any mismatch becomes a conflict).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
STATE_FILE = REPO_ROOT / ".skills-sync-state.json"
CONFIG_FILE = REPO_ROOT / "skills-sync.toml"

IGNORE_NAMES = {".DS_Store", "__pycache__", ".pytest_cache"}


# --- hashing ---------------------------------------------------------------


def hash_skill(skill_dir: Path) -> str:
    """Canonical sha256 of a skill folder.

    Hashes each file's relative path and content in sorted order. Skips
    junk files (see IGNORE_NAMES) so syncing through hosts that drop
    .DS_Store doesn't churn the hash.
    """
    h = hashlib.sha256()
    files = sorted(_walk_files(skill_dir), key=lambda p: p.relative_to(skill_dir).as_posix())
    for f in files:
        rel = f.relative_to(skill_dir).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _walk_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if any(part in IGNORE_NAMES for part in p.relative_to(root).parts):
            continue
        if p.is_file():
            yield p


# --- harness filtering -----------------------------------------------------


def _skill_harnesses(skill: Path) -> set[str] | None:
    """Return the harnesses set from SKILL.md frontmatter, or None (= all harnesses).

    SKILL.md frontmatter format:
      harnesses: [databricks, claude-code, codex, cursor]

    When the field is absent, the skill is included everywhere (default behaviour).
    """
    skill_md = skill / "SKILL.md"
    if not skill_md.exists():
        return None
    text = skill_md.read_text("utf-8")
    if not text.startswith("---"):
        return None
    try:
        end = text.index("---", 3)
    except ValueError:
        return None
    for line in text[3:end].splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip() == "harnesses":
            raw = v.strip().strip("[]")
            return {h.strip() for h in raw.split(",") if h.strip()}
    return None


# --- config & state --------------------------------------------------------


@dataclass
class WorkspaceTarget:
    name: str
    profile: str
    path: str  # remote /Workspace/.../skills root


def load_workspace(name: str) -> WorkspaceTarget:
    if not CONFIG_FILE.exists():
        sys.exit(
            f"No config at {CONFIG_FILE.relative_to(REPO_ROOT)}. "
            f"Copy skills-sync.example.toml to skills-sync.toml and edit it."
        )
    cfg = tomllib.loads(CONFIG_FILE.read_text("utf-8"))
    entry = cfg.get("workspaces", {}).get(name)
    if not entry:
        available = ", ".join(cfg.get("workspaces", {}).keys()) or "(none)"
        sys.exit(f"Unknown workspace '{name}'. Available: {available}")
    return WorkspaceTarget(name=name, profile=entry["profile"], path=entry["path"].rstrip("/"))


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"version": 1, "workspaces": {}}
    try:
        return json.loads(STATE_FILE.read_text("utf-8"))
    except json.JSONDecodeError as e:
        print(
            f"WARN: state file {STATE_FILE.name} is corrupt ({e}); "
            f"treating as empty. Conflicts may be over-prompted.",
            file=sys.stderr,
        )
        return {"version": 1, "workspaces": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", "utf-8")


def state_for(state: dict, ws: str, skill: str) -> str | None:
    return (
        state.get("workspaces", {})
        .get(ws, {})
        .get("skills", {})
        .get(skill, {})
        .get("hash")
    )


def write_state(state: dict, ws: str, skill: str, h: str) -> None:
    state.setdefault("workspaces", {}).setdefault(ws, {}).setdefault("skills", {})[skill] = {
        "hash": h,
        "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def drop_state(state: dict, ws: str, skill: str) -> None:
    skills = state.get("workspaces", {}).get(ws, {}).get("skills", {})
    skills.pop(skill, None)


# --- databricks CLI wrappers ----------------------------------------------


def db_run(args: list[str], profile: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["databricks", *args, "--profile", profile],
        capture_output=True,
        text=True,
        check=check,
    )


def _remote_no_pull(target: WorkspaceTarget, skill: str) -> bool:
    """Return True if the remote skill's SKILL.md declares no_pull: true.

    Fetches only the SKILL.md file (not the full skill directory) and checks
    its frontmatter. Used during plan building to avoid pulling workspace-origin
    skills that should stay remote.
    """
    r = db_run(
        ["workspace", "export", f"{target.path}/{skill}/SKILL.md"],
        target.profile,
        check=False,
    )
    if r.returncode != 0:
        return False
    text = r.stdout
    if not text.startswith("---"):
        return False
    try:
        end = text.index("---", 3)
    except ValueError:
        return False
    for line in text[3:end].splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip() == "no_pull":
            return v.strip().lower() in ("true", "yes", "1")
    return False


def remote_list_skills(target: WorkspaceTarget) -> list[str]:
    """Names of subdirectories under target.path that look like skills (contain SKILL.md)."""
    r = db_run(["workspace", "list", target.path, "-o", "json"], target.profile, check=False)
    if r.returncode != 0:
        blob = r.stderr + r.stdout
        if "RESOURCE_DOES_NOT_EXIST" in blob or "doesn't exist" in blob or "does not exist" in blob:
            return []
        sys.exit(f"databricks workspace list failed:\n{r.stderr}")
    items = json.loads(r.stdout or "[]")
    names: list[str] = []
    for it in items:
        if it.get("object_type") != "DIRECTORY":
            continue
        name = Path(it["path"]).name
        # Verify it's a skill (has SKILL.md). Cheap call.
        skill_check = db_run(
            ["workspace", "get-status", f"{target.path}/{name}/SKILL.md", "-o", "json"],
            target.profile,
            check=False,
        )
        if skill_check.returncode == 0:
            names.append(name)
        else:
            print(f"  (skipping remote {name}/ — no SKILL.md)", file=sys.stderr)
    return names


def remote_export_skill(target: WorkspaceTarget, skill: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    # export-dir creates dest/<skill>; we want dest/<skill> to BE the skill dir
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / skill
        r = db_run(
            ["workspace", "export-dir", f"{target.path}/{skill}", str(tmp_path), "--overwrite"],
            target.profile,
            check=False,
        )
        if r.returncode != 0:
            sys.exit(f"export-dir failed for {skill}:\n{r.stderr}")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(tmp_path), str(dest))


def remote_import_skill(target: WorkspaceTarget, skill_dir: Path, skill: str) -> None:
    # Ensure remote root exists; import-dir errors if intermediates are missing.
    db_run(["workspace", "mkdirs", target.path], target.profile, check=False)
    r = db_run(
        ["workspace", "import-dir", str(skill_dir), f"{target.path}/{skill}", "--overwrite"],
        target.profile,
        check=False,
    )
    if r.returncode != 0:
        sys.exit(f"import-dir failed for {skill}:\n{r.stderr}")


def remote_hash_skill(target: WorkspaceTarget, skill: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / skill
        remote_export_skill(target, skill, out)
        return hash_skill(out)


# --- planning --------------------------------------------------------------


ACTIONS = {
    "PUSH": "→",
    "PULL": "←",
    "SKIP": "·",
    "CONFLICT": "!",
}


@dataclass
class SkillPlan:
    name: str
    state: str  # local-only | remote-only | identical | local-ahead | remote-ahead | diverged | unknown | unknown-match
    action: str  # PUSH | PULL | SKIP | CONFLICT
    local_hash: str | None
    remote_hash: str | None


def build_plan(target: WorkspaceTarget, state: dict, stateless: bool) -> list[SkillPlan]:
    local_names = sorted(
        p.name for p in SKILLS_DIR.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
        and ((h := _skill_harnesses(p)) is None or "databricks" in h)
    )
    remote_names = sorted(remote_list_skills(target))
    all_names = sorted(set(local_names) | set(remote_names))

    plans: list[SkillPlan] = []
    for name in all_names:
        in_local = name in local_names
        in_remote = name in remote_names
        lh = hash_skill(SKILLS_DIR / name) if in_local else None
        rh = remote_hash_skill(target, name) if in_remote else None

        if in_local and not in_remote:
            plans.append(SkillPlan(name, "local-only", "PUSH", lh, rh))
            continue
        if in_remote and not in_local:
            if _remote_no_pull(target, name):
                plans.append(SkillPlan(name, "no-pull", "SKIP", lh, rh))
            else:
                plans.append(SkillPlan(name, "remote-only", "PULL", lh, rh))
            continue
        if lh == rh:
            plans.append(SkillPlan(name, "identical", "SKIP", lh, rh))
            continue

        if stateless:
            plans.append(SkillPlan(name, "diverged", "CONFLICT", lh, rh))
            continue

        baseline = state_for(state, target.name, name)
        if baseline is None:
            # No state entry; hashes differ → can't infer direction. Soft conflict.
            plans.append(SkillPlan(name, "unknown", "CONFLICT", lh, rh))
        elif baseline == rh:
            # Remote unchanged; local moved.
            plans.append(SkillPlan(name, "local-ahead", "PUSH", lh, rh))
        elif baseline == lh:
            # Local unchanged; remote moved.
            if _remote_no_pull(target, name):
                plans.append(SkillPlan(name, "no-pull", "SKIP", lh, rh))
            else:
                plans.append(SkillPlan(name, "remote-ahead", "PULL", lh, rh))
        else:
            # Both moved vs. baseline.
            plans.append(SkillPlan(name, "diverged", "CONFLICT", lh, rh))
    return plans


def print_plan(target: WorkspaceTarget, plans: list[SkillPlan]) -> None:
    print(f"Workspace: {target.name}  (profile={target.profile}, path={target.path})")
    print()
    if not plans:
        print("  (no skills found on either side)")
        return
    width = max(len(p.name) for p in plans)
    for p in plans:
        arrow = ACTIONS[p.action]
        print(f"  {p.name.ljust(width)}  [{p.state:<13}]  {p.action:<8} {arrow}")
    print()
    counts = {a: 0 for a in ACTIONS}
    for p in plans:
        counts[p.action] += 1
    print(
        f"{counts['PUSH']} to push, {counts['PULL']} to pull, "
        f"{counts['SKIP']} unchanged, {counts['CONFLICT']} conflicts"
    )


# --- apply -----------------------------------------------------------------


def prompt_conflict(p: SkillPlan, target: WorkspaceTarget, batch: str | None) -> str:
    """Return one of: push, pull, skip."""
    if batch == "push-all":
        return "push"
    if batch == "pull-all":
        return "pull"
    if batch == "skip-conflicts":
        return "skip"

    print()
    print(f"  CONFLICT: {p.name}  ({p.state})")
    print(f"    local  hash: {p.local_hash}")
    print(f"    remote hash: {p.remote_hash}")
    while True:
        choice = input("    push / pull / skip / diff > ").strip().lower()
        if choice in {"push", "p"}:
            return "push"
        if choice in {"pull", "u"}:
            return "pull"
        if choice in {"skip", "s", ""}:
            return "skip"
        if choice in {"diff", "d"}:
            show_diff(p, target)
        else:
            print("    enter push / pull / skip / diff")


def show_diff(p: SkillPlan, target: WorkspaceTarget) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        remote_copy = Path(tmp) / p.name
        remote_export_skill(target, p.name, remote_copy)
        local_copy = SKILLS_DIR / p.name
        r = subprocess.run(
            ["diff", "-ruN", str(remote_copy), str(local_copy)],
            capture_output=True,
            text=True,
        )
        # diff exit code 1 just means "differences found"
        out = r.stdout or "(no textual diff output)"
        print("    --- remote (workspace)")
        print("    +++ local  (repo)")
        for line in out.splitlines():
            print(f"    {line}")


def apply_plan(
    target: WorkspaceTarget,
    plans: list[SkillPlan],
    state: dict,
    stateless: bool,
    batch: str | None,
) -> None:
    for p in plans:
        action = p.action
        if action == "CONFLICT":
            resolved = prompt_conflict(p, target, batch)
            if resolved == "skip":
                print(f"  {p.name}: skipped")
                continue
            action = "PUSH" if resolved == "push" else "PULL"

        if action == "SKIP":
            # Baseline an unknown-match so future runs are quiet.
            if not stateless and p.state == "identical" and state_for(state, target.name, p.name) is None:
                write_state(state, target.name, p.name, p.local_hash or "")
            continue

        if action == "PUSH":
            print(f"  {p.name}: pushing →")
            remote_import_skill(target, SKILLS_DIR / p.name, p.name)
            if not stateless:
                write_state(state, target.name, p.name, p.local_hash or hash_skill(SKILLS_DIR / p.name))
        elif action == "PULL":
            print(f"  {p.name}: pulling ←")
            remote_export_skill(target, p.name, SKILLS_DIR / p.name)
            if not stateless:
                write_state(state, target.name, p.name, hash_skill(SKILLS_DIR / p.name))

    if not stateless:
        save_state(state)
        print(f"\nState written to {STATE_FILE.name}")


# --- entry point -----------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync skills/ to/from a Databricks workspace.")
    parser.add_argument("command", choices=["plan", "apply"])
    parser.add_argument("--workspace", "-w", required=True, help="Named target from skills-sync.toml.")
    parser.add_argument("--stateless", action="store_true", help="Ignore .skills-sync-state.json entirely.")
    parser.add_argument(
        "--push-all", action="store_true", help="On apply, resolve every conflict by pushing."
    )
    parser.add_argument(
        "--pull-all", action="store_true", help="On apply, resolve every conflict by pulling."
    )
    parser.add_argument(
        "--skip-conflicts", action="store_true", help="On apply, leave every conflict untouched."
    )
    args = parser.parse_args()

    batch_flags = [
        ("push-all", args.push_all),
        ("pull-all", args.pull_all),
        ("skip-conflicts", args.skip_conflicts),
    ]
    on = [name for name, v in batch_flags if v]
    if len(on) > 1:
        sys.exit(f"--push-all / --pull-all / --skip-conflicts are mutually exclusive (got: {', '.join(on)})")
    batch = on[0] if on else None

    if not SKILLS_DIR.exists():
        sys.exit(f"No skills/ directory at {SKILLS_DIR}")

    target = load_workspace(args.workspace)
    state = {} if args.stateless else load_state()

    plans = build_plan(target, state, stateless=args.stateless)
    print_plan(target, plans)

    if args.command == "plan":
        return 0

    if not plans:
        return 0
    print("\nApplying...")
    apply_plan(target, plans, state, stateless=args.stateless, batch=batch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
