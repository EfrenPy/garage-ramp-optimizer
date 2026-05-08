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
- Run a quick syntax check before opening a PR:
  `python -m py_compile ramp_optimizer.py build_exe.py`.

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
   `_TRANSLATIONS_ES` dictionary at the top of `ramp_optimizer.py`.
   Strings missing from the dictionary fall back to the English
   original at runtime, so the program does not break, but the user
   experience is mixed.
3. If your change affects the GUI progress bar, update the `STAGES`
   list inside `launch_gui()` so the trigger substrings still match
   the localised log output.

## Adding a new profile family

The optimisation lives in `ramp_optimizer.py`.  To add a new family:

1. Write a `your_profile(ramp, ...)` generator that returns
   `(x_array, y_array)`.
2. Write a `search_your_profile(ramp, car, ...)` that calls
   `evaluate(...)` to score candidates and returns a `dict` shaped
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

- [ ] `python -m py_compile ramp_optimizer.py build_exe.py` is clean.
- [ ] You ran `python ramp_optimizer.py 136 540` (or any other
      sensible inputs) end-to-end and verified the blueprints look
      right.
- [ ] If you touched user-visible strings, the Spanish translation
      dictionary is up to date.
- [ ] If you added new dependencies, you updated `README.md` and
      `CONTRIBUTING.md`.
- [ ] No build artifacts (`dist/`, `build/`, `*.spec`,
      `__pycache__/`, generated PNG/PDF/CSV) are staged.

## Code of conduct

Be kind. Assume good faith.  This is a hobby project — discussion
should stay friendly and constructive.
