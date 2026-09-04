# AGENTS.md — the brief for any AI agent working in this repo

**This repository is a distribution mirror, and that changes what you may
edit.** It is how HACS users install the
[SecuraCV](https://github.com/kmay89/securaCV) Home Assistant integration:
a byte-for-byte copy of the monorepo's `custom_components/securacv/` plus
`conftest.py`, refreshed automatically. Development happens in the
monorepo, where the privacy invariants and the dictionary-sync gate live.

## What is carried vs. what is owned here

| Files | Owner | Rule |
|---|---|---|
| `custom_components/securacv/**` (minus `brand/`), `conftest.py` | **The monorepo.** | **Never edit here.** Changes arrive as PRs on `bot/mirror-sync`, opened by the monorepo's `homeassistant-mirror.yml`; [`check_mirror_sync.py`](.github/scripts/check_mirror_sync.py) proves the copy exact and [`mirror-freshness.yml`](.github/workflows/mirror-freshness.yml) is the drift backstop. Fix integration bugs in [`kmay89/securaCV`](https://github.com/kmay89/securaCV) under `custom_components/securacv/`. |
| `README.md`, `hacs.json`, `LICENSE`, `.github/**`, `custom_components/securacv/brand/`, `requirements_test.txt`, this file, `CLAUDE.md` | **This repo.** | Editable here. `README.md` is the HACS store page (`hacs.json` sets `render_readme`), so it is the most user-facing document in the repo. `requirements_test.txt` is bumped by Dependabot in both repos and this side's pins lead. |

## Voice rules (the monorepo's AGENTS.md is the canonical statement)

1. **A group of Canaries is a "fleet."** The bird-group word for it is
   banned — a company by that name soured it. The monorepo's AGENTS.md
   (rule 3) is the canonical statement, and
   [`.github/scripts/lint_readme.py`](.github/scripts/lint_readme.py)
   enforces it on this repo's prose in CI. Only the unrelated Unix
   `flock(2)` syscall keeps its name.
2. **US spellings.** The one enumerated list of banned forms lives in the
   monorepo's `scripts/lint_spelling.py` — deliberately not repeated here.
   From a monorepo checkout: `python3 scripts/lint_spelling.py
   /path/to/this/repo/README.md`.
3. **Never overclaim.** The record is **tamper-evident** — it makes
   interference visible, never impossible, so do not write the "-proof"
   form. "Verified" means an Ed25519 signature checked against a pinned
   key, nothing looser. Absolute-security phrasing is banned outright;
   `lint_readme.py` enforces this too.

## Before you commit

```sh
python3 .github/scripts/lint_readme.py       # prose: links, words, claims
pip install -r requirements_test.txt
pytest custom_components/securacv/tests -q \
  --deselect custom_components/securacv/tests/test_homekit_projection.py::test_mirror_matches_the_dictionary \
  --deselect custom_components/securacv/tests/test_homekit_projection.py::test_hold_window_is_sane \
  --deselect custom_components/securacv/tests/test_voice.py::test_sentences_yaml_matches_registered_intents
```

(The three deselected tests need monorepo ground-truth files and fail by
design in a standalone clone — [`tests.yml`](.github/workflows/tests.yml)
deselects exactly the same three.) If you touched a workflow, also run
`python3 .github/scripts/ci_policy_check.py` (needs `pyyaml`); the ground
rules are in [`.github/CI.md`](.github/CI.md).

File issues and PRs about integration *behavior* against the main
repository — this one only distributes it.
