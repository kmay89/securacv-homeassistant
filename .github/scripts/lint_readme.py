#!/usr/bin/env python3
"""Lint the mirror-owned prose: README.md, AGENTS.md, CLAUDE.md.

    python3 .github/scripts/lint_readme.py
    python3 .github/scripts/lint_readme.py --source <monorepo-checkout>

WHY. README.md is this repository's HACS store page (hacs.json sets
"render_readme": true) — the most user-facing document here — and it is
mirror-OWNED: mirror-freshness.yml deliberately never compares it against
the monorepo, so no other gate reads its prose at all. Before this lint,
a broken link, an overclaim, or a banned word in the store page merged
green. The same holds for the two agent-brief files.

Three checks in the default mode, chosen to need no exemption list:

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

--source MODE: THE LINKS INTO kmay89/securaCV. The store page sends readers
to the monorepo's docs by absolute URL (most of them to a heading), and the
default mode cannot see whether those still land: a heading renamed
upstream breaks the HACS page and nothing here goes red. With `--source`
pointing at a monorepo checkout of main, the script checks ONLY those links
(the prose checks stay in the default mode, so each CI step fails for its
own reason):

  * Every URL into the repository, in every link syntax (inline, reference,
    autolink, bare, HTML attribute), outside fenced code, code spans and
    HTML comments: github.com blob/tree/raw/blame URLs and the repository
    root, http or https or scheme-relative, any case for the owner and
    repo, dot segments resolved the way a browser resolves them, and
    raw.githubusercontent.com. A link must name ref "main" (or HEAD): the
    checkout is main, so a link pinned anywhere else cannot be vouched for
    and is refused rather than passed. Other GitHub pages (issues,
    releases, ...) are not paths in a checkout; they are listed as not
    checked.
  * The file or directory must exist at that path. A path git knows but
    the sparse checkout left off disk is named as such, so a link that
    outgrows mirror-freshness.yml's sparse set says how to fix it.
  * A heading anchor must match a heading slug computed the way GitHub
    computes it for Markdown (github_slug(), below), or an explicit HTML
    id/name anchor; on a directory it is read in the README GitHub renders
    there. A line anchor (#L10, #L10-L20) must fall inside the file, and on
    a rendered Markdown file it needs ?plain=1 (GitHub renders the file
    otherwise, and the line is not there to land on).
"""
import argparse
import functools
import html
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

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


# --- GitHub heading slugs --------------------------------------------------
#
# GitHub turns a Markdown heading into an anchor in two steps: render the
# heading, take its TEXT (inline code keeps its content, a link keeps its
# text, emphasis and HTML tags vanish, an image contributes nothing), then
# lowercase it, drop every character that is not a letter, mark, decimal
# digit, connector (the underscore), hyphen or space, and turn each space
# into a hyphen. A repeated slug gets -1, -2, ... in document order, counted
# per base slug. Explicit <a id>/<a name> (any tag's id or name) anchors are
# honored as written. Known gaps, both rare in docs: an emoji shortcode is
# read as its letters (GitHub renders it to an emoji, which the slug drops),
# and a raw HTML <h2> counts only through an explicit id.
CODE_SPAN_RE = re.compile(r"(?<![`\\])(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_ATTR = (r"""(?:\s+[A-Za-z_:][\w.:-]*"""
         r"""(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+))?)""")
TAG_RE = re.compile(rf"</?[A-Za-z][A-Za-z0-9-]*{_ATTR}*\s*/?>")
ANCHOR_ATTR_RE = re.compile(
    r"""\s(?:id|name)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""",
    re.IGNORECASE)
EMPHASIS_RE = re.compile(r"(?<![^\W_])(_+)(?=\S)(.+?)(?<=\S)\1(?![^\W_])")


def _inline_text(s: str) -> str:
    """Rendered text of a run of inline Markdown with no code spans in it."""
    # An escaped character is a literal: park it where no rule below can
    # read it as markup, and put it back at the end.
    s = ESCAPE_RE.sub(lambda m: chr(0xE000 + ord(m.group(1))), s)
    s = COMMENT_RE.sub("", s)
    s = re.sub(r"!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])", "", s)  # images
    s = re.sub(r"\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])", r"\1", s)  # links
    s = TAG_RE.sub("", s)
    while True:  # _emphasis_ and __strong__; an intraword _ is a letter
        t = EMPHASIS_RE.sub(r"\2", s)
        if t == s:
            break
        s = t
    s = html.unescape(s)
    return re.sub("[\uE000-\uE07F]",
                  lambda m: chr(ord(m.group(0)) - 0xE000), s)


def heading_text(raw: str) -> str:
    """The text GitHub's renderer leaves of a heading's inline Markdown."""
    out, pos = [], 0
    for m in CODE_SPAN_RE.finditer(raw):
        out.append(_inline_text(raw[pos:m.start()]))
        code = m.group(2).replace("\n", " ")
        if code.startswith(" ") and code.endswith(" ") and code.strip(" "):
            code = code[1:-1]
        out.append(code)
        pos = m.end()
    out.append(_inline_text(raw[pos:]))
    return "".join(out)


def _slug_char(c: str) -> bool:
    cat = unicodedata.category(c)
    return c in "- " or cat[0] in "LM" or cat in ("Nd", "Pc")


def github_slug(text: str) -> str:
    """GitHub's anchor for a heading whose rendered text is `text`."""
    return "".join(c for c in text.lower() if _slug_char(c)).replace(" ", "-")


def slugify(heading: str) -> str:
    """GitHub's anchor for a heading written as `heading` (inline Markdown)."""
    return github_slug(heading_text(heading))


ATX_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
THEMATIC_RE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
LIST_RE = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)")
HTML_BLOCK_TAGS = frozenset("""
    address article aside base basefont blockquote body caption center col
    colgroup dd details dialog dir div dl dt fieldset figcaption figure footer
    form frame frameset h1 h2 h3 h4 h5 h6 head header hr html iframe legend li
    link main menu menuitem nav noframes ol optgroup option p param search
    section summary table tbody td tfoot th thead title tr track ul""".split())
HTML_OPEN_RE = re.compile(r"^ {0,3}</?([A-Za-z][A-Za-z0-9-]*)(?=[\s/>]|$)")
HTML_RAW_RE = re.compile(r"^ {0,3}<(script|pre|style|textarea)(?=[\s>]|$)",
                         re.IGNORECASE)
HTML_LONE_TAG_RE = re.compile(
    rf"^ {{0,3}}(?:<[A-Za-z][A-Za-z0-9-]*{_ATTR}*\s*/?>"
    r"|</[A-Za-z][A-Za-z0-9-]*\s*>)\s*$")


def _atx_content(content: str) -> str:
    # "## Title ##" closes with a run of #s after a space; "## C#" does not.
    return re.sub(r"(?:^|[ \t]+)#+[ \t]*$", "", content).strip()


def headings(lines):
    """Yield the inline Markdown of every heading, in document order: ATX
    and setext, outside fenced code, indented code, HTML blocks and comments,
    and the YAML front matter GitHub renders as a table."""
    start = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() in ("---", "..."):
                start = j + 1
                break
    fence = FenceTracker()
    para, para_setext, para_depth = [], False, 0
    html_end = None  # None, "blank", or a pattern that closes a raw block
    for line in lines[start:]:
        quote = QUOTE_RE.match(line)
        depth = quote.group(0).count(">") if quote else 0
        text = line[quote.end():] if quote else line
        if fence.feed(text):
            para = []
            continue
        bare = text.strip()
        if html_end is not None:
            if (not bare) if html_end == "blank" else html_end.search(text):
                html_end = None
            continue
        if not bare:
            para = []
            continue
        m = ATX_RE.match(text)
        if m:
            para = []
            yield _atx_content(m.group(2) or "")
            continue
        # The underline must sit at the paragraph's quote depth: a "---"
        # under a quoted paragraph, outside the quote, is a thematic break.
        if para and para_setext and depth == para_depth and \
                SETEXT_RE.match(text):
            yield "\n".join(p.strip() for p in para)
            para = []
            continue
        if THEMATIC_RE.match(text):
            para = []
            continue
        if bare.startswith("<!--"):
            if "-->" not in bare[4:]:
                html_end = re.compile("-->")
            para = []
            continue
        raw = HTML_RAW_RE.match(text)
        if raw:
            close = re.compile(rf"</{raw.group(1)}\s*>", re.IGNORECASE)
            if not close.search(text):
                html_end = close
            para = []
            continue
        tag = HTML_OPEN_RE.match(text)
        if tag and tag.group(1).lower() in HTML_BLOCK_TAGS:
            html_end, para = "blank", []
            continue
        if not para and HTML_LONE_TAG_RE.match(text):
            html_end = "blank"
            continue
        if not para and len(text) - len(text.lstrip(" ")) >= 4:
            continue  # indented code
        if LIST_RE.match(text) or bare.startswith("|"):
            # A list item or table row opens a run no setext line can close.
            para, para_setext = [text], False
            continue
        if not para:
            para_setext, para_depth = True, depth
        para.append(text)


def masked_lines(text: str) -> list:
    """The file's lines as prose: fenced code blanked, HTML comments and
    code spans overwritten with spaces, so line numbers and columns hold."""
    fence = FenceTracker()
    lines = ["" if fence.feed(QUOTE_RE.sub("", line)) else line
             for line in text.splitlines()]
    joined = "\n".join(lines)

    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))

    joined = COMMENT_RE.sub(blank, joined)
    # A code span never crosses a blank line.
    parts = re.split(r"(\n[ \t]*\n)", joined)
    joined = "".join(CODE_SPAN_RE.sub(blank, p) if i % 2 == 0 else p
                     for i, p in enumerate(parts))
    return joined.split("\n")


def markdown_anchors(text: str) -> set:
    """Every fragment that lands in this Markdown file on GitHub."""
    result, seen = set(), {}
    for raw in headings(text.splitlines()):
        slug = slugify(raw)
        if not slug:
            continue
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        result.add(slug if n == 0 else f"{slug}-{n}")
    for line in masked_lines(text):
        for tag in re.finditer(r"<[A-Za-z][^>]*>", line):
            for a in ANCHOR_ATTR_RE.finditer(tag.group(0)):
                result.add(next(g for g in a.groups() if g is not None))
    return result


@functools.lru_cache(maxsize=None)
def anchors_of(path: Path) -> set:
    return markdown_anchors(path.read_text(encoding="utf-8"))


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


# --- --source: the links into kmay89/securaCV -------------------------------
UPSTREAM_REF = "main"
# Any URL into the monorepo, in any link syntax: the lookbehind keeps a URL
# that is only a query value (my.home-assistant.io's repository_url) out,
# and the lookahead keeps securacv-homeassistant (this repo) out.
UPSTREAM_URL_RE = re.compile(
    r"(?<![\w/?=&%.:+@-])(?:https?:)?//"
    r"(?:(?:www\.)?github\.com/kmay89/securaCV(?:\.git)?"
    r"|raw\.githubusercontent\.com/kmay89/securaCV)"
    r"(?![\w-]|\.\w)[^\s<>()\[\]\"'`|]*",
    re.IGNORECASE)
URL_TRAIL = ".,:;!?*_~"  # what a bare URL's sentence ends with, not the URL
LINE_ANCHOR_RE = re.compile(r"^L(\d+)(?:C\d+)?(?:-L(\d+)(?:C\d+)?)?$")
PATH_KINDS = ("blob", "tree", "raw", "blame")
MARKDOWN_EXT = frozenset({".md", ".markdown", ".mdown", ".mkdn", ".mkd",
                          ".mdwn"})
# Rendered by GitHub too, but no slugger for them here.
OTHER_MARKUP_EXT = frozenset({".rst", ".rest", ".adoc", ".asciidoc", ".asc",
                              ".org", ".textile", ".rdoc", ".creole",
                              ".mediawiki", ".wiki", ".pod", ".ipynb"})


@dataclass
class UpstreamLink:
    """One URL into kmay89/securaCV, taken apart."""
    url: str
    kind: str = "page"   # root | blob | tree | raw | blame | page
    path: str = ""       # repository-relative; "" is the repository root
    fragment: str = ""
    plain: bool = False  # ?plain=1: GitHub shows the source, not the render
    error: str = ""


def upstream_links(text: str):
    """Yield (line_number, url) for every URL into kmay89/securaCV that the
    rendered page links: fenced code, code spans and comments are inert."""
    for n, line in enumerate(masked_lines(text), 1):
        for m in UPSTREAM_URL_RE.finditer(line):
            yield n, m.group(0).rstrip(URL_TRAIL)


def parse_upstream(url: str, ref: str = UPSTREAM_REF) -> UpstreamLink:
    full = "https:" + url if url.startswith("//") else url
    parts = urlsplit(full)
    link = UpstreamLink(url=url, fragment=unquote(parts.fragment),
                        plain="1" in parse_qs(parts.query).get("plain", ()))
    # A browser resolves "." and ".." before it asks GitHub for the page.
    segs = urlsplit(urljoin("https://github.com/", parts.path or "/")).path
    segs = segs.split("/")[1:]
    if segs and not segs[-1]:
        segs.pop()
    repo = re.sub(r"\.git$", "", segs[1], flags=re.IGNORECASE) \
        if len(segs) > 1 else ""
    if not segs or segs[0].lower() != "kmay89" or repo.lower() != "securacv":
        link.error = "its dot segments lead out of kmay89/securaCV"
        return link
    rest = segs[2:]
    if parts.netloc.lower() != "raw.githubusercontent.com":
        if not rest:
            link.kind = "root"
            return link
        if rest[0] not in PATH_KINDS:
            return link  # an issue, a release, an Actions run: not a path
        link.kind, rest = rest[0], rest[1:]
    else:
        link.kind = "raw"
    tail = "/".join(rest)
    if tail.startswith("refs/heads/"):
        tail = tail[len("refs/heads/"):]
    for name in (ref, "HEAD"):
        if tail == name or tail.startswith(name + "/"):
            link.path = unquote(tail[len(name) + 1:])
            break
    else:
        link.error = (f"names ref {rest[0] if rest else '(none)'!r}, and "
                      f"only links on {ref!r} can be checked against a "
                      f"checkout of {ref!r}; link to {ref!r}")
        return link
    if link.kind != "tree" and not link.path:
        link.error = f"a {link.kind} URL needs a file path"
    return link


def _readme_in(directory: Path, root: bool = False):
    """The Markdown README GitHub renders under a directory listing (for the
    repository root it looks in .github/, the root, then docs/)."""
    places = [directory / ".github", directory, directory / "docs"] \
        if root else [directory]
    for place in places:
        if not place.is_dir():
            continue
        for f in sorted(place.iterdir()):
            if f.is_file() and f.stem.lower() == "readme" and \
                    f.suffix.lower() in MARKDOWN_EXT:
                return f
    return None


def _sparse_hint(source: Path, path: str) -> str:
    """Say so when git has the path but the sparse checkout left it off."""
    if not path or not (source / ".git").exists():
        return ""
    try:
        out = subprocess.run(
            ["git", "-C", str(source), "ls-tree", "--name-only", "HEAD",
             "--", path], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    if out.returncode == 0 and out.stdout.strip():
        return (" on disk, though git has it at HEAD: it is outside the "
                "sparse checkout (widen the sparse-checkout set in "
                "mirror-freshness.yml)")
    return ""


def resolve_upstream(link: UpstreamLink, source: Path):
    """None when the link lands in the checkout, else the reason it doesn't.
    A "page" link is not a path; the caller lists it as not checked."""
    if link.error:
        return link.error
    if link.kind == "page":
        return None
    target = source / link.path if link.path else source
    if not os.path.lexists(target):
        return "no such file or directory" + _sparse_hint(source, link.path)
    frag = link.fragment
    if link.kind == "raw":
        if target.is_dir():
            return "a raw URL needs a file, and this is a directory"
        return "a raw URL has no anchors" if frag else None
    if not frag:
        return None
    line_anchor = LINE_ANCHOR_RE.match(frag)
    if target.is_dir():
        if line_anchor:
            return f"#{frag} is a line anchor, and this is a directory"
        readme = _readme_in(target, root=not link.path)
        if readme is None:
            return (f"#{frag}: GitHub renders no Markdown README here, so "
                    "the directory has no headings")
        if frag in anchors_of(readme):
            return None
        return (f"#{frag} matches no heading in "
                f"{readme.relative_to(source).as_posix()}")
    ext = target.suffix.lower()
    rendered = link.kind == "blob" and not link.plain and \
        ext in MARKDOWN_EXT | OTHER_MARKUP_EXT
    if line_anchor:
        if rendered:
            return (f"#{frag} is a line anchor, but GitHub renders {ext} "
                    "files; add ?plain=1 so the lines are there to land on")
        count = len(target.read_bytes().splitlines())
        for n in line_anchor.groups():
            if n is not None and not 1 <= int(n) <= count:
                return f"#{frag}: the file has {count} line(s)"
        return None
    if link.kind == "blame" or ext not in MARKDOWN_EXT | OTHER_MARKUP_EXT:
        return (f"#{frag} is not a line anchor (#L<n>), and a "
                f"{link.kind} view of a {ext or 'plain'} file has no headings")
    if ext in OTHER_MARKUP_EXT:
        return (f"#{frag}: anchors in a rendered {ext} file are not computed "
                "here; link without the anchor or teach this script the "
                "markup")
    if link.plain:
        return (f"#{frag}: ?plain=1 shows the source, where headings have no "
                "anchors")
    if frag in anchors_of(target):
        return None
    return f"#{frag} matches no heading there"


def check_upstream(paths, source: Path, ref: str = UPSTREAM_REF):
    """Check every link into kmay89/securaCV in `paths` against `source`.
    Returns (problems, number checked, the links that are not paths)."""
    problems, checked, unchecked = [], 0, []
    for path in paths:
        if not path.exists():
            problems.append(f"{path.name}: MISSING — the mirror-owned prose "
                            "set must exist (is the HACS store page gone?)")
            continue
        for n, url in upstream_links(path.read_text(encoding="utf-8")):
            link = parse_upstream(url, ref)
            if link.kind == "page" and not link.error:
                unchecked.append(f"{path.name}:{n}: {url}")
                continue
            checked += 1
            why = resolve_upstream(link, source)
            if why:
                problems.append(f"{path.name}:{n}: {url} — {why}")
    return problems, checked, unchecked


# The --source mode's own probes: a slugger or URL parser that has drifted
# (a runner's Python changing unicodedata or urllib under it) must not
# report the store page's links fine.
SLUG_CHECK = (
    ("What Sealed ✓, Verified ✓ and Failed ⚠ mean",
     "what-sealed--verified--and-failed--mean"),
    ("Path 1: Home Assistant OS — the SecuraCV app",
     "path-1-home-assistant-os--the-securacv-app"),
    ("Entity ids: `pwk_*` → `securacv_*`", "entity-ids-pwk_--securacv_"),
    ("Step 6: Verify per-device PKI (optional but recommended)",
     "step-6-verify-per-device-pki-optional-but-recommended"),
    ("[Linked](https://x.example) _emphasis_ and snake_case",
     "linked-emphasis-and-snake_case"),
)
SHAPE_CHECK = (
    ("https://github.com/kmay89/securaCV/blob/main/docs/a.md#x",
     "blob", "docs/a.md", "x"),
    ("https://github.com/kmay89/securaCV/tree/main/docs", "tree", "docs", ""),
    ("https://github.com/kmay89/securaCV", "root", "", ""),
    ("http://www.github.com/KMAY89/securacv/", "root", "", ""),
    ("//github.com/kmay89/securaCV/blob/main/docs/../README.md",
     "blob", "README.md", ""),
    ("https://raw.githubusercontent.com/kmay89/securaCV/main/docs/a.md",
     "raw", "docs/a.md", ""),
    ("https://github.com/kmay89/securaCV/issues/1", "page", "", ""),
)
EXTRACT_CHECK = (
    ("[x](https://github.com/kmay89/securaCV/blob/main/a.md#b).",
     ["https://github.com/kmay89/securaCV/blob/main/a.md#b"]),
    ("See https://github.com/kmay89/securaCV.",
     ["https://github.com/kmay89/securaCV"]),
    ("[r]: <https://github.com/kmay89/securaCV/tree/main/docs>",
     ["https://github.com/kmay89/securaCV/tree/main/docs"]),
    ("[m](https://github.com/kmay89/securacv-homeassistant)", []),
    ("[h](https://x.example/?u=https://github.com/kmay89/securaCV)", []),
    ("`https://github.com/kmay89/securaCV/blob/main/a.md`", []),
    ("```\nhttps://github.com/kmay89/securaCV/blob/main/a.md\n```", []),
)


def self_check_upstream() -> list:
    """Run the slugger, the URL parser and the extractor over their probes;
    return what they got wrong."""
    wrong = []
    for heading, want in SLUG_CHECK:
        if slugify(heading) != want:
            wrong.append(f"slug of {heading!r}: expected {want!r}, got "
                         f"{slugify(heading)!r}")
    for url, kind, path, frag in SHAPE_CHECK:
        got = parse_upstream(url)
        if (got.kind, got.path, got.fragment, got.error) != \
                (kind, path, frag, ""):
            wrong.append(f"{url}: expected {kind} {path!r} #{frag}, got "
                         f"{got.kind} {got.path!r} #{got.fragment} "
                         f"{got.error}".rstrip())
    for text, want in EXTRACT_CHECK:
        got = [u for _, u in upstream_links(text)]
        if got != want:
            wrong.append(f"links in {text!r}: expected {want}, got {got}")
    return wrong


def lint_upstream(source: Path) -> int:
    wrong = self_check_upstream()
    if wrong:
        print("lint_readme.py --source: the link checker failed its own "
              "probes, so it cannot vouch for the store page's links:",
              file=sys.stderr)
        for w in wrong:
            print(f"  {w}", file=sys.stderr)
        return 1
    if not source.is_dir():
        print(f"lint_readme.py --source: {source} is not a directory (a "
              "kmay89/securaCV checkout of main)", file=sys.stderr)
        return 2
    problems, checked, unchecked = check_upstream(
        [ROOT / name for name in FILES], source)
    for u in unchecked:
        print(f"  not checked (a GitHub page, not a path): {u}")
    if problems:
        print(f"lint_readme.py --source: {len(problems)} link(s) into "
              f"kmay89/securaCV do not land in {source}:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    print(f"links into kmay89/securaCV OK — {checked} resolve against "
          f"{source} (files, directories, headings, lines)")
    return 0


def lint_prose() -> int:
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Lint the mirror-owned prose; with --source, check its "
                    "links into kmay89/securaCV against a checkout instead.")
    ap.add_argument("--source", type=Path, metavar="MONOREPO",
                    help="a kmay89/securaCV checkout of main: check only the "
                         "links into it (files, directories, anchors)")
    args = ap.parse_args(argv)
    if args.source is not None:
        return lint_upstream(args.source)
    return lint_prose()


if __name__ == "__main__":
    raise SystemExit(main())
