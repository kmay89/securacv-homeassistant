#!/usr/bin/env python3
"""Unit tests for the CI policy checker (.github/CI.md).

Run:  python3 -m unittest discover -s .github/scripts -p 'test_*.py' -v

R3's eviction half is a single string test on the group name; the cases
below pin what counts as a per-commit group and what an exemption looks
like, so the rule cannot silently widen or narrow. Ported with the rule from
the monorepo's .github/scripts/test_ci_policy_check.py.
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ci_policy_check as cpc  # noqa: E402

BASE_POLICY = {"timeout_max": 120}


def _problems(body: str, policy: dict | None = None) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "wf.yml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(body))
        return cpc.check_workflow(path, policy or BASE_POLICY)


class R3Eviction(unittest.TestCase):
    TEST_WF = """
        on:
          push: {branches: [main], paths: ['x/**', '.github/workflows/wf.yml']}
          pull_request: {paths: ['x/**', '.github/workflows/wf.yml']}
        permissions: {contents: read}
        concurrency:
          group: %s
          cancel-in-progress: ${{ github.event_name == 'pull_request' }}
        jobs:
          t:
            runs-on: ubuntu-latest
            timeout-minutes: 5
            steps:
              - uses: actions/checkout@v7
    """

    def test_shared_per_ref_group_on_branch_pushes_is_flagged(self):
        probs = _problems(self.TEST_WF % "wf-${{ github.ref }}")
        self.assertTrue(any("R3" in p and "evicts" in p for p in probs), probs)

    def test_per_commit_group_passes(self):
        group = "wf-${{ github.ref }}-${{ github.event_name == 'pull_request' && 'pr' || github.sha }}"
        probs = _problems(self.TEST_WF % group)
        self.assertFalse(any("R3" in p for p in probs), probs)

    def test_publisher_exemption(self):
        policy = dict(BASE_POLICY, main_queue_ok=["wf.yml"])
        probs = _problems(self.TEST_WF % "wf-${{ github.ref }}", policy)
        self.assertFalse(any("R3" in p for p in probs), probs)

    def test_pull_request_only_workflow_is_not_a_branch_push(self):
        probs = _problems("""
            on:
              pull_request: {paths: ['x/**', '.github/workflows/wf.yml']}
            permissions: {contents: read}
            concurrency:
              group: wf-${{ github.ref }}
              cancel-in-progress: ${{ github.event_name == 'pull_request' }}
            jobs:
              t:
                runs-on: ubuntu-latest
                timeout-minutes: 5
                steps:
                  - uses: actions/checkout@v7
        """)
        self.assertFalse(any("R3" in p for p in probs), probs)


if __name__ == "__main__":
    unittest.main()
