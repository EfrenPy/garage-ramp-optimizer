"""Visual-regression tests for the blueprint drawings.

Each test renders a small but realistic blueprint and pytest-mpl
compares the resulting figure pixel-for-pixel against a baseline
image stored under tests/baseline_images/.

To regenerate the baseline images after an intentional change:

    python -m pytest --mpl-generate-path=tests/baseline_images tests/test_blueprints_visual.py

To actually run the comparison:

    python -m pytest --mpl tests/test_blueprints_visual.py

Without --mpl the tests still run and just confirm the drawing code
does not crash; without baselines the comparison is silently skipped.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import ramp_optimizer as ro

# pytest-mpl is the only consumer of the Figure that the
# `mpl_image_compare`-marked tests return.  When it is not installed
# pytest emits a PytestReturnNotNoneWarning for every such test, which
# adds noise without catching anything.  Skip those tests cleanly with
# this fixture; the always-on smoke test below still guarantees the
# drawing functions execute without crashing.
HAVE_MPL_REGRESSION = pytest.importorskip.__module__ is not None
try:
    import pytest_mpl  # noqa: F401
    HAVE_MPL_REGRESSION = True
except ImportError:
    HAVE_MPL_REGRESSION = False

requires_pytest_mpl = pytest.mark.skipif(
    not HAVE_MPL_REGRESSION,
    reason="pytest-mpl is not installed",
)


# A modest geometry so the heavy parallel searches do not run.
RAMP = ro.Ramp(rise=80.0, run=400.0)
CAR = ro.Car(clearance=14.0, wheelbase=240.0,
              front_overhang=80.0, rear_overhang=0.0)


@pytest.fixture
def matplotlib_pyplot():
    """Skip the test if matplotlib's pyplot is not available."""
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        return plt
    except Exception:  # noqa: BLE001
        pytest.skip("matplotlib is not available")


@requires_pytest_mpl
@pytest.mark.mpl_image_compare(
    baseline_dir="baseline_images",
    filename="cord_4slope.png",
    tolerance=15,
)
def test_chord_blueprint_4slope(matplotlib_pyplot, tmp_path):
    """Render a 4-slope cord blueprint and compare to baseline."""
    breaks = [(80.0, 12.0), (200.0, 35.0), (320.0, 65.0)]
    x, y = ro.n_slope_profile(RAMP, breaks, fillet=0.0, n=600)
    out = tmp_path / "cord.png"
    ro.draw_chord_blueprint(
        RAMP, x_curve=x, y_curve=y,
        label="4-slope ramp", color="tab:purple",
        breaks=breaks,
        path=str(out),
    )
    # Re-open the saved figure as the figure pytest-mpl will compare.
    return matplotlib_pyplot.gcf()


@requires_pytest_mpl
@pytest.mark.mpl_image_compare(
    baseline_dir="baseline_images",
    filename="topref_4slope.png",
    tolerance=15,
)
def test_topref_blueprint_4slope(matplotlib_pyplot, tmp_path):
    """Render a 4-slope wall-reference blueprint and compare to baseline."""
    breaks = [(80.0, 12.0), (200.0, 35.0), (320.0, 65.0)]
    x, y = ro.n_slope_profile(RAMP, breaks, fillet=0.0, n=600)
    out = tmp_path / "topref.png"
    ro.draw_piecewise_blueprint_topref(
        RAMP,
        breaks=breaks,
        x_curve=x, y_curve=y,
        color="tab:purple",
        wall_height_above_top=80.0,
        label="4-slope ramp",
        path=str(out),
    )
    return matplotlib_pyplot.gcf()


def test_blueprints_do_not_crash_without_baselines(tmp_path):
    """Sanity test: even without --mpl, calling the draw functions
    must not raise. This catches regressions like the
    Axes.annotate(xy=...) bug reported in CHANGELOG without needing
    baseline images."""
    breaks = [(80.0, 12.0), (200.0, 35.0)]
    x, y = ro.n_slope_profile(RAMP, breaks, fillet=0.0, n=400)

    ro.draw_chord_blueprint(
        RAMP, x_curve=x, y_curve=y,
        label="3-slope ramp", color="tab:green",
        breaks=breaks,
        path=str(tmp_path / "cord.png"),
    )
    ro.draw_piecewise_blueprint_topref(
        RAMP,
        breaks=breaks,
        x_curve=x, y_curve=y,
        color="tab:green",
        wall_height_above_top=80.0,
        label="3-slope ramp",
        path=str(tmp_path / "topref.png"),
    )
