# Contributing

Thanks for taking a look at the project! Bug reports, feature ideas and
pull requests are all welcome.

## Reporting bugs and requesting features

Please open a [GitHub issue](https://github.com/EfrenPy/garage-ramp-optimizer/issues)
with:

- A short description of what you expected and what happened instead.
- The exact command line you used (or screenshots of the GUI inputs).
- The car geometry and ramp dimensions you tried.
- The console log shown in the GUI's "Calculation output" panel (or
  the terminal output if you ran the script directly).
- The OS, Python version and matplotlib / scipy / numpy versions if
  you can paste them (`python -c "import sys, numpy, scipy, matplotlib; print(sys.version, numpy.__version__, scipy.__version__, matplotlib.__version__)"`).

## Setting up a development environment

```bash
git clone https://github.com/EfrenPy/garage-ramp-optimizer.git
cd garage-ramp-optimizer

# Create and activate a virtual environment.
python -m venv .venv
# Windows:        .venv\Scripts\activate
# Linux / macOS:  source .venv/bin/activate

pip install --upgrade pip
pip install numpy scipy matplotlib

# Optional, only if you plan to compile the .exe:
pip install pyinstaller
```

Run the GUI:

```bash
python ramp_optimizer.py
```

Run a silent CLI calculation:

```bash
python ramp_optimizer.py 136 540
```

## Building the executable

```bash
# English UI (default)
python build_exe.py

# Spanish UI
python build_exe.py --spanish
```

The result lands in `dist/rampa.exe` (Windows) or `dist/rampa`
(Linux / macOS). See [`COMPILAR.md`](COMPILAR.md) for the full guide.

## Code style

- **Python 3.10+** features are fine (PEP 604 unions, `match`, etc.).
- Keep functions reasonably small; the optimisation core is mostly
  numerical and lives in module-level helpers — please follow the
  existing style.
- Use `numpy` for vectorised math, `scipy.optimize.differential_evolution`
  for the heavy global searches, and `matplotlib` (Agg backend) for
  every figure.  No interactive backends — the GUI is Tkinter, kept
  separate from matplotlib's GUI.
- Run the lint + test pass before opening a PR:

  ```bash
  python -m ruff check .
  python -m pytest -q
  python -m py_compile ramp_env.py ramp_model.py ramp_profiles.py \
      ramp_search.py ramp_optimizer.py ramp_gui.py ramp_i18n.py build_exe.py
  ```

  The same checks run automatically on every push and pull request via
  `.github/workflows/ci.yml`.

## Module layout

The app is a set of flat top-level modules (not a package); `ramp_optimizer`
imports the rest and re-exports their public names, so `ramp_optimizer.Car`,
`ramp_optimizer.evaluate`, etc. keep working:

| Module | Responsibility |
|---|---|
| `ramp_env.py` | Pin BLAS thread counts to 1 — **import before numpy** |
| `ramp_model.py` | `Car` / `Ramp` value objects |
| `ramp_profiles.py` | The profile-family generators (pure geometry) |
| `ramp_search.py` | `evaluate()` + the `differential_evolution` searches |
| `ramp_optimizer.py` | Blueprint drawing, CLI, `compute_and_save` orchestration |
| `ramp_gui.py` | Tkinter front-end (`launch_gui`) |
| `ramp_i18n.py` | `t()` and the `_TRANSLATIONS_ES` catalogue |

## Adding or changing user-visible strings

The application is **English by default** and ships an opt-in Spanish
translation triggered at compile time (`python build_exe.py --spanish`)
or at runtime (`--lang es` / `RAMP_LANG=es`).

If you add or change a user-visible string:

1. Write the English string verbatim where it is used, wrapped with
   `t("...")`.  For strings with placeholders, keep the format
   placeholders inside the translated string so both languages share
   the same `.format(...)` arguments.
2. Add the Spanish translation as a new key/value in the
   `_TRANSLATIONS_ES` dictionary in `ramp_i18n.py`.  Strings missing
   from the dictionary fall back to the English original at runtime, so
   the program does not break, but the user experience is mixed.
   `tests/test_validation_and_i18n.py` checks that every translation
   keeps the placeholder set of its English key.
3. If your change affects the GUI progress bar, update the `STAGES`
   list inside `launch_gui()` so the trigger substrings still match
   the localised log output.

## Adding a new profile family

Generators live in `ramp_profiles.py` and their searches in
`ramp_search.py`.  To add a new family:

1. Write a `your_profile(ramp, ...)` generator in `ramp_profiles.py`
   that returns `(x_array, y_array)`.
2. Write a `search_your_profile(ramp, car, ...)` in `ramp_search.py`
   that calls `evaluate(...)` to score candidates and returns a `dict`
   shaped
   like the existing `best4` / `best_smooth` (must include
   `chassis_min`, `overhang_min`, `score`, `x`, `y`).
3. Plug it into `compute_and_save(ramp, car)` and into the comparison
   plot's `profiles` list.
4. If the new profile has natural worker keypoints, write a
   `draw_your_blueprint_topref(...)` and `draw_chord_blueprint(...,
   breaks=...)` call so it gets a wall-reference and a cord-reference
   plan.

## Pull-request checklist

Before pressing "Create pull request":

- [ ] `python -m py_compile ramp_*.py build_exe.py` is clean.
- [ ] You ran `python ramp_optimizer.py 136 540` (or any other
      sensible inputs) end-to-end and verified the blueprints look
      right.
- [ ] If you touched user-visible strings, the Spanish translation
      dictionary is up to date.
- [ ] If you added new dependencies, you updated `README.md` and
      `CONTRIBUTING.md`.
- [ ] No build artifacts (`dist/`, `build/`, `*.spec`,
      `__pycache__/`, generated PNG/PDF/CSV) are staged.

## Recorded follow-ups

The geometry, profile generators and searches have been split out of
`ramp_optimizer.py` into `ramp_model` / `ramp_profiles` / `ramp_search`
(see **Module layout** above).  The remaining large piece is the
**blueprint-drawing layer** (~1500 lines of matplotlib), still in
`ramp_optimizer.py` because it is coupled to the module-level output
toggles (`_OUTPUT_PDF/PNG/CSV`).  Moving it into a `ramp_blueprints`
module — threading an explicit output-config object instead of the
globals — would finish the split.  Do it incrementally, with the test
suite (including the `--mpl` visual-regression checks) covering the
public surface after each move.

### SignPath Foundation code-signing — pending approval

An application for free Authenticode signing through
[SignPath Foundation](https://signpath.org/) was submitted on
2026-05-11.  The CI pipeline changes that activate signing live
on the `signpath/wire-up` branch and are deliberately **not
merged to `main` yet** — they reference a placeholder
Organisation UUID and would fail every release until the real
values from SignPath arrive.

When the approval email lands, follow the post-approval
flip-the-switch checklist in
[`docs/SIGNPATH.md`](docs/SIGNPATH.md):

1. Store the SignPath CI API token as the `SIGNPATH_API_TOKEN`
   repo secret.
2. Replace the two TODO placeholders on `signpath/wire-up`.
3. Open a PR from `signpath/wire-up` to `main` titled
   `ci: enable SignPath code-signing on release`.
4. Smoke-test with a `vX.Y.Z-rc1` tag (the pipeline auto-routes
   pre-release tags to the `test-signing` policy).
5. Merge the PR; subsequent stable tags ship signed.

Until then, the binaries attached to GitHub Releases remain
**unsigned** and trigger SmartScreen on first launch.

## Code of conduct

Be kind. Assume good faith.  This is a hobby project — discussion
should stay friendly and constructive.
