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
     phrases the website bans are banned here too. So is "encrypted by
     default": every Canary ships speaking plain MQTT to the broker, and
     TLS is opt-in per device. The pattern also matches the negated form,
     so honest copy says "plain by default". The prose is hard-wrapped, so
     a claim is matched per Markdown block (a paragraph, list item or
     quote), not per line: its words may be split by a line break, a
     hyphen, emphasis stars or underscores, or backticks, and it is still
     one claim. A blank line, a heading or a fence ends a block; a list
     item or a table row starts one. Fenced samples are checked too. Every
     run first tries the matcher on its own probes (SELF_CHECK) and
     refuses to report the files clean if any probe comes out wrong.

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
ABSOLUTE = "the record is tamper-evident, and absolutes are unbackable"
PLAIN = ("the Canary-to-broker link is plain MQTT by default and TLS is "
         "opt-in per device; say \"plain by default\"")
# What may sit between the words of a claim: whitespace (a hard wrap's line
# break included), hyphens, emphasis markup and backticks.
SEP = r"[\s*_`-]+"
OVERCLAIMS = [
    (re.compile(p, re.IGNORECASE), why) for p, why in (
        (rf"tamper(?:{SEP})?proof", ABSOLUTE),
        (r"\bunhackable\b", ABSOLUTE),
        (rf"\b100%{SEP}(?:secure|private|anonymous)\b", ABSOLUTE),
        (rf"\bimpossible{SEP}to{SEP}(?:hack|break|breach)\b", ABSOLUTE),
        (rf"\bmilitary{SEP}grade\b", ABSOLUTE),
        (rf"\bcompletely{SEP}(?:secure|anonymous)\b", ABSOLUTE),
        (rf"\bguaranteed{SEP}privacy\b", ABSOLUTE),
        (rf"\bencrypted{SEP}by{SEP}default\b", PLAIN),
    )
]
# Markdown block boundaries for the claim check. A heading or fence line is
# a block of its own; a list item or table row starts a new one; a quote's
# ">" markers are stripped so a wrapped quote still reads as one block.
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}(?:\s|$)")
ITEM_RE = re.compile(r"^\s{0,3}(?:[-*+]\s|\d{1,9}[.)]\s|\|)")
QUOTE_RE = re.compile(r"^\s{0,3}(?:>\s?)+")
# The claim check's own probes: (sample, line of the first hit, or None for
# a sample that must pass). The first group is what a hard-wrapped store
# page actually produces; the second is what block splitting must keep
# apart. A matcher that misses one is broken, and a broken matcher must not
# report the real files clean.
SELF_CHECK = (
    ("The link is encrypted by default.", 1),
    ("The broker link is encrypted by\ndefault, so relax.", 1),
    ("The link is\nencrypted-by-default.", 2),
    ("It is **encrypted** by\ndefault.", 1),
    ("> The link is encrypted\n> by default.", 1),
    ("- The link is\n  encrypted\n  by default.", 2),
    ("It is impossible to\nhack.", 1),
    ("The record is tamper\nproof.", 1),
    ("The link is plain by default.", None),
    ("The link is unencrypted by default.", None),
    ("It is not encrypted until you\nprovision TLS.", None),
    ("### What is encrypted\n\nBy default, nothing.", None),
    ("### What is encrypted\nBy default, nothing.", None),
    ("- encrypted\n- by default", None),
    ("| encrypted |\n| by default |", None),
)
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


def blocks(lines):
    """Split lines into Markdown blocks, the runs a hard-wrapped claim can
    span. Yields lists of (line_number, text), numbered from 1."""
    block = []
    for i, line in enumerate(lines, 1):
        text = QUOTE_RE.sub("", line)
        bare = text.strip()
        if not bare or FENCE_RE.match(bare) or HEADING_RE.match(text):
            if block:
                yield block
            block = []
            if bare:
                yield [(i, text)]
            continue
        if block and ITEM_RE.match(text):
            yield block
            block = []
        block.append((i, text))
    if block:
        yield block


def overclaims(lines):
    """Yield (line_number, claim, reason) for every overclaim, numbered by
    the line the claim starts on."""
    for block in blocks(lines):
        joined = "\n".join(text for _, text in block)
        for pat, why in OVERCLAIMS:
            for m in pat.finditer(joined):
                row = joined.count("\n", 0, m.start())
                yield block[row][0], " ".join(m.group(0).split()), why


def self_check() -> list:
    """Run the claim matcher over SELF_CHECK; return what it got wrong."""
    wrong = []
    for sample, want in SELF_CHECK:
        got = [n for n, _, _ in overclaims(sample.splitlines())]
        if (got[:1] or [None])[0] != want:
            wrong.append(f"{sample!r}: expected "
                         f"{'a hit on line %d' % want if want else 'no hit'}"
                         f", got {got or 'no hit'}")
    return wrong


def main() -> int:
    wrong = self_check()
    if wrong:
        print("lint_readme.py: the overclaim matcher failed its own probes, "
              "so it cannot vouch for the prose:", file=sys.stderr)
        for w in wrong:
            print(f"  {w}", file=sys.stderr)
        return 1
    problems = []
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            problems.append(f"{name}: MISSING — the mirror-owned prose set "
                            "must exist (is the HACS store page gone?)")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        claims = {}
        for n, claim, why in overclaims(lines):
            claims.setdefault(n, []).append((claim, why))
        fence = FenceTracker()
        for i, line in enumerate(lines, 1):
            in_fence = fence.feed(line)
            # Word and claim rules bind fenced samples too — the store page
            # renders them; only the link check treats a sample as inert.
            if BIRD.search(BIRD_MASK.sub("(", line)):
                problems.append(f"{name}:{i}: the bird-group word — a group "
                                "of Canaries is a FLEET")
            for claim, why in claims.get(i, ()):
                problems.append(f"{name}:{i}: overclaim {claim!r} — {why}")
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
