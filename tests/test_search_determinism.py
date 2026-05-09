"""Search-routine reproducibility.

Both ``search_smooth`` and ``search_n_slope`` must return bit-for-bit
identical results when called twice with the same inputs.  Earlier
versions of this module passed a plain ``int`` to scipy's
``differential_evolution(seed=...)``, which (in combination with
multi-threaded BLAS reordering) could produce visibly different
control points and worst-case scrape values across runs of the same
build on the same machine.  Pinning the BLAS thread counts at module
import time and passing an explicit ``np.random`` Generator/RandomState
makes the search deterministic; this regression test guards against
that property silently breaking.
"""

import numpy as np
import pytest

import ramp_optimizer as ro

scipy = pytest.importorskip("scipy")


@pytest.fixture
def ramp():
    return ro.Ramp(rise=136.0, run=540.0)


@pytest.fixture
def car():
    return ro.Car(
        clearance=14.0, wheelbase=269.0, front_overhang=87.0, rear_overhang=0.0,
    )


def test_search_smooth_is_deterministic(ramp, car):
    a = ro.search_smooth(ramp, car, K=3, de_maxiter=10, de_popsize=8)
    b = ro.search_smooth(ramp, car, K=3, de_maxiter=10, de_popsize=8)
    assert a["score"] == pytest.approx(b["score"], abs=0.0, rel=0.0)
    assert np.array_equal(a["xs_ctrl"], b["xs_ctrl"])
    assert np.array_equal(a["ys_ctrl"], b["ys_ctrl"])


def test_search_n_slope_is_deterministic(ramp, car):
    a = ro.search_n_slope(ramp, car, n_segments=3, fillet=0.0,
                          de_maxiter=10, de_popsize=8)
    b = ro.search_n_slope(ramp, car, n_segments=3, fillet=0.0,
                          de_maxiter=10, de_popsize=8)
    assert a["score"] == pytest.approx(b["score"], abs=0.0, rel=0.0)
    assert a["breaks"] == b["breaks"]
