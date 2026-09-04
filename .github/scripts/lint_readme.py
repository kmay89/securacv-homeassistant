#!/usr/bin/env python3
"""Lint the mirror-owned prose: README.md, AGENTS.md, CLAUDE.md.

    python3 .github/scripts/lint_readme.py

WHY. README.md is this repository's HACS store page (hacs.json sets
"render_readme": true) — the most user-facing document here — and it is
mirror-OWNED: mirror-freshness.yml deliberately never compares it against
the monorepo, so no other gate reads its content at all. Before this lint,
a broken link, an overclaim, or a banned word in the store page merged
green. The same holds for the two agent-brief files.

Three checks, chosen to need no exemption list:

  1. Every relative link resolves (file exists; a #fragment on a .md target
     matches a real heading, GitHub-slugified). Links inside fenced code
     blocks are skipped — a sample is not a promise.
  2. The banned bird-group word for a group of devices is absent — a group
     of Canaries is a fleet. (The monorepo's AGENTS.md rule 3 is the
     canonical statement; the briefs here are written so they never need
     to quote the word.) The Unix flock(2) syscall form is masked. Checked
     on every line, fenced samples included — the HACS store page renders
     those too.
  3. No overclaims: the record is tamper-EVIDENT, and the absolute-security
     phrases the website bans are banned here too. Also checked on every
     line.

A missing file is an error, not a skip — deleting the HACS store page must
not read as a clean lint.

US-spelling is deliberately NOT re-enumerated here: two independently
maintained ban lists (monorepo, website) already exist and disagree at the
edges — a third would compound the drift. From a monorepo checkout run
`python3 scripts/lint_spelling.py /path/to/this/repo/README.md` instead.
"""
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
FILES = ["README.md", "AGENTS.md", "CLAUDE.md"]

BIRD = re.compile(r"flock", re.IGNORECASE)
BIRD_MASK = re.compile(r"flock\(")  # the Unix syscall, a real API name
OVERCLAIMS = [
    re.compile(r"tamper-?proof", re.IGNORECASE),
    re.compile(r"\bunhackable\b", re.IGNORECASE),
    re.compile(r"\b100%\s+(?:secure|private|anonymous)\b", re.IGNORECASE),
    re.compile(r"\bimpossible\s+to\s+(?:hack|break|breach)\b", re.IGNORECASE),
    re.compile(r"\bmilitary[- ]grade\b", re.IGNORECASE),
    re.compile(r"\bcompletely\s+(?:secure|anonymous)\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\s+privacy\b", re.IGNORECASE),
]
LINK_RE = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
EXTERNAL = ("http://", "https://", "mailto:", "tel:", "data:")


class FenceTracker:
    """CommonMark fence pairing: a fence closes only on a same-character
    marker at least as long as its opener."""

    def __init__(self):
        self.marker = None

    def feed(self, line):
        m = FENCE_RE.match(line.strip())
        if self.marker is None:
            if m:
                self.marker = m.group(1)
                return True
            return False
        if m and m.group(1)[0] == self.marker[0] and \
                len(m.group(1)) >= len(self.marker):
            self.marker = None
        return True


def slugify(heading: str) -> str:
    h = heading.strip().lower()
    h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", h)
    h = h.replace("`", "").replace("*", "")
    return "".join(c for c in h if c.isalnum() or c in "-_ ").replace(" ", "-")


def anchors_of(path: Path) -> set:
    result, seen = set(), {}
    fence = FenceTracker()
    for line in path.read_text(encoding="utf-8").splitlines():
        if fence.feed(line):
            continue
        m = re.match(r"^#{1,6}\s+(.*)", line)
        if m:
            slug = slugify(m.group(1))
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            result.add(slug if n == 0 else f"{slug}-{n}")
    return result


def main() -> int:
    problems = []
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            problems.append(f"{name}: MISSING — the mirror-owned prose set "
                            "must exist (is the HACS store page gone?)")
            continue
        fence = FenceTracker()
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            in_fence = fence.feed(line)
            # Word and claim rules bind fenced samples too — the store page
            # renders them; only the link check treats a sample as inert.
            if BIRD.search(BIRD_MASK.sub("(", line)):
                problems.append(f"{name}:{i}: the bird-group word — a group "
                                "of Canaries is a FLEET")
            for pat in OVERCLAIMS:
                m = pat.search(line)
                if m:
                    problems.append(f"{name}:{i}: overclaim {m.group(0)!r} — "
                                    "the record is tamper-evident, and "
                                    "absolutes are unbackable")
            if not in_fence:
                for m in LINK_RE.finditer(line):
                    raw = m.group(1)
                    if raw.startswith(EXTERNAL):
                        continue
                    target = raw.strip("<>")
                    frag = None
                    if "#" in target:
                        target, frag = target.split("#", 1)
                    if not target:
                        if frag and frag not in anchors_of(path):
                            problems.append(f"{name}:{i}: #{frag} — no such "
                                            "heading in this file")
                        continue
                    resolved = (path.parent / unquote(target)).resolve()
                    if not resolved.exists():
                        problems.append(f"{name}:{i}: {raw} — no such file")
                    elif frag and resolved.suffix == ".md":
                        if frag not in anchors_of(resolved):
                            problems.append(f"{name}:{i}: {raw} — #{frag} "
                                            "matches no heading there")
    if problems:
        print(f"lint_readme.py: {len(problems)} problem(s) in the "
              "mirror-owned prose:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    print("mirror prose OK — links resolve, no banned word, no overclaims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
