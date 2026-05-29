#!/usr/bin/env python3
"""Symlink `commands/` into local agent command directories.

Reads [command_targets.<name>] from skills-sync.toml. Each entry has a path
and an optional commands allowlist:

  [command_targets.claude-code-project]
  path = ".claude/commands"
  commands = ["sync-ucos"]   # optional — omit to link all commands

  - '~' is expanded to the user's home dir.
  - Relative paths resolve against the current working directory at
    invocation time. This lets project-scoped targets like
    `.claude/commands` follow you into whichever project you cd into.
  - If `commands` is set, only those command names are linked/unlinked
    for that target. Commands not in the list are silently ignored.

Unlike link_skills.py, commands are individual .md files (not folders),
so symlinks point to files.

Subcommands:
  status   show whether each command is linked, missing, or in conflict.
  link     create symlinks (commands/<name>.md → <target>/<name>.md).
  unlink   remove symlinks that point back into this repo.

Safety:
  - Never deletes a real file that isn't a symlink into this repo.
  - On `link`, an existing foreign symlink is skipped unless --force.
  - On `unlink`, anything that isn't a symlink pointing into this repo
    is left alone.
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / "commands"
CONFIG_FILE = REPO_ROOT / "skills-sync.toml"


@dataclass
class CommandTarget:
    name: str
    path: Path                    # resolved absolute path
    allowlist: list[str] | None   # None = all commands; list = only these names


def load_target(name: str) -> CommandTarget:
    if not CONFIG_FILE.exists():
        sys.exit(
            f"No config at {CONFIG_FILE.relative_to(REPO_ROOT)}. "
            f"Copy skills-sync.example.toml to skills-sync.toml and edit it."
        )
    cfg = tomllib.loads(CONFIG_FILE.read_text("utf-8"))
    entry = cfg.get("command_targets", {}).get(name)
    if not entry:
        available = ", ".join(cfg.get("command_targets", {}).keys()) or "(none)"
        sys.exit(f"Unknown command target '{name}'. Available: {available}")
    raw = entry.get("path")
    if not raw:
        sys.exit(f"Target '{name}' is missing 'path'.")
    expanded = Path(os.path.expanduser(raw))
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    allowlist = entry.get("commands")  # list[str] or None
    return CommandTarget(name=name, path=expanded.resolve(), allowlist=allowlist)


def list_commands() -> list[Path]:
    if not COMMANDS_DIR.exists():
        return []
    return sorted(
        p for p in COMMANDS_DIR.iterdir()
        if p.is_file() and p.suffix == ".md" and not p.name.startswith(".")
    )


def _filter_commands(cmd_filter: str | None, allowlist: list[str] | None) -> list[Path]:
    commands = list_commands()
    if allowlist is not None:
        commands = [c for c in commands if c.stem in allowlist]
    if cmd_filter:
        commands = [c for c in commands if c.stem == cmd_filter]
        if not commands:
            sys.exit(f"No command named '{cmd_filter}' under {COMMANDS_DIR.relative_to(REPO_ROOT)}.")
    return commands


def classify(src: Path, dest: Path) -> str:
    """Return one of: missing, linked, conflict-symlink, conflict-real."""
    if not dest.exists() and not dest.is_symlink():
        return "missing"
    if dest.is_symlink():
        try:
            resolved = dest.resolve()
        except OSError:
            return "conflict-symlink"
        if resolved == src.resolve():
            return "linked"
        return "conflict-symlink"
    return "conflict-real"


def cmd_status(target: CommandTarget, cmd_filter: str | None) -> int:
    commands = _filter_commands(cmd_filter, target.allowlist)
    print(f"Target: {target.name} → {target.path}")
    if not target.path.exists():
        print(f"  (target directory does not exist yet)")
    for cmd in commands:
        dest = target.path / cmd.name
        state = classify(cmd, dest)
        print(f"  {cmd.stem:<30}  {state}")
    return 0


def cmd_link(target: CommandTarget, cmd_filter: str | None, force: bool, dry_run: bool) -> int:
    commands = _filter_commands(cmd_filter, target.allowlist)
    if not target.path.exists():
        print(f"{'Would create' if dry_run else 'Creating'} target dir: {target.path}")
        if not dry_run:
            target.path.mkdir(parents=True, exist_ok=True)

    print(f"Target: {target.name} → {target.path}")
    exit_code = 0
    for cmd in commands:
        dest = target.path / cmd.name
        state = classify(cmd, dest)
        if state == "linked":
            print(f"  {cmd.stem}: already linked")
            continue
        if state == "conflict-real":
            print(
                f"  {cmd.stem}: CONFLICT — real file at {dest}. "
                f"Remove it manually first."
            )
            exit_code = 1
            continue
        if state == "conflict-symlink":
            if not force:
                print(
                    f"  {cmd.stem}: CONFLICT — existing symlink points elsewhere. "
                    f"Use --force to replace."
                )
                exit_code = 1
                continue
            if dry_run:
                print(f"  {cmd.stem}: would replace foreign symlink → {cmd}")
            else:
                dest.unlink()
                dest.symlink_to(cmd.resolve())
                print(f"  {cmd.stem}: replaced symlink → {cmd}")
            continue
        if dry_run:
            print(f"  {cmd.stem}: would link → {cmd}")
        else:
            dest.symlink_to(cmd.resolve())
            print(f"  {cmd.stem}: linked → {cmd}")
    return exit_code


def cmd_unlink(target: CommandTarget, cmd_filter: str | None, dry_run: bool) -> int:
    commands = _filter_commands(cmd_filter, target.allowlist)
    print(f"Target: {target.name} → {target.path}")
    for cmd in commands:
        dest = target.path / cmd.name
        state = classify(cmd, dest)
        if state == "linked":
            if dry_run:
                print(f"  {cmd.stem}: would unlink")
            else:
                dest.unlink()
                print(f"  {cmd.stem}: unlinked")
        elif state == "missing":
            print(f"  {cmd.stem}: not linked")
        else:
            print(f"  {cmd.stem}: not a symlink into this repo — leaving alone")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Symlink commands/ into local agent command directories."
    )
    parser.add_argument("command", choices=["status", "link", "unlink"])
    parser.add_argument(
        "--target", "-t", required=True,
        help="Named command target from skills-sync.toml."
    )
    parser.add_argument(
        "--command", "-c", dest="cmd_filter",
        help="Operate on one command by name (without .md). Default: all.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="On link, replace an existing symlink that points elsewhere.",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Print what would happen; don't change anything.",
    )
    args = parser.parse_args()

    target = load_target(args.target)

    if args.command == "status":
        return cmd_status(target, args.cmd_filter)
    if args.command == "link":
        return cmd_link(target, args.cmd_filter, args.force, args.dry_run)
    if args.command == "unlink":
        return cmd_unlink(target, args.cmd_filter, args.dry_run)
    return 1


if __name__ == "__main__":
    sys.exit(main())
