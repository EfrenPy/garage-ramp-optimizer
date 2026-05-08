"""Mathematical checks on the chord-reference projection.

Chord coordinates project a (x, y) point onto the straight cord
between T = (run, rise) and B = (0, 0):

    s = distance along the cord from T toward B
    p = perpendicular distance from the cord, with the sign convention
        p > 0  ->  surface ABOVE the cord
        p < 0  ->  surface BELOW the cord
"""

import math

import numpy as np
import pytest

import ramp_optimizer as ro


@pytest.fixture
def ramp():
    return ro.Ramp(rise=136.0, run=540.0)


def test_endpoints(ramp):
    """T and B both sit on the cord, p must be 0 there."""
    s, p = ro.chord_coords(ramp, np.array([ramp.run]), np.array([ramp.rise]))
    assert s[0] == pytest.approx(0.0, abs=1e-6)
    assert p[0] == pytest.approx(0.0, abs=1e-6)

    s, p = ro.chord_coords(ramp, np.array([0.0]), np.array([0.0]))
    L = math.hypot(ramp.run, ramp.rise)
    assert s[0] == pytest.approx(L, abs=1e-6)
    assert p[0] == pytest.approx(0.0, abs=1e-6)


def test_midpoint(ramp):
    """The middle of the cord projects to s = L/2 with p = 0."""
    L = math.hypot(ramp.run, ramp.rise)
    midx, midy = ramp.run / 2, ramp.rise / 2
    s, p = ro.chord_coords(ramp, np.array([midx]), np.array([midy]))
    assert s[0] == pytest.approx(L / 2, abs=1e-6)
    assert p[0] == pytest.approx(0.0, abs=1e-6)


def test_below_chord_is_negative_p(ramp):
    """Profile points below the cord must have p < 0 (sag side)."""
    # At x = run/2 the cord is at y = rise/2.  A point at (run/2, 0)
    # is below the cord, so p < 0.
    s, p = ro.chord_coords(ramp, np.array([ramp.run / 2]), np.array([0.0]))
    assert p[0] < 0


def test_above_chord_is_positive_p(ramp):
    """Profile points above the cord must have p > 0."""
    s, p = ro.chord_coords(ramp, np.array([ramp.run / 2]), np.array([ramp.rise]))
    assert p[0] > 0


def test_perpendicular_distance_magnitude(ramp):
    """For a single point, |p| should match the geometric perpendicular
    distance from the point to the cord line."""
    L = math.hypot(ramp.run, ramp.rise)
    point = np.array([200.0]), np.array([10.0])

    s, p = ro.chord_coords(ramp, *point)

    # Geometric perpendicular distance from (x, y) to the line through
    # (0, 0) and (run, rise):
    #   distance = |rise * x - run * y| / L
    expected_abs = abs(ramp.rise * point[0][0] - ramp.run * point[1][0]) / L
    assert abs(p[0]) == pytest.approx(expected_abs, abs=1e-6)


def test_array_shape_preserved(ramp):
    """chord_coords should keep the input array shape."""
    xs = np.linspace(0, ramp.run, 17)
    ys = np.linspace(0, ramp.rise, 17)
    s, p = ro.chord_coords(ramp, xs, ys)
    assert s.shape == xs.shape
    assert p.shape == ys.shape
