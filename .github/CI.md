# CI ground rules

Same rules as the monorepo — `kmay89/securaCV`'s `.github/CI.md` is the
canonical statement, with the full "why" for each rule. This repo vendors
the same checker (`.github/scripts/ci_policy_check.py`, run by
`workflows-lint.yml` on every PR that touches CI), so the rules are
machine-enforced here too and can't rot by forgetting.

In one line each:

| # | Rule |
|---|------|
| R1 | Every workflow declares `permissions` (least-privilege `GITHUB_TOKEN`, always explicit) |
| R2 | Every job sets `timeout-minutes` |
| R3 | Push/PR workflows declare a `concurrency` group. **Tests:** `group: <name>-${{ github.ref }}-${{ github.event_name == 'pull_request' && 'pr' \|\| github.sha }}` + `cancel-in-progress: ${{ github.event_name == 'pull_request' }}` — PR runs collapse per branch, every main commit gets its own group. GitHub keeps one *pending* run per group and a third arrival evicts it, so a shared per-ref group can leave a main commit unchecked while looking merely queued. **Publishers** keep `group: <name>-${{ github.ref }}` + `cancel-in-progress: false`, listed in `ci-policy.yml → main_queue_ok` (this repo has none). Never a bare `cancel-in-progress: true` on a branch push |
| R4 | Action refs are pinned — never `@main`/`@master`, never docker `:latest` |
| R5 | `pull_request` workflows are path-filtered (or listed in `ci-policy.yml → unfiltered_ok` with a reason) |
| R6 | `push` and `pull_request` path lists are identical |
| R7 | A paths filter includes the workflow's own file |
| R8 | Third-party actions (any owner outside `actions/`/`github/`) are pinned to a full commit SHA with a `# <version>` comment; Dependabot bumps pin and comment together |

Exemptions live in `.github/ci-policy.yml`, never in the checker — each
one carries a comment saying why. Run the checker locally with
`python3 .github/scripts/ci_policy_check.py` (needs `pyyaml`), and its
tests with `python3 -m unittest discover -s .github/scripts -p 'test_*.py'`.

Repo-specific conventions:

- The hassfest / HACS action SHA pins in `validate.yml` mirror the
  monorepo's `validate.yml` (whose `release.yml` carries the HACS pin
  too) — bump them together.
- `validate.yml` keeps a weekly schedule on purpose: hassfest and the
  HACS checks tighten upstream over time, and a new rule should surface
  here rather than in a user's install.
- The integration directory and `conftest.py` arrive from the monorepo
  through its `homeassistant-mirror.yml` (PRs on `bot/mirror-sync`); edit
  them there, never here. `mirror-freshness.yml` is the backstop that
  proves the copy exact; its weekly run raises one drift issue, and the
  first passing run on `main` closes it.
- `requirements_test.txt` is owned here (Dependabot bumps it in both
  repos). `tests.yml`'s `lint` job runs its pinned ruff and mypy with the
  monorepo's `pyproject.toml` config (read from `main`, not copied), so a
  bump to either is checked here too, not only in the monorepo.
