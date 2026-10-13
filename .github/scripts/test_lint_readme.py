#!/usr/bin/env python3
"""Unit tests for lint_readme.py's --source mode (sweep item HA31).

Run:  python3 -m unittest discover -s .github/scripts -p 'test_*.py' -v

The store page (README.md) links into kmay89/securaCV's docs by absolute
URL, most of them to a heading. These cases pin the three parts that decide
whether such a link lands: the slugger (a heading's anchor, computed the way
GitHub computes it), the URL parser (which URLs are links into the monorepo
and what path, ref and anchor each names), and the resolver (does the path
exist in a checkout, does the anchor match). They also pin the CI wiring in
mirror-freshness.yml: the sparse checkout reaches every path the store page
links to, the link check is its own step, and the "mirror has drifted" issue
stays keyed to the drift comparison alone.

Every fixture is built in a temporary directory: nothing here needs the
network or a monorepo checkout.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lint_readme as lr  # noqa: E402

REPO = "https://github.com/kmay89/securaCV"
FRESHNESS = lr.ROOT / ".github" / "workflows" / "mirror-freshness.yml"
# The status check that means "unless the run was canceled", spelled without
# the Actions function whose name the monorepo's US-spelling lint refuses.
UNLESS_CANCELED = "(success() || failure())"


def anchors(md: str) -> set:
    return lr.markdown_anchors(textwrap.dedent(md))


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t",
                           "-c", "user.email=t@example.invalid", *args],
                          check=True, capture_output=True, text=True).stdout


class Slugger(unittest.TestCase):
    """slugify(): a heading's inline Markdown in, GitHub's anchor out."""

    def test_punctuation_dropped_and_each_space_a_hyphen(self):
        # The store page links to exactly this one; the checkmarks and the
        # comma go, the spaces around them stay, hence the double hyphens.
        self.assertEqual(lr.slugify("What Sealed ✓, Verified ✓ and Failed ⚠ mean"),
                         "what-sealed--verified--and-failed--mean")
        self.assertEqual(lr.slugify("Path 1: Home Assistant OS — the SecuraCV app"),
                         "path-1-home-assistant-os--the-securacv-app")

    def test_inline_code_keeps_its_content(self):
        self.assertEqual(lr.slugify("Entity ids: `pwk_*` → `securacv_*`"),
                         "entity-ids-pwk_--securacv_")
        # A code span is literal: link syntax inside it is not a link.
        self.assertEqual(lr.slugify("Use `[x](y)` here"), "use-xy-here")

    def test_a_link_is_reduced_to_its_text(self):
        self.assertEqual(lr.slugify("See [Step 3](guide.md#step-3) first"),
                         "see-step-3-first")
        self.assertEqual(lr.slugify("A [reference][ref] link"),
                         "a-reference-link")

    def test_emphasis_vanishes_but_an_intraword_underscore_is_a_letter(self):
        self.assertEqual(lr.slugify("**Bold** _em_ __strong__ snake_case"),
                         "bold-em-strong-snake_case")
        self.assertEqual(lr.slugify(r"An \_escaped\_ underscore"),
                         "an-_escaped_-underscore")

    def test_html_tags_go_and_their_text_stays(self):
        self.assertEqual(lr.slugify("<code>mqtt</code> topics"), "mqtt-topics")
        # The anchor tag leaves its trailing space behind, as on GitHub.
        self.assertEqual(lr.slugify('Title <a name="t"></a>'), "title-")

    def test_an_image_contributes_no_text(self):
        self.assertEqual(lr.slugify("![logo](logo.png) Title"), "-title")

    def test_letters_and_marks_of_any_script_survive(self):
        # U+FE0F (the emoji presentation selector) is a mark, so it stays,
        # exactly as GitHub keeps it in the monorepo's AGENTS.md anchors.
        self.assertEqual(lr.slugify("Ünïcode ⚠️ note"),
                         "ünïcode-️-note")

    def test_entities_are_decoded_first(self):
        self.assertEqual(lr.slugify("Q&amp;A"), "qa")


class Anchors(unittest.TestCase):
    """markdown_anchors(): every fragment that lands in a Markdown file."""

    def test_duplicate_headings_get_numbered_suffixes(self):
        self.assertEqual(anchors("# Notes\n## Notes\n### Notes\n"),
                         {"notes", "notes-1", "notes-2"})

    def test_setext_headings_and_closing_hashes(self):
        self.assertEqual(anchors("""\
            Title
            =====

            Sub
            ---
            ## Closed ##
            ## C#
        """), {"title", "sub", "closed", "c"})

    def test_a_thematic_break_is_not_a_setext_underline(self):
        # After a blank line, a list item or a quote it is a rule, not an
        # underline (the monorepo's FLEET_FIGURES.md has the quote case).
        self.assertEqual(anchors("para\n\n---\n"), set())
        self.assertEqual(anchors("- item\n---\n"), set())
        self.assertEqual(anchors("> quoted\n---\n"), set())
        self.assertEqual(anchors("> quoted\n> ---\n"), {"quoted"})

    def test_code_html_blocks_comments_and_front_matter_hide_headings(self):
        self.assertEqual(anchors("""\
            ---
            title: Not a heading
            ---
            ```
            # not a heading
            ```

                # nor this (indented code)

            <details>
            ## raw HTML until the blank line
            </details>

            <!--
            ## commented out
            -->
            # After
        """), {"after"})

    def test_a_stray_backtick_or_comment_opener_hides_nothing_past_its_block(self):
        # CommonMark: a code span or an inline comment never crosses a block
        # (a list item, a blank line), so the anchor after one still renders.
        self.assertEqual(anchors('- a stray `\n- <a id="x"></a> b `c`\n'), {"x"})
        self.assertEqual(anchors('a <!-- b\n\n<a id="y"></a> -->\n'), {"y"})
        # Inside its block a code span still hides what it holds.
        self.assertEqual(anchors('- a `\n  <a id="x"></a>` b\n'), set())

    def test_a_comment_that_opens_a_line_runs_to_its_close(self):
        # An HTML block: blank lines do not end it, its "-->" does.
        self.assertEqual(anchors('<!--\n\n<a id="z"></a>\n\n-->\n# After\n'),
                         {"after"})
        self.assertEqual(anchors('<!-- one -->\n<a id="w"></a>\n'), {"w"})
        self.assertEqual(anchors('> <!--\n> <a id="q"></a>\n> -->\n'), set())

    def test_explicit_html_anchors_are_honored(self):
        found = anchors("""\
            ## <a name="pin-tracker"></a>Pin tracker
            <a id="assembly-watch"></a>

            `<a id="in-code">` is not an anchor
        """)
        self.assertEqual(found, {"pin-tracker", "assembly-watch"})


class UrlShapes(unittest.TestCase):
    """upstream_links() and parse_upstream(): which URLs are links into the
    monorepo, and what each one names."""

    def shape(self, url):
        link = lr.parse_upstream(url)
        return link.kind, link.path, link.fragment, link.plain, link.error

    def test_every_shape(self):
        cases = {
            f"{REPO}/blob/main/docs/a.md#step-1": ("blob", "docs/a.md", "step-1", False),
            f"{REPO}/blob/main/docs/a.md": ("blob", "docs/a.md", "", False),
            f"{REPO}/tree/main/docs/blueprints": ("tree", "docs/blueprints", "", False),
            f"{REPO}/tree/main": ("tree", "", "", False),
            f"{REPO}/tree/main/docs/#intro": ("tree", "docs", "intro", False),
            f"{REPO}/blame/main/a.py#L3": ("blame", "a.py", "L3", False),
            f"{REPO}/raw/main/a.py": ("raw", "a.py", "", False),
            "https://raw.githubusercontent.com/kmay89/securaCV/main/a.py":
                ("raw", "a.py", "", False),
            "https://raw.githubusercontent.com/kmay89/securaCV/refs/heads/main/a.py":
                ("raw", "a.py", "", False),
            REPO: ("root", "", "", False),
            f"{REPO}/": ("root", "", "", False),
            f"{REPO}#readme": ("root", "", "readme", False),
            f"{REPO}.git": ("root", "", "", False),
            "http://www.github.com/KMAY89/SECURACV/blob/main/x.md":
                ("blob", "x.md", "", False),
            "//github.com/kmay89/securaCV/blob/main/x.md": ("blob", "x.md", "", False),
            f"{REPO}/blob/HEAD/x.md": ("blob", "x.md", "", False),
            # A browser resolves dot segments before GitHub sees the path.
            f"{REPO}/blob/main/docs/../README.md": ("blob", "README.md", "", False),
            f"{REPO}/blob/main/./docs/a.md": ("blob", "docs/a.md", "", False),
            f"{REPO}/blob/main/docs/a%20b.md#caf%C3%A9": ("blob", "docs/a b.md", "café", False),
            f"{REPO}/blob/main/docs/a.md?plain=1#L10-L20":
                ("blob", "docs/a.md", "L10-L20", True),
            # Typed without a scheme, as prose often does.
            "github.com/kmay89/securaCV/blob/main/x.md": ("blob", "x.md", "", False),
            "www.github.com/kmay89/securaCV/tree/main/docs": ("tree", "docs", "", False),
            "raw.githubusercontent.com/kmay89/securaCV/main/s.sh": ("raw", "s.sh", "", False),
        }
        for url, (kind, path, frag, plain) in cases.items():
            with self.subTest(url=url):
                self.assertEqual(self.shape(url), (kind, path, frag, plain, ""))

    def test_refused_shapes(self):
        for url, why in {
            f"{REPO}/blob/v1.0/docs/a.md": "names ref 'v1.0'",
            f"{REPO}/blob/0123abcd/docs/a.md": "names ref '0123abcd'",
            f"{REPO}/tree/feature/x/docs": "names ref 'feature'",
            f"{REPO}/blob/main": "needs a file path",
            f"{REPO}/blob/main/../../../other/x": "lead out of kmay89/securaCV",
        }.items():
            with self.subTest(url=url):
                self.assertIn(why, lr.parse_upstream(url).error)

    def test_github_pages_are_not_paths(self):
        for tail in ("issues/1", "pulls", "releases/tag/v1", "actions",
                     "commit/0123abcd", "wiki"):
            with self.subTest(tail=tail):
                self.assertEqual(self.shape(f"{REPO}/{tail}")[0], "page")

    def test_extracted_from_every_link_syntax(self):
        text = textwrap.dedent(f"""\
            Inline [a]({REPO}/blob/main/a.md#x "title"), autolink
            <{REPO}/tree/main/docs>, bare {REPO}/blob/main/b.md.
            | table | {REPO}/blob/main/c.md |
            <a href="{REPO}/blob/main/d.md">html</a>
            [ref]: {REPO}/blob/main/e.md
        """)
        self.assertEqual([u for _, u in lr.upstream_links(text)], [
            f"{REPO}/blob/main/a.md#x", f"{REPO}/tree/main/docs",
            f"{REPO}/blob/main/b.md", f"{REPO}/blob/main/c.md",
            f"{REPO}/blob/main/d.md", f"{REPO}/blob/main/e.md"])
        self.assertEqual([n for n, _ in lr.upstream_links(text)],
                         [1, 2, 2, 3, 4, 5])

    def test_code_and_comments_are_read_too(self):
        # What a reader copies (the installer command in a fence, a URL in a
        # code span) is as much a promise as what they click, and an HTML
        # comment is one edit away from the page. Nothing is masked, so a
        # stray backtick cannot hide the links after it.
        install = "https://raw.githubusercontent.com/kmay89/securaCV/main/scripts/install.sh"
        text = textwrap.dedent(f"""\
            ```bash
            curl -fsSL {install} | bash
            ```
            `{REPO}/blob/main/code-span.md`
            <!-- {REPO}/blob/main/comment.md -->
            - a stray `
            - [next item]({REPO}/blob/main/after.md)
            see github.com/kmay89/securaCV/tree/main/docs
        """)
        self.assertEqual(list(lr.upstream_links(text)), [
            (2, install), (4, f"{REPO}/blob/main/code-span.md"),
            (5, f"{REPO}/blob/main/comment.md"), (7, f"{REPO}/blob/main/after.md"),
            (8, "github.com/kmay89/securaCV/tree/main/docs")])
        self.assertEqual(list(lr.unread_mentions(text)), [])

    def test_not_links_into_the_monorepo(self):
        text = textwrap.dedent("""\
            [store](https://my.home-assistant.io/x?repository_url=https://github.com/kmay89/securaCV)
            [this repo](https://github.com/kmay89/securacv-homeassistant)
            [pages](https://kmay89.github.io/securaCV.github.io)
            https://github.com/kmay89/securaCVx/blob/main/a.md
        """)
        self.assertEqual(list(lr.upstream_links(text)), [])
        self.assertEqual(list(lr.unread_mentions(text)), [])

    def test_a_mention_the_extractor_does_not_read_is_counted(self):
        # The guard counts without the extractor's regex: a URL glued into
        # another URL's path, or a host that only ends in github.com, names
        # the repository and is not read, so the check must not pass it.
        text = textwrap.dedent(f"""\
            ok {REPO}/blob/main/a.md
            [x](https://x.example/go/https://github.com/kmay89/securaCV/blob/main/a.md)
            two {REPO}/blob/main/a.md and evilgithub.com/kmay89/securaCV/blob/main/b.md
        """)
        self.assertEqual(list(lr.unread_mentions(text)), [(2, 1, 0), (3, 2, 1)])
        with mock.patch.object(lr, "UPSTREAM_URL_RE", re.compile("(?!)")):
            self.assertEqual(list(lr.unread_mentions(text)),
                             [(1, 1, 0), (2, 1, 0), (3, 2, 0)])

    def test_the_prose_uses_only_shapes_this_check_resolves(self):
        links = [lr.parse_upstream(u) for name in lr.FILES for _, u in
                 lr.upstream_links((lr.ROOT / name).read_text("utf-8"))]
        self.assertEqual([lk.error for lk in links if lk.error], [])
        self.assertEqual({lk.kind for lk in links} - {"blob", "tree", "root", "raw"},
                         set())
        # The shapes it does use today, each covered by a case above.
        self.assertTrue(any(lk.kind == "blob" and lk.fragment for lk in links))
        self.assertTrue(any(lk.kind == "blob" and not lk.fragment for lk in links))
        self.assertTrue(any(lk.kind == "root" for lk in links))
        # The installer command the store page pipes to bash.
        self.assertIn("scripts/install.sh",
                      {lk.path for lk in links if lk.kind == "raw"})

    def test_every_mention_in_the_prose_is_a_url_the_check_reads(self):
        # Counted with neither regex, on the real files: every place a file
        # names the repository on a GitHub host (this repo and query values
        # aside) is one URL the check must read. A fixture built from the
        # extractor's own output cannot see a link it drops; this can.
        for name in lr.FILES:
            text = (lr.ROOT / name).read_text("utf-8")
            low, naive = text.lower(), 0
            for host in ("github.com", "githubusercontent.com"):
                needle = f"{host}/kmay89/securacv"
                at = low.find(needle)
                while at >= 0:
                    after = low[at + len(needle):at + len(needle) + 1]
                    query = low[:at].endswith(("=https://", "=http://", "=//",
                                               "=https://www.", "=https://raw."))
                    other_repo = after != "" and (after.isalnum() or after in "-_")
                    if not other_repo and not query:
                        naive += 1
                    at = low.find(needle, at + 1)
            with self.subTest(file=name):
                self.assertEqual(len(list(lr.upstream_links(text))), naive)
                self.assertEqual(list(lr.unread_mentions(text)), [])


class Resolver(unittest.TestCase):
    """resolve_upstream() and check_upstream() against a fixture checkout."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "securaCV"
        self.write("README.md", "# SecuraCV\n## Start here\n")
        self.write("docs/guide.md", """\
            # Guide
            ## Step 1: Install
            ## Notes
            ## Notes
            <a id="pinned"></a>
        """)
        self.write("docs/blueprints/README.md", "# Blueprints\n## Alerts\n")
        self.write("docs/empty/.keep", "")
        self.write("docs/data.yaml", "a: 1\nb: 2\nc: 3\nd: 4\ne: 5\n")
        self.write("docs/guide.rst", "Title\n=====\n")
        lr.anchors_of.cache_clear()

    def tearDown(self):
        shutil.rmtree(self.tmp)
        lr.anchors_of.cache_clear()

    def write(self, rel, text):
        p = self.src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text), encoding="utf-8")

    def why(self, url):
        return lr.resolve_upstream(lr.parse_upstream(url), self.src)

    def test_existing_files_and_directories_resolve(self):
        for url in (REPO, f"{REPO}/blob/main/docs/guide.md",
                    f"{REPO}/tree/main/docs", f"{REPO}/tree/main",
                    # GitHub redirects a blob URL of a directory to tree
                    f"{REPO}/blob/main/docs/blueprints",
                    f"{REPO}/raw/main/docs/data.yaml"):
            with self.subTest(url=url):
                self.assertIsNone(self.why(url))

    def test_a_missing_file_fails(self):
        self.assertIn("no such file", self.why(f"{REPO}/blob/main/docs/gone.md"))
        self.assertIn("no such file", self.why(f"{REPO}/tree/main/gone"))

    def test_a_renamed_heading_fails(self):
        url = f"{REPO}/blob/main/docs/guide.md#step-1-install"
        self.assertIsNone(self.why(url))
        self.write("docs/guide.md", "# Guide\n## Step 1: Set up\n")
        lr.anchors_of.cache_clear()
        self.assertIn("matches no heading", self.why(url))

    def test_duplicate_headings(self):
        self.assertIsNone(self.why(f"{REPO}/blob/main/docs/guide.md#notes"))
        self.assertIsNone(self.why(f"{REPO}/blob/main/docs/guide.md#notes-1"))
        self.assertIn("matches no heading",
                      self.why(f"{REPO}/blob/main/docs/guide.md#notes-2"))

    def test_an_explicit_anchor_lands(self):
        self.assertIsNone(self.why(f"{REPO}/blob/main/docs/guide.md#pinned"))

    def test_a_directory_anchor_reads_its_readme(self):
        self.assertIsNone(self.why(f"{REPO}/tree/main/docs/blueprints#alerts"))
        self.assertIn("docs/blueprints/README.md",
                      self.why(f"{REPO}/tree/main/docs/blueprints#gone"))
        self.assertIsNone(self.why(f"{REPO}#start-here"))
        self.assertIn("no Markdown README",
                      self.why(f"{REPO}/tree/main/docs/empty#x"))

    def test_line_anchors(self):
        yml = f"{REPO}/blob/main/docs/data.yaml"
        self.assertIsNone(self.why(f"{yml}#L5"))
        self.assertIsNone(self.why(f"{yml}#L2-L5"))
        self.assertIsNone(self.why(f"{yml}#L2C3-L4C1"))
        self.assertIn("5 line(s)", self.why(f"{yml}#L6"))
        self.assertIn("5 line(s)", self.why(f"{yml}#L2-L9"))
        self.assertIn("5 line(s)", self.why(f"{yml}#L0"))
        self.assertIn("not a line anchor", self.why(f"{yml}#intro"))
        self.assertIn("line anchor", self.why(f"{REPO}/tree/main/docs#L1"))
        self.assertIsNone(self.why(f"{REPO}/blame/main/docs/data.yaml#L5"))

    def test_rendered_markdown_needs_plain_for_lines_and_the_render_for_headings(self):
        md = f"{REPO}/blob/main/docs/guide.md"
        self.assertIn("?plain=1", self.why(f"{md}#L2"))
        self.assertIsNone(self.why(f"{md}?plain=1#L2"))
        self.assertIn("?plain=1 shows the source", self.why(f"{md}?plain=1#notes"))

    def test_other_markup_anchors_are_refused_not_guessed(self):
        self.assertIn("not computed",
                      self.why(f"{REPO}/blob/main/docs/guide.rst#title"))

    def test_raw_urls(self):
        self.assertIn("no anchors", self.why(f"{REPO}/raw/main/docs/data.yaml#L1"))
        self.assertIn("directory", self.why(f"{REPO}/raw/main/docs"))

    def test_check_upstream_reports_each_problem_by_line(self):
        page = self.tmp / "README.md"
        page.write_text(textwrap.dedent(f"""\
            # Store page
            [ok]({REPO}/blob/main/docs/guide.md#step-1-install)
            [gone]({REPO}/blob/main/docs/gone.md)
            [pinned]({REPO}/blob/v2/docs/guide.md)
            [issues]({REPO}/issues)
            `{REPO}/blob/main/in-a-code-span.md`
            [glued](https://x.example/go/https://github.com/kmay89/securaCV/blob/main/docs/guide.md)
            [store](https://my.home-assistant.io/x?repository_url=https://github.com/kmay89/securaCV)
        """), encoding="utf-8")
        problems, checked, unchecked = lr.check_upstream([page], self.src)
        self.assertEqual(checked, 4)
        self.assertEqual(unchecked, [f"README.md:5: {REPO}/issues"])
        self.assertEqual(len(problems), 4, problems)
        self.assertTrue(problems[0].startswith("README.md:3: "), problems)
        self.assertIn("no such file", problems[0])
        self.assertTrue(problems[1].startswith("README.md:4: "), problems)
        self.assertIn("names ref 'v2'", problems[1])
        self.assertTrue(problems[2].startswith("README.md:6: "), problems)
        self.assertIn("no such file", problems[2])
        self.assertTrue(problems[3].startswith("README.md:7: "), problems)
        self.assertIn("1 time(s), and only 0 read as a URL", problems[3])

    def test_a_dangling_symlink_is_named_not_a_crash(self):
        # A sparse checkout can carry a link whose target it left off disk.
        os.symlink("../spec/gone.yaml", self.src / "docs" / "linked.yaml")
        self.assertIn("symlink to ../spec/gone.yaml",
                      self.why(f"{REPO}/blob/main/docs/linked.yaml#L1"))

    def test_a_missing_prose_file_is_an_error_not_a_skip(self):
        problems, _, _ = lr.check_upstream([self.tmp / "README.md"], self.src)
        self.assertEqual(len(problems), 1)
        self.assertIn("MISSING", problems[0])

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_a_path_outside_the_sparse_checkout_says_so(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.src), "-c", "user.name=t",
                            "-c", "user.email=t@example.invalid", *args],
                           check=True, capture_output=True)
        git("init", "-q")
        git("add", "-A")
        git("commit", "-q", "-m", "fixture")
        # Cone mode keeps the files of every ancestor directory (docs/guide.md
        # stays), so the path left off has to sit beside the cone, not above.
        self.write("spec/dictionary.md", "# Dictionary\n")
        git("add", "-A")
        git("commit", "-q", "-m", "spec")
        git("sparse-checkout", "set", "docs/blueprints")
        self.assertFalse((self.src / "spec" / "dictionary.md").exists())
        self.assertIsNone(self.why(f"{REPO}/blob/main/docs/guide.md"))
        self.assertIn("outside the sparse checkout",
                      self.why(f"{REPO}/blob/main/spec/dictionary.md"))
        self.assertNotIn("sparse", self.why(f"{REPO}/blob/main/spec/never.md"))
        # A directory left off is named the same way.
        self.assertIn("outside the sparse checkout",
                      self.why(f"{REPO}/tree/main/spec"))

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_a_file_deleted_from_a_full_checkout_is_not_called_sparse(self):
        # A local run against a working checkout: the doc was moved or
        # deleted and not committed. git still has it at HEAD, but nothing
        # left it off on purpose, so "widen the sparse set" would mislead.
        for args in (("init", "-q"), ("add", "-A"),
                     ("commit", "-q", "-m", "fixture")):
            subprocess.run(["git", "-C", str(self.src), "-c", "user.name=t",
                            "-c", "user.email=t@example.invalid", *args],
                           check=True, capture_output=True)
        (self.src / "docs" / "data.yaml").unlink()
        why = self.why(f"{REPO}/blob/main/docs/data.yaml")
        self.assertIn("no such file", why)
        self.assertNotIn("sparse", why)
        self.assertIn("not committed", why)


class StorePage(unittest.TestCase):
    """The real README.md against a checkout built from its own links: every
    link lands, and renaming any one heading fails exactly that link."""

    def test_fixture_from_its_own_links_resolves_then_a_rename_fails(self):
        readme = lr.ROOT / "README.md"
        links = [lr.parse_upstream(u) for _, u in
                 lr.upstream_links(readme.read_text("utf-8"))]
        heads = {}  # path -> anchors that file must carry
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            for lk in links:
                if lk.path:
                    (src / lk.path).parent.mkdir(parents=True, exist_ok=True)
                    heads.setdefault(lk.path, set())
                    if lk.fragment:
                        heads[lk.path].add(lk.fragment)
            for path, frags in heads.items():
                # A slug of [a-z0-9_-] reads back from its words exactly.
                body = "".join(f"## {f.replace('-', ' ')}\n" for f in sorted(frags))
                (src / path).write_text(f"# Doc\n{body}", encoding="utf-8")
            lr.anchors_of.cache_clear()
            problems, checked, _ = lr.check_upstream([readme], src)
            self.assertEqual(problems, [])
            self.assertEqual(checked, len(links))

            path, frags = next((p, f) for p, f in sorted(heads.items()) if f)
            gone = sorted(frags)[0]
            text = (src / path).read_text(encoding="utf-8")
            (src / path).write_text(
                text.replace(f"## {gone.replace('-', ' ')}\n", "## Renamed\n"),
                encoding="utf-8")
            lr.anchors_of.cache_clear()
            problems, _, _ = lr.check_upstream([readme], src)
            lr.anchors_of.cache_clear()
            self.assertTrue(problems)
            self.assertTrue(all(f"#{gone} matches no heading" in p
                                for p in problems), problems)


class CommandLine(unittest.TestCase):

    def test_the_self_check_passes(self):
        self.assertEqual(lr.self_check_upstream(), [])

    def test_a_broken_slugger_fails_its_own_probes(self):
        with mock.patch.object(lr, "heading_text", lambda raw: raw):
            self.assertTrue(lr.self_check_upstream())

    def test_a_source_that_is_not_a_directory_exits_2(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch("sys.stderr", new=open(os.devnull, "w")) as err:
            try:
                self.assertEqual(lr.main(["--source", str(Path(d) / "no")]), 2)
            finally:
                err.close()

    def test_source_mode_checks_only_the_links(self):
        # A banned claim in the prose is the default mode's business; the
        # --source step must fail for its links alone.
        with mock.patch.object(lr, "lint_prose", side_effect=AssertionError), \
                mock.patch.object(lr, "check_upstream", return_value=([], 0, [])), \
                mock.patch("sys.stdout", new=open(os.devnull, "w")) as out:
            try:
                self.assertEqual(lr.main(["--source", str(lr.ROOT)]), 0)
            finally:
                out.close()


class MirrorFreshnessWiring(unittest.TestCase):
    """mirror-freshness.yml runs the check weekly, as its own step, with the
    docs in its sparse checkout, and raises the drift issue for drift only."""

    @classmethod
    def setUpClass(cls):
        cls.wf = yaml.safe_load(FRESHNESS.read_text(encoding="utf-8"))
        (cls.job,) = cls.wf["jobs"].values()
        cls.steps = cls.job["steps"]

    def step(self, needle):
        found = [s for s in self.steps if needle in s.get("run", "")]
        self.assertEqual(len(found), 1, f"one step should run {needle!r}")
        return found[0]

    def test_the_sparse_checkout_reaches_every_path_the_store_page_links(self):
        clone = self.step("sparse-checkout set")
        m = re.search(r"sparse-checkout set ((?:[^\n\\]|\\\n)+)", clone["run"])
        cone = m.group(1).replace("\\\n", " ").split()
        paths = {lr.parse_upstream(u).path for _, u in
                 lr.upstream_links((lr.ROOT / "README.md").read_text("utf-8"))}
        for path in sorted(paths - {""}):
            # Cone mode carries everything under a cone directory, and the
            # files directly in each of its ancestors (the root's included).
            parent = path.rpartition("/")[0]
            with self.subTest(path=path):
                self.assertTrue(any(
                    path == d or path.startswith(d + "/") or
                    d.startswith(path + "/") or not parent or d == parent or
                    d.startswith(parent + "/") for d in cone),
                    f"{path} is outside the sparse checkout {cone}")
        self.assertIn("custom_components/securacv", cone)  # the drift compare

    def test_the_link_check_is_its_own_step_after_a_drift_failure_too(self):
        links = self.step("lint_readme.py --source /tmp/securaCV")
        clone = self.step("sparse-checkout set")
        compare = self.step("check_mirror_sync.py --source")
        self.assertEqual(compare.get("id"), "compare")
        self.assertNotIn("lint_readme", compare["run"])
        self.assertTrue(links.get("id"))
        cond = links.get("if", "")
        self.assertIn(UNLESS_CANCELED, cond)  # runs after a red Compare too
        self.assertIn(f"steps.{clone['id']}.outcome == 'success'", cond)

    def test_the_drift_issue_is_keyed_to_the_compare_step_alone(self):
        link_id = self.step("lint_readme.py --source")["id"]
        raise_ = self.step("gh issue create")
        close = self.step("gh issue close")
        self.assertIn("steps.compare.outcome == 'failure'", raise_["if"])
        self.assertIn("github.event_name == 'schedule'", raise_["if"])
        self.assertIn("steps.compare.outcome == 'success'", close["if"])
        for s in (raise_, close):
            self.assertNotIn(link_id, s["if"])
            # A bare success() would read a failed link step as drift unfixed.
            self.assertNotIn("success()", s["if"].replace(UNLESS_CANCELED, ""))

    def test_a_pr_that_leaves_the_carried_set_alone_skips_the_drift_compare(self):
        # The prose files and the link script trigger this workflow for the
        # link step alone. A store-page PR must not go red for drift it did
        # not cause: the mirror lags the monorepo between a monorepo merge
        # and the bot/mirror-sync PR. So on a PR, Compare runs only when the
        # PR touches one of the other trigger paths, and the gate diffs
        # exactly those.
        on = self.wf.get("on", self.wf.get(True))
        link_only = {"README.md", "AGENTS.md", "CLAUDE.md",
                     ".github/scripts/lint_readme.py"}
        carried = sorted(p.removesuffix("/**") for p in on["pull_request"]["paths"]
                         if p not in link_only)
        gate = self.step("git diff --quiet HEAD^1 HEAD")
        m = re.search(r"git diff --quiet HEAD\^1 HEAD --((?:[^\n\\;]|\\\n)+)",
                      gate["run"])
        self.assertEqual(sorted(m.group(1).replace("\\\n", " ").split()), carried)
        self.assertIn("github.event_name == 'pull_request'", gate.get("if", ""))
        compare = self.step("check_mirror_sync.py --source")
        self.assertIn("github.event_name != 'pull_request'", compare.get("if", ""))
        self.assertIn(f"steps.{gate['id']}.outputs.carried != 'false'",
                      compare.get("if", ""))
        # HEAD^1 is the PR's base only if the checkout fetched the parents
        # of the merge commit it checks out.
        checkout = next(s for s in self.steps
                        if str(s.get("uses", "")).startswith("actions/checkout@"))
        self.assertGreaterEqual(int(checkout.get("with", {}).get("fetch-depth", 1)), 2)
        self.assertLess(self.steps.index(checkout), self.steps.index(gate))
        self.assertLess(self.steps.index(gate), self.steps.index(compare))

    def test_triggers_weekly_and_on_store_page_or_script_changes(self):
        on = self.wf.get("on", self.wf.get(True))
        self.assertIn("schedule", on)
        for trig in ("push", "pull_request"):
            with self.subTest(trigger=trig):
                for path in ("README.md", "AGENTS.md", "CLAUDE.md",
                             ".github/scripts/lint_readme.py"):
                    self.assertIn(path, on[trig]["paths"])


if __name__ == "__main__":
    unittest.main()
