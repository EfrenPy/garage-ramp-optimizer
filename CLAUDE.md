# CLAUDE.md — project-specific context

This file is the orientation guide for future Claude Code sessions
working on `garage-ramp-optimizer`.  Global rules live in
`~/.claude/`; this file documents the *project-specific* state that
is not derivable from the source alone.

## What this project is

A Python desktop optimiser that computes ramp profiles for
low-clearance cars given a fixed rise / horizontal run, generates
worker-friendly construction blueprints (PNG + PDF) in three
reference systems, and ships as PyInstaller-built Windows
executables (English `rampa-en.exe`, Spanish `rampa-es.exe`)
attached to every GitHub Release.

- Single Python source (`ramp_optimizer.py` ~3,500 lines) + a
  GUI module split (`ramp_gui.py`).
- Five profile families optimised in parallel
  (`ProcessPoolExecutor`): linear, two arcs + straight, 3 slopes,
  4 slopes, smooth PCHIP curve.
- Heavy searches use
  `scipy.optimize.differential_evolution` and are **deterministic**
  via fixed seeds.

## High-level repo layout

```
ramp_optimizer.py        core: model, CLI, profile generators, drawing
ramp_gui.py              Tkinter GUI extracted from ramp_optimizer
ramp_i18n.py             gettext-style en/es string catalogue
build_exe.py             PyInstaller wrapper (--spanish, --rebuild-bootloader)
requirements.txt         pinned scipy <1.12 (see "Gotchas")
pyproject.toml           version source (release-please updates it)
tests/                   pytest suite (chord coords, profiles, i18n, eval)
docs/
  SIGNPATH.md            SignPath Foundation application + post-approval guide
  index.md               GitHub Pages content
  ramp_profile.png       README hero image
  gui_screenshot.png     README GUI screenshot
.github/workflows/
  ci.yml                 ruff + pytest on push / PR
  release.yml            build .exes -> (sign) -> publish GitHub Release
  release-please.yml     auto-version-bump PRs from conventional commits
  docs.yml               GitHub Pages
  cleanup-storage.yml    manual workflow_dispatch to nuke Actions storage
```

## Active workstreams

### SignPath Foundation code-signing — APPLICATION SUBMITTED 2026-05-11

The Windows binaries are currently **unsigned**; SmartScreen warns
users on first launch.  Application to SignPath Foundation
(free Authenticode signing for OSS) was submitted on 2026-05-11.

- Approval ETA: 1-2 weeks from submission.
- Expected reply: email containing Organisation ID (UUID),
  Project Slug, and a one-shot CI API token.

**Pre-staged CI changes live on `signpath/wire-up`** (pushed to
origin, *no PR open*).  Do **not** merge that branch to `main`
until SignPath approves and the placeholders are filled in — CI
would otherwise fail loudly on every release.

The branch is self-contained: it adds a `sign-windows-exe` job to
`release.yml`, switches `publish-release` to download the
`*.exe-signed` artifacts, enables `--rebuild-bootloader` on the
windows build (unique bootloader hash per release), and routes
tags through two policies via a regex match:

| Tag shape | Policy |
|---|---|
| `vX.Y.Z`                            | `release-signing` |
| `vX.Y.Z-rc1` / `-alpha` / `-beta` / `-pre` | `test-signing` |

The post-approval flip-the-switch checklist is in
`docs/SIGNPATH.md`.  Two TODO placeholders need editing on the
wire-up branch when the email arrives:
`organization-id: 00000000-...` and `project-slug:
garage-ramp-optimizer`.

A `SIGNPATH_API_TOKEN` GitHub Actions secret must be created at
the same time (Repo Settings -> Secrets and variables -> Actions).

The README `main` branch already documents how end-users will
verify the future signature
(`README.md` -> "Verifying the Windows signature").

## Gotchas / non-obvious decisions

### scipy is pinned to `>=1.10,<1.12`

`requirements.txt` enforces this; do **not** relax it.  scipy
1.12+ changed `differential_evolution`'s internal RNG/iteration
strategy and regressed `search_smooth` from a -0.14 cm worst
clearance to -0.76 cm on the default Seat León / 136-540 ramp.
Dependabot will re-propose loosening the upper bound periodically;
**close those PRs with a comment pointing at this paragraph**.
Past offender: closed PR #19.

### `differential_evolution` is single-seed by default

We briefly tried best-of-3 seeds in v0.7.1 to dodge the scipy
regression; reverted in favour of the version pin
(commit `9b425e4`).  If you ever re-enable multi-seed, profile
wall-clock — 3 seeds tripled runtime from ~245 s to ~641 s.

### BLAS threads are pinned at module load

`ramp_optimizer.py` exports `OPENBLAS_NUM_THREADS=1`,
`MKL_NUM_THREADS=1`, etc. before importing numpy.  This is
mandatory: `ProcessPoolExecutor` workers otherwise contend on a
shared BLAS thread pool and the parallel block is slower than
serial.  Keep that block at the very top of the file.

### Output format toggles propagate via module globals

`_OUTPUT_PDF / _OUTPUT_PNG / _OUTPUT_CSV` are flipped by
`compute_and_save()` before any plotting code runs, and read by
`_save_fig` + inline CSV writes deeper in the file.  Yes, globals.
The alternative was threading 3 booleans through ~12 plotting
functions; this stays.

### Spanish translations live in `ramp_i18n.py`

Every user-visible string (~311 entries) routes through `t()`.
**When you add a new string anywhere — GUI, console, plot
title — also add its Spanish translation in the same commit.**
The `--spanish` build flips the language; missing translations
fall back to English, which silently breaks the Spanish .exe.

### `--rebuild-bootloader` on every release

`release.yml` passes `--rebuild-bootloader` to `build_exe.py` on
`signpath/wire-up` (will land on main when SignPath approves).
This reinstalls PyInstaller from source so the bootloader is
locally compiled against the windows-latest MSVC toolchain —
giving each release a unique bootloader hash, which helps both
SmartScreen reputation accumulation and antivirus FP rates.
Adds ~1-2 min per matrix leg.

## Release workflow

1. **Author conventional-commit changes** on `main` (`feat:`,
   `fix:`, `chore:`, `ci:`, `docs:`, `refactor:`, `test:`,
   `perf:`).  `ci:` and `chore:` are **skipped** by release-please
   when deciding whether to bump.
2. **`release-please-action`** opens / updates a PR titled
   `chore(main): release X.Y.Z` after each push to `main`.
3. **Squash-merge that PR** -> release-please creates the
   `vX.Y.Z` tag and `release-please.yml` chains `release.yml`
   (via `workflow_call`) to build and publish the GitHub Release.
4. **Forcing a release** (e.g. only `ci:` commits landed but you
   want a build): create an **empty commit** with a
   `Release-As: X.Y.Z` git-trailer footer, push, then squash-merge
   release-please's resulting PR.  This is how `v0.7.2` shipped.
5. **Do not** push tags manually (`git tag vX.Y.Z; git push
   --tags`) — release-please will treat that tag as out-of-band
   and refuse to bump on the next release.

## Branch hygiene

- Only `main` should normally exist on origin.
- The single exception today is `signpath/wire-up` (CI pre-stage,
  pending SignPath approval).
- After merging a release-please PR, the bot does NOT delete the
  remote branch automatically — clean it up with
  `git push origin --delete release-please--branches--main`
  (or any other one-off feature branch).
- Dependabot branches auto-delete on merge / close.

## Commit + PR conventions

- **Conventional Commits** mandatory for release-please routing.
- **No `Co-Authored-By: Claude` trailer** — disabled globally via
  the user's `~/.claude/settings.json`.
- Commit bodies should explain the **why**, not the **what** —
  the diff already shows the what.

## Running things locally

```bash
# Tests
pytest --cov=. --cov-report=term-missing

# Lint
ruff check .

# CLI run
python ramp_optimizer.py 136 540

# Spanish CLI run
python ramp_optimizer.py --lang es 136 540

# GUI run
python ramp_optimizer.py

# Build the windows .exe (requires Windows + Python)
python build_exe.py                  # English UI
python build_exe.py --spanish        # Spanish UI
python build_exe.py --rebuild-bootloader   # plus locally compiled bootloader
```

## Reference: prior incidents

| Date | What happened | Where to find more |
|---|---|---|
| 2026-05-09 | smooth profile regressed -0.14 -> -0.76 cm after dependency bumps. Root-caused to scipy 1.12 RNG change. | `requirements.txt` upper bound + closed PR #19 |
| 2026-05-09 | `plano_rampa_curva_muro.pdf` table overlapped the plot. Fixed via figsize / gridspec / explicit `add_axes`. | commit `f316b88` (and the smooth-blueprint twin a few commits later) |
| 2026-05-09 | Calculate button hidden on laptop screens. Fixed via 2-column inputs grid + tk Canvas scrollable wrapper + responsive geometry. | `ramp_gui.py` |
| 2026-05-09 | release-please startup_failure on chained `release.yml`. Reusable workflow needed `actions: write` permission cascade. | commit `c18e1ca` |
| 2026-05-11 | Five dependabot CI bumps merged but release-please refused to bump (`ci:` is skipped). Forced via `Release-As: 0.7.2` empty commit. | commit `7c69d3e` |
