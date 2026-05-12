#!/usr/bin/env python3
"""Placeholder skill script. Prints a greeting."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a greeting.")
    parser.add_argument("--name", default="world", help="Name to greet.")
    parser.add_argument(
        "--from-asset",
        action="store_true",
        help="Load the greeting template from assets/greeting.txt instead.",
    )
    args = parser.parse_args()

    if args.from_asset:
        skill_root = Path(__file__).resolve().parent.parent
        asset = skill_root / "assets" / "greeting.txt"
        template = asset.read_text(encoding="utf-8").strip()
    else:
        template = "Hello, {name}!"

    print(template.format(name=args.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
