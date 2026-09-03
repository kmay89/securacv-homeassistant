#!/usr/bin/env python3
"""check_mirror_sync.py — is this HACS mirror still the monorepo's integration?

THE PROBLEM THIS CATCHES
========================
`custom_components/securacv/` here is a byte-for-byte copy of the same
directory in kmay89/securaCV (plus `brand/`, which HACS wants and the
monorepo does not carry), and the root `conftest.py` is the monorepo's file
too (the Home Assistant stubs the tests import). The monorepo's
`.github/workflows/homeassistant-mirror.yml` pushes every change to that set
here as a PR on `bot/mirror-sync` — and runs THIS script against its own
checkout before opening it. This check is the backstop for everything that
path does not cover: a hand-made edit here, a sync that never ran (no
`MIRROR_PAT` in the monorepo), a monorepo commit that slipped by while the
secret was missing. Before the push existed the copies drifted for weeks at a
time, and nobody noticed until a user did.

WHAT IT DOES
============
Compares every file under `custom_components/securacv/` (excluding the
mirror-only `brand/` directory and `__pycache__`) plus the carried root files
against the same paths in a monorepo checkout — the one `--source` points at,
or the sparse clone the workflow makes — and reports three kinds of drift:

  * DIFFERENT  — same path, different bytes (the fix that never got copied)
  * MISSING    — present upstream, absent here (a new module HACS users lack)
  * EXTRA      — present here, absent upstream (a file the monorepo deleted)

Exit 1 on any drift so CI is red, and print the exact `cp`/`rm` commands
that fix it, because the cure is mechanical and should be copy-pasteable.

Run locally against a sibling checkout:
  python3 .github/scripts/check_mirror_sync.py --source ../securaCV
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
REL = Path("custom_components") / "securacv"
# Carried root files — byte-identical to the monorepo's, like the directory.
# requirements_test.txt is deliberately NOT here: Dependabot bumps it in both
# repos and this repo's pins lead, so the monorepo never overwrites it.
ROOT_FILES = ("conftest.py",)
MIRROR_ONLY = {"brand"}          # HACS brand assets; the monorepo has no use for them
IGNORE_DIRS = {"__pycache__", ".pytest_cache"}


def files_under(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        if rel.parts and rel.parts[0] in MIRROR_ONLY:
            continue
        out[rel.as_posix()] = p
    return out


def carried(repo: Path) -> dict[str, Path]:
    """Every carried file in a checkout, keyed by repo-relative posix path."""
    out = {f"{REL.as_posix()}/{k}": p for k, p in files_under(repo / REL).items()}
    for name in ROOT_FILES:
        p = repo / name
        if p.is_file():
            out[name] = p
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="path to a kmay89/securaCV checkout (full or sparse)")
    args = ap.parse_args()

    upstream = Path(args.source).resolve()
    if not (upstream / REL).is_dir():
        print(f"::error::upstream integration not found at {upstream / REL}")
        return 2

    up = carried(upstream)
    mi = carried(HERE)

    different = [k for k in sorted(set(up) & set(mi)) if sha(up[k]) != sha(mi[k])]
    missing = sorted(set(up) - set(mi))
    extra = sorted(set(mi) - set(up))

    if not (different or missing or extra):
        print(f"mirror in sync — {len(mi)} files match kmay89/securaCV "
              f"({REL.as_posix()}/ + {', '.join(ROOT_FILES)}; "
              f"{', '.join(sorted(MIRROR_ONLY))}/ is mirror-only by design)")
        return 0

    print("::error::the HACS mirror has drifted from the monorepo integration")
    for k in different:
        print(f"DIFFERENT  {k}")
    for k in missing:
        print(f"MISSING    {k}  (upstream has it, mirror does not)")
    for k in extra:
        print(f"EXTRA      {k}  (mirror has it, upstream does not)")
    print("\nTo resync from a monorepo checkout at $SRC:")
    for k in different + missing:
        print(f"  mkdir -p {Path(k).parent} && cp \"$SRC/{k}\" {k}")
    for k in extra:
        print(f"  git rm {k}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
