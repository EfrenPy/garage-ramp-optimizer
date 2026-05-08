#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_exe.py
============

Compile ramp_optimizer.py into a native GUI executable (rampa.exe on
Windows, ./rampa on Linux/Mac) using PyInstaller.

Author: Efren Rodriguez Rodriguez
Web:    https://efrenrodriguezrodriguez.com/

Usage
-----

    Windows   ->  open cmd or PowerShell here and run:
                      python build_exe.py
                  Result: dist\\rampa.exe   (English UI by default)

    Spanish UI version:
                      python build_exe.py --spanish
                      (or  --es  for short)
                  Result: dist\\rampa.exe   (Spanish UI)

    Linux/Mac ->  python3 build_exe.py [--spanish]
                  Result: dist/rampa

What it does
------------
1. Checks that numpy, scipy, matplotlib and pyinstaller are installed;
   pip-installs them if missing.
2. Cleans previous builds (build/, dist/, rampa.spec).
3. If --spanish is given, drops a marker file `_lang_es.flag` next to
   the script and bundles it into the .exe via PyInstaller's
   --add-data.  At runtime the executable detects the marker and
   switches the UI / output files to Spanish.
4. Calls PyInstaller with the right flags:
     --onefile      -> single self-contained executable
     --windowed     -> no console window (we ship a Tkinter GUI)
     --hidden-import matplotlib.backends.backend_pdf  (and
                     backend_agg, backend_svg) so matplotlib can write
                     PDF / PNG / SVG inside the bundled .exe
     --hidden-import tkinter*  in case PyInstaller does not detect them
     --collect-submodules scipy / matplotlib.backends
     --collect-data matplotlib
5. Verifies the executable was created and prints a short usage hint.

The resulting executable launches the GUI by default.  Calling it with
command-line arguments (e.g. `rampa.exe 136 540`) runs the silent mode
that just produces the blueprints without opening the GUI.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_PACKAGES = ["numpy", "scipy", "matplotlib", "pyinstaller"]

PROJECT_DIR = Path(__file__).resolve().parent
SCRIPT = PROJECT_DIR / "ramp_optimizer.py"
LANG_FLAG_FILE = PROJECT_DIR / "_lang_es.flag"
ICON_FILE = PROJECT_DIR / "docs" / "icon.ico"
LOCALE_DIR = PROJECT_DIR / "locale"


def run(cmd, **kw):
    print(">>>", " ".join(str(c) for c in cmd))
    return subprocess.check_call(cmd, **kw)


def ensure_package(pkg_name: str, import_name: str | None = None) -> None:
    """pip-install *pkg_name* if it is not importable."""
    name_for_import = import_name or pkg_name
    try:
        __import__(name_for_import)
        print(f"OK  {pkg_name} is already installed.")
        return
    except ImportError:
        pass
    print(f"... installing {pkg_name} ...")
    run([sys.executable, "-m", "pip", "install", "--upgrade", pkg_name])


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="build_exe",
        description="Compile ramp_optimizer.py into a native GUI executable. "
                    "Pass --spanish to bundle a Spanish UI.",
    )
    p.add_argument(
        "--spanish", "--es", dest="spanish", action="store_true",
        help="Build the Spanish version of the GUI and the output blueprints.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 70)
    print("  Garage ramp optimizer - build script")
    print("=" * 70)
    print(f"  System      : {platform.system()} {platform.release()}")
    print(f"  Python      : {sys.version.split()[0]}")
    print(f"  Folder      : {PROJECT_DIR}")
    print(f"  Language    : {'Spanish (es)' if args.spanish else 'English (en)'}")
    print()

    if not SCRIPT.exists():
        print(f"ERROR: cannot find {SCRIPT}", file=sys.stderr)
        sys.exit(1)

    # 1) Ensure dependencies.
    print("Step 1: ensuring required dependencies are installed...")
    ensure_package("numpy")
    ensure_package("scipy")
    ensure_package("matplotlib")
    ensure_package("pyinstaller", import_name="PyInstaller")
    print()

    # 2) Clean previous builds.
    print("Step 2: cleaning previous builds...")
    for d in ("build", "dist"):
        target = PROJECT_DIR / d
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    spec_file = PROJECT_DIR / "rampa.spec"
    if spec_file.exists():
        spec_file.unlink()
    # Drop or recreate the language marker file.
    if LANG_FLAG_FILE.exists():
        LANG_FLAG_FILE.unlink()
    print()

    # 3) Run PyInstaller.
    print("Step 3: building with PyInstaller "
          "(this may take a couple of minutes)...")

    sep = ";" if platform.system() == "Windows" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                  # single self-contained .exe
        "--windowed",                 # no console window (it is a GUI)
        "--name", "rampa",
        "--noconfirm",
        "--clean",
        # scipy and matplotlib load some modules dynamically; these flags
        # make sure PyInstaller bundles them all.
        "--collect-submodules", "scipy",
        "--collect-submodules", "matplotlib.backends",
        "--collect-data", "matplotlib",
        # Specific backends.  Without these matplotlib's lazy import of
        # backend_pdf would fail at runtime.
        "--hidden-import", "matplotlib.backends.backend_pdf",
        "--hidden-import", "matplotlib.backends.backend_agg",
        "--hidden-import", "matplotlib.backends.backend_svg",
        # Tkinter ships with Python but some PyInstaller versions still
        # need it spelled out.
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
    ]

    # Custom application icon, when present (only matters on Windows
    # / macOS; PyInstaller silently ignores it on Linux .onefile builds).
    if ICON_FILE.exists():
        cmd += ["--icon", str(ICON_FILE)]

    # Bundle the gettext catalog so the Spanish UI can use the standard
    # gettext path at runtime (with the in-process dict as fallback).
    # The catalog is generated by ``scripts/sync_translations.py``.
    if LOCALE_DIR.is_dir():
        cmd += ["--add-data", f"{LOCALE_DIR}{sep}locale"]

    if args.spanish:
        # Create the marker file and bundle it.  ramp_optimizer.py looks
        # for it inside sys._MEIPASS at startup and switches LANGUAGE to
        # 'es' when present.
        LANG_FLAG_FILE.write_text("es", encoding="utf-8")
        cmd += ["--add-data", f"{LANG_FLAG_FILE}{sep}."]

    cmd.append(str(SCRIPT))

    try:
        run(cmd, cwd=PROJECT_DIR)
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: PyInstaller failed with exit code {e.returncode}.",
              file=sys.stderr)
        sys.exit(e.returncode)
    finally:
        # Marker is bundled inside the .exe; we can remove it from the
        # source tree to keep things clean.
        if LANG_FLAG_FILE.exists():
            try:
                LANG_FLAG_FILE.unlink()
            except OSError:
                pass

    # 4) Verify result.
    is_windows = platform.system() == "Windows"
    out_name = "rampa.exe" if is_windows else "rampa"
    out_path = PROJECT_DIR / "dist" / out_name
    print()
    if not out_path.exists():
        print(f"ERROR: did not create {out_path}", file=sys.stderr)
        sys.exit(1)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print("=" * 70)
    lang_tag = " [Spanish UI]" if args.spanish else " [English UI]"
    print(f"  OK. Executable created{lang_tag}:")
    print(f"    {out_path}   ({size_mb:.1f} MB)")
    print("=" * 70)
    print()
    print("Usage:")
    if is_windows:
        print(r"  - Double-click dist\rampa.exe   -> opens the GUI.")
        print(r"  - From cmd:   dist\rampa.exe 136 540   "
              r"(silent mode, just generates the blueprints).")
    else:
        print("  - ./dist/rampa            -> opens the GUI.")
        print("  - ./dist/rampa 136 540    (silent mode).")
    print()


if __name__ == "__main__":
    main()
