#!/usr/bin/env python3
"""Symlink `skills/` into local agent skill directories.

Reads [link_targets.<name>] from skills-sync.toml. Each entry has a path,
an optional skills allowlist, and an optional harness override:

  [link_targets.claude-code-user]
  path = "~/.claude/skills"
  skills = ["my-skill"]          # optional — omit to link all skills
  harness = "claude-code"        # optional — inferred from the name otherwise

  - '~' is expanded to the user's home dir.
  - Relative paths resolve against the current working directory at
    invocation time. This lets project-scoped targets like
    `.claude/skills` follow you into whichever project you cd into.
  - If `skills` is set, only those skill names are linked/unlinked for
    that target. Skills not in the list are silently ignored.
  - The target's harness is matched against each skill's SKILL.md
    `harnesses` field so that, e.g., a skill marked `harnesses: [codex]`
    links into Codex targets but not Claude Code ones. The harness is
    taken from the `harness` key when present, otherwise inferred from
    the target name (`codex-user` → `codex`); when neither yields a
    value, no harness filtering is applied.

Subcommands:
  status   show whether each skill is linked, missing, or in conflict.
  link     create symlinks (skill folder → <target>/<skill-name>).
  unlink   remove symlinks that point back into this repo.

Safety:
  - Never deletes a real directory. A non-symlink at the destination is
    flagged as a conflict; user must remove it manually.
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
SKILLS_DIR = REPO_ROOT / "skills"
CONFIG_FILE = REPO_ROOT / "skills-sync.toml"


@dataclass
class LinkTarget:
    name: str
    path: Path              # resolved absolute path
    allowlist: list[str] | None  # None = all skills; list = only these names
    harness: str | None     # harness this target represents; None = no filtering


# Harnesses link_skills.py can target. All of these read SKILL.md folders
# natively, so they're driven by the same symlink mechanism. Used to map a
# target to the SKILL.md `harnesses` value it should match.
LINK_HARNESSES = ("claude-code", "codex", "cursor")


def _infer_harness(name: str, explicit: str | None) -> str | None:
    """Resolve which harness a link target represents.

    Used to filter skills by their SKILL.md `harnesses` field. An explicit
    `harness = "..."` key in the target config wins; otherwise it is inferred
    from the target name (e.g. `codex-user` → `codex`). Returns None when it
    can't be determined, in which case no harness filtering is applied.
    """
    if explicit:
        return explicit
    for h in LINK_HARNESSES:
        if name == h or name.startswith(f"{h}-"):
            return h
    return None


def load_target(name: str) -> LinkTarget:
    if not CONFIG_FILE.exists():
        sys.exit(
            f"No config at {CONFIG_FILE.relative_to(REPO_ROOT)}. "
            f"Copy skills-sync.example.toml to skills-sync.toml and edit it."
        )
    cfg = tomllib.loads(CONFIG_FILE.read_text("utf-8"))
    entry = cfg.get("link_targets", {}).get(name)
    if not entry:
        available = ", ".join(cfg.get("link_targets", {}).keys()) or "(none)"
        sys.exit(f"Unknown link target '{name}'. Available: {available}")
    raw = entry.get("path")
    if not raw:
        sys.exit(f"Target '{name}' is missing 'path'.")
    expanded = Path(os.path.expanduser(raw))
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    allowlist = entry.get("skills")  # list[str] or None
    harness = _infer_harness(name, entry.get("harness"))
    return LinkTarget(
        name=name, path=expanded.resolve(), allowlist=allowlist, harness=harness
    )


def list_skills() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        p for p in SKILLS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


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


def classify(skill: Path, dest: Path) -> str:
    """Return one of: missing, linked, conflict-symlink, conflict-real."""
    if not dest.exists() and not dest.is_symlink():
        return "missing"
    if dest.is_symlink():
        try:
            resolved = dest.resolve()
        except OSError:
            return "conflict-symlink"
        if resolved == skill.resolve():
            return "linked"
        return "conflict-symlink"
    return "conflict-real"


def _filter_skills(
    skill_filter: str | None,
    allowlist: list[str] | None,
    harness: str | None,
) -> list[Path]:
    skills = list_skills()
    if allowlist is not None:
        skills = [s for s in skills if s.name in allowlist]
    # Respect SKILL.md harnesses field — omit skills that don't target this
    # target's harness. Skills with no harnesses field are included everywhere.
    if harness is not None:
        skills = [s for s in skills if (h := _skill_harnesses(s)) is None or harness in h]
    if skill_filter:
        skills = [s for s in skills if s.name == skill_filter]
        if not skills:
            sys.exit(f"No skill named '{skill_filter}' under {SKILLS_DIR.relative_to(REPO_ROOT)}.")
    return skills


def cmd_status(target: LinkTarget, skill_filter: str | None) -> int:
    skills = _filter_skills(skill_filter, target.allowlist, target.harness)
    print(f"Target: {target.name} → {target.path}")
    if not target.path.exists():
        print(f"  (target directory does not exist yet)")
    for skill in skills:
        dest = target.path / skill.name
        state = classify(skill, dest)
        print(f"  {skill.name:<30}  {state}")
    return 0


def cmd_link(target: LinkTarget, skill_filter: str | None, force: bool, dry_run: bool) -> int:
    skills = _filter_skills(skill_filter, target.allowlist, target.harness)
    if not target.path.exists():
        print(f"{'Would create' if dry_run else 'Creating'} target dir: {target.path}")
        if not dry_run:
            target.path.mkdir(parents=True, exist_ok=True)

    print(f"Target: {target.name} → {target.path}")
    exit_code = 0
    for skill in skills:
        dest = target.path / skill.name
        state = classify(skill, dest)
        if state == "linked":
            print(f"  {skill.name}: already linked")
            continue
        if state == "conflict-real":
            print(
                f"  {skill.name}: CONFLICT — real file or directory at {dest}. "
                f"Remove it manually first."
            )
            exit_code = 1
            continue
        if state == "conflict-symlink":
            if not force:
                print(
                    f"  {skill.name}: CONFLICT — existing symlink points elsewhere. "
                    f"Use --force to replace."
                )
                exit_code = 1
                continue
            if dry_run:
                print(f"  {skill.name}: would replace foreign symlink → {skill}")
            else:
                dest.unlink()
                dest.symlink_to(skill.resolve())
                print(f"  {skill.name}: replaced symlink → {skill}")
            continue
        if dry_run:
            print(f"  {skill.name}: would link → {skill}")
        else:
            dest.symlink_to(skill.resolve())
            print(f"  {skill.name}: linked → {skill}")
    return exit_code


def cmd_unlink(target: LinkTarget, skill_filter: str | None, dry_run: bool) -> int:
    skills = _filter_skills(skill_filter, target.allowlist, target.harness)
    print(f"Target: {target.name} → {target.path}")
    for skill in skills:
        dest = target.path / skill.name
        state = classify(skill, dest)
        if state == "linked":
            if dry_run:
                print(f"  {skill.name}: would unlink")
            else:
                dest.unlink()
                print(f"  {skill.name}: unlinked")
        elif state == "missing":
            print(f"  {skill.name}: not linked")
        else:
            print(f"  {skill.name}: not a symlink into this repo — leaving alone")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Symlink skills/ into local agent skill directories."
    )
    parser.add_argument("command", choices=["status", "link", "unlink"])
    parser.add_argument(
        "--target", "-t", required=True,
        help="Named link target from skills-sync.toml."
    )
    parser.add_argument(
        "--skill", "-s",
        help="Operate on one skill by name. Default: all skills in skills/.",
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
        return cmd_status(target, args.skill)
    if args.command == "link":
        return cmd_link(target, args.skill, args.force, args.dry_run)
    if args.command == "unlink":
        return cmd_unlink(target, args.skill, args.dry_run)
    return 1


if __name__ == "__main__":
    sys.exit(main())
