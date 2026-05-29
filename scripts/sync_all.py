#!/usr/bin/env python3
"""Sync all skills and commands to local agent harnesses and a Databricks workspace.

Run from the target project directory (e.g. work-desktop). Orchestrates
link_skills.py, link_commands.py, compile_cursor.py, and sync_skills.py in sequence.

  python3 ~/path/to/databricks-skills-template/scripts/sync_all.py

Steps run by default:
  claude          link skills   → .claude/skills/    (claude-code-project)
  claude-commands link commands → .claude/commands/  (claude-code-project)
  codex           link skills   → .codex/skills/     (codex-project)
  cursor          compile       → .cursor/rules/     (cursor-project)
  cursor-commands link commands → .cursor/commands/  (cursor-project)

Opt-in step (not run by default — pass --include-db or --workspace NAME):
  db              sync          → Databricks workspace (first configured, or --workspace)

Flags:
  --dry-run / -n          Preview without making changes.
  --force / -f            Replace existing symlinks that point elsewhere
                          (passed through to link_skills.py and link_commands.py).
  --skip-claude           Skip the claude-code-project skills link step.
  --skip-claude-commands  Skip the claude-code-project commands link step.
  --skip-codex            Skip the codex-project link step.
  --skip-cursor           Skip the cursor-project compile step.
  --skip-cursor-commands  Skip the cursor-project commands link step.
  --include-db / --db     Include the Databricks workspace sync step
                          (otherwise skipped by default).
  --workspace NAME        Databricks workspace target (implies --include-db;
                          default workspace is the first entry in toml).
  --interactive / -i      Prompt before each step; pass conflicts through to
                          sync_skills.py interactively rather than skipping them.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
CONFIG_FILE = REPO_ROOT / "skills-sync.toml"

LINK_PY = SCRIPTS_DIR / "link_skills.py"
LINK_COMMANDS_PY = SCRIPTS_DIR / "link_commands.py"
COMPILE_PY = SCRIPTS_DIR / "compile_cursor.py"
SYNC_PY = SCRIPTS_DIR / "sync_skills.py"

_PY = sys.executable  # same interpreter that launched this script


# ── helpers ────────────────────────────────────────────────────────────────


def _configured_workspaces() -> list[str]:
    if not CONFIG_FILE.exists():
        return []
    cfg = tomllib.loads(CONFIG_FILE.read_text("utf-8"))
    return list(cfg.get("workspaces", {}).keys())


def _banner(title: str) -> None:
    bar = "─" * 52
    print(f"\n{bar}\n  {title}\n{bar}")


def _step(label: str) -> None:
    print(f"\n▸ {label}")


def _prompt(question: str) -> bool:
    """Prompt yes/no; default yes."""
    while True:
        try:
            ans = input(f"  {question} [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if ans in ("", "y", "yes"):
            return True
        if ans in ("n", "no"):
            return False


def _run(cmd: list) -> bool:
    """Run cmd, return True on success. Output streams directly to terminal."""
    sys.stdout.flush()  # drain buffered prints before subprocess output appears
    result = subprocess.run([str(c) for c in cmd])
    return result.returncode == 0


# ── main ───────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync all skills to local harnesses and Databricks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Preview without making changes.")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Replace existing symlinks that point elsewhere.")
    parser.add_argument("--skip-claude", action="store_true",
                        help="Skip the claude-code-project skills link step.")
    parser.add_argument("--skip-claude-commands", action="store_true",
                        help="Skip the claude-code-project commands link step.")
    parser.add_argument("--skip-codex", action="store_true",
                        help="Skip the codex-project link step.")
    parser.add_argument("--skip-cursor", action="store_true",
                        help="Skip the cursor-project compile step.")
    parser.add_argument("--skip-cursor-commands", action="store_true",
                        help="Skip the cursor-project commands link step.")
    parser.add_argument("--include-db", "--db", dest="include_db", action="store_true",
                        help="Include the Databricks workspace sync step "
                             "(skipped by default).")
    parser.add_argument("--workspace", "-w", metavar="NAME",
                        help="Databricks workspace target name "
                             "(implies --include-db; default: first in toml).")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Prompt before each step; handle DB conflicts interactively.")
    args = parser.parse_args()

    dry = args.dry_run
    dry_flag = ["--dry-run"] if dry else []
    force_flag = ["--force"] if args.force else []

    # DB sync is opt-in: enabled by --include-db or by passing --workspace.
    include_db = args.include_db or bool(args.workspace)

    # Resolve workspace
    workspaces = _configured_workspaces()
    workspace = args.workspace or (workspaces[0] if workspaces else None)
    if include_db and workspace is None:
        print("No workspaces configured in skills-sync.toml — cannot --include-db.")
        return 1

    _banner(f"skills sync{'  (dry-run)' if dry else ''}")
    print(f"  repo:      {REPO_ROOT}")
    print(f"  cwd:       {Path.cwd()}")
    if include_db:
        print(f"  workspace: {workspace}")
    else:
        print("  workspace: (skipped — pass --include-db or --workspace NAME to sync)")

    failures: list[str] = []

    # ── Step: claude-code-project skills ──────────────────────────────────
    if not args.skip_claude:
        _step("claude-code-project  →  .claude/skills/")
        if not args.interactive or _prompt("Run this step?"):
            ok = _run([_PY, LINK_PY, "link", "--target", "claude-code-project"] + dry_flag + force_flag)
            if not ok:
                failures.append("claude")

    # ── Step: claude-code-project commands ────────────────────────────────
    if not args.skip_claude_commands:
        _step("claude-code-project  →  .claude/commands/")
        if not args.interactive or _prompt("Run this step?"):
            ok = _run([_PY, LINK_COMMANDS_PY, "link", "--target", "claude-code-project"] + dry_flag + force_flag)
            if not ok:
                failures.append("claude-commands")

    # ── Step: codex-project ───────────────────────────────────────────────
    if not args.skip_codex:
        _step("codex-project  →  .codex/skills/")
        if not args.interactive or _prompt("Run this step?"):
            ok = _run([_PY, LINK_PY, "link", "--target", "codex-project"] + dry_flag + force_flag)
            if not ok:
                failures.append("codex")

    # ── Step: cursor-project rules ────────────────────────────────────────
    if not args.skip_cursor:
        _step("cursor-project  →  .cursor/rules/")
        if not args.interactive or _prompt("Run this step?"):
            ok = _run([_PY, COMPILE_PY, "compile", "--target", "cursor-project"] + dry_flag)
            if not ok:
                failures.append("cursor")

    # ── Step: cursor-project commands ─────────────────────────────────────
    if not args.skip_cursor_commands:
        _step("cursor-project  →  .cursor/commands/")
        if not args.interactive or _prompt("Run this step?"):
            ok = _run([_PY, LINK_COMMANDS_PY, "link", "--target", "cursor-project"] + dry_flag + force_flag)
            if not ok:
                failures.append("cursor-commands")

    # ── Step: Databricks workspace ────────────────────────────────────────
    if include_db:
        _step(f"databricks  →  {workspace}")
        if not args.interactive or _prompt(f"Sync to workspace '{workspace}'?"):
            if dry:
                # sync_skills uses `plan` for dry-run, not apply --dry-run
                cmd = [_PY, SYNC_PY, "plan", "--workspace", workspace]
            elif args.interactive:
                # Let sync_skills prompt natively on conflicts
                cmd = [_PY, SYNC_PY, "apply", "--workspace", workspace]
            else:
                # Non-interactive: skip conflicts (local is being published, not merged)
                cmd = [_PY, SYNC_PY, "apply", "--workspace", workspace, "--skip-conflicts"]
            ok = _run(cmd)
            if not ok:
                failures.append("databricks")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'─' * 52}")
    if failures:
        print(f"  Finished with errors in: {', '.join(failures)}")
        return 1
    print(f"  All steps complete{'.' if not dry else ' (dry-run).'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
