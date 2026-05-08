"""Profile-generator invariants.

Each profile generator must:
  * start at (0, 0) and end at (run, rise) within tight tolerance,
  * be monotonically non-decreasing in both x and y,
  * produce arrays of equal length.
"""

import math

import numpy as np
import pytest

import ramp_optimizer as ro


@pytest.fixture
def ramp():
    return ro.Ramp(rise=136.0, run=540.0)


def _check_basic_invariants(x, y, ramp):
    assert len(x) == len(y)
    assert x[0] == pytest.approx(0.0, abs=1e-6)
    assert y[0] == pytest.approx(0.0, abs=1e-6)
    assert x[-1] == pytest.approx(ramp.run, abs=1e-6)
    assert y[-1] == pytest.approx(ramp.rise, abs=1e-6)
    assert np.all(np.diff(x) >= -1e-9), "x must be non-decreasing"
    assert np.all(np.diff(y) >= -1e-9), "y must be non-decreasing"


def test_linear_profile(ramp):
    x, y = ro.linear_profile(ramp, n=200)
    _check_basic_invariants(x, y, ramp)
    # Linear ramp must lie on a straight line from (0,0) to (run, rise).
    expected = ramp.rise / ramp.run * x
    assert np.allclose(y, expected, atol=1e-6)


def test_three_segment_profile(ramp):
    theta = math.atan(ramp.rise / ramp.run) * 1.5  # safely inside the valid range
    x, y = ro.three_segment_profile(ramp, theta=theta, r_top_frac=0.7, n=300)
    _check_basic_invariants(x, y, ramp)


def test_n_slope_profile(ramp):
    breaks = [(150.0, 30.0), (380.0, 100.0)]
    x, y = ro.n_slope_profile(ramp, breaks, fillet=0.0, n=300)
    _check_basic_invariants(x, y, ramp)


def test_smooth_profile(ramp):
    interior_x_frac = np.array([0.2, 0.5, 0.8])
    interior_y_frac = np.array([0.15, 0.5, 0.85])
    x, y, _xc, _yc = ro.smooth_profile(ramp, interior_x_frac, interior_y_frac, n=300)
    _check_basic_invariants(x, y, ramp)


def test_three_slope_profile(ramp):
    x, y = ro.three_slope_profile(
        ramp, x1=180.0, y1=35.0, x2=420.0, y2=110.0, fillet=0.0, n=300,
    )
    _check_basic_invariants(x, y, ramp)


def test_n_slope_rejects_unsorted_breaks(ramp):
    # Breakpoints out of order must raise.
    with pytest.raises(ValueError):
        ro.n_slope_profile(ramp, [(380.0, 30.0), (150.0, 100.0)], fillet=0.0, n=20)


def test_three_slope_keypoints_count_with_no_fillet(ramp):
    # With fillet = 0, only the four corners (start, kink1, kink2, end)
    # should be returned.
    pts = ro.three_slope_keypoints(
        ramp, x1=180.0, y1=35.0, x2=420.0, y2=110.0, fillet=0.0,
    )
    kink_pts = [p for p in pts if p[3] == "kink"]
    assert len(kink_pts) == 4
