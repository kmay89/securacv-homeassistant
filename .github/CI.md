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
| R3 | Push/PR workflows declare a `concurrency` group; cancel superseded PR runs only — never main, never a publish |
| R4 | Action refs are pinned — never `@main`/`@master`, never docker `:latest` |
| R5 | `pull_request` workflows are path-filtered (or listed in `ci-policy.yml → unfiltered_ok` with a reason) |
| R6 | `push` and `pull_request` path lists are identical |
| R7 | A paths filter includes the workflow's own file |
| R8 | Third-party actions (any owner outside `actions/`/`github/`) are pinned to a full commit SHA with a `# <version>` comment; Dependabot bumps pin and comment together |

Exemptions live in `.github/ci-policy.yml`, never in the checker — each
one carries a comment saying why. Run the checker locally with
`python3 .github/scripts/ci_policy_check.py` (needs `pyyaml`).

Repo-specific conventions:

- The hassfest / HACS action SHA pins in `validate.yml` mirror the
  monorepo's `homeassistant-freshness.yml` — bump both together.
- `validate.yml` keeps a weekly schedule on purpose: hassfest and the
  HACS checks tighten upstream over time, and a new rule should surface
  here rather than in a user's install.
- The integration directory and `conftest.py` arrive from the monorepo
  through its `homeassistant-mirror.yml` (PRs on `bot/mirror-sync`); edit
  them there, never here. `mirror-freshness.yml` is the backstop that
  proves the copy exact. `requirements_test.txt` is owned here.
