"""Capture a screenshot of the Tkinter GUI for the README.

This pops the GUI on whatever X display is set in DISPLAY, waits a
beat for the window to render, takes a screenshot of it, and exits.
On a headless Linux you can run it under Xvfb:

    xvfb-run -s "-screen 0 1280x900x24" python docs/capture_gui_screenshot.py

The screenshot is saved at  docs/gui_screenshot.png  by default.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# Force matplotlib to a non-interactive backend before importing the
# main module (otherwise Tk would try to bring up a second event loop).
os.environ.setdefault("MPLBACKEND", "Agg")

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))

import ramp_optimizer as ro  # noqa: E402


OUT_PATH = HERE / "gui_screenshot.png"


def _close_after(root, ms: int) -> None:
    root.after(ms, root.destroy)


def _take_screenshot(window_title: str, out: Path) -> None:
    """Use ImageMagick `import` to capture the named window.

    `import -window root` captures the whole virtual screen; we pick
    that to keep the snippet simple even when the WM is missing on
    Xvfb.
    """
    subprocess.run(
        ["import", "-window", "root", str(out)],
        check=True,
    )


def main() -> None:
    # Patch tkinter so we can intercept the root window after it is
    # created, schedule a destroy and a screenshot.
    import tkinter as tk

    original_mainloop = tk.Tk.mainloop

    def patched_mainloop(self, n: int = 0):
        # Pre-fill some sample inputs so the screenshot looks useful.
        # The widgets are stored as locals inside launch_gui(); we
        # cannot reach them directly, so we rely on the defaults
        # already shown by the GUI (rise=136, run=540, etc.).

        # Give Tk a moment to lay out, then snap the screen.
        def _shoot():
            try:
                self.update_idletasks()
                self.update()
                time.sleep(0.4)
                _take_screenshot(self.title(), OUT_PATH)
                print(f"Saved {OUT_PATH}")
            finally:
                self.destroy()

        self.after(800, _shoot)
        return original_mainloop(self, n)

    tk.Tk.mainloop = patched_mainloop  # type: ignore[assignment]
    ro.launch_gui()


if __name__ == "__main__":
    main()
