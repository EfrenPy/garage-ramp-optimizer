"""Sanity checks on the simulator.

`evaluate` slides the car along a road profile and reports the worst
clearance under the chassis (between wheels) and under the front
overhang.  On a perfectly flat profile the clearance must equal the
ground clearance everywhere, so both worst-case numbers must be
close to it.
"""

import numpy as np
import pytest

import ramp_optimizer as ro


def test_flat_profile_clearance_equals_ground_clearance():
    ramp = ro.Ramp(rise=136.0, run=540.0)
    car = ro.Car(clearance=14.0, wheelbase=269.0,
                  front_overhang=87.0, rear_overhang=0.0)

    # A "flat" profile that just stays at y = 0 along the slope -- the
    # road extension code in `evaluate` then attaches a flat at y = rise
    # afterwards, but inside the profile region the geometry is flat,
    # so chassis clearance there must equal car.clearance.
    x = np.linspace(0.0, ramp.run, 1500)
    y = np.zeros_like(x)
    ramp_flat = ro.Ramp(rise=0.0, run=540.0)

    m = ro.evaluate(x, y, car, ramp_flat, n_positions=100, n_chassis=80)
    assert m["chassis_min"] == pytest.approx(car.clearance, abs=1e-6)
    assert m["overhang_min"] == pytest.approx(car.clearance, abs=1e-6)


def test_linear_ramp_scrapes_for_aggressive_geometry():
    """The default Seat Leon FR scenario is documented in the README to
    scrape ~ -2.9 cm under the chassis and ~ -7.9 cm under the bumper
    on a linear ramp.  Verify the simulator reproduces something in
    that ballpark."""
    ramp = ro.Ramp(rise=136.0, run=540.0)
    car = ro.Car(clearance=14.0, wheelbase=269.0,
                  front_overhang=87.0, rear_overhang=0.0)

    x, y = ro.linear_profile(ramp, n=2000)
    m = ro.evaluate(x, y, car, ramp, n_positions=1500, n_chassis=200)

    # Chassis should scrape between -2 and -4 cm.
    assert -4.0 < m["chassis_min"] < -2.0
    # Bumper should scrape between -10 and -6 cm.
    assert -10.0 < m["overhang_min"] < -6.0


def test_evaluate_returns_required_keys():
    ramp = ro.Ramp(rise=50.0, run=400.0)
    car = ro.Car(clearance=14.0, wheelbase=269.0)
    x, y = ro.linear_profile(ramp, n=300)
    m = ro.evaluate(x, y, car, ramp, n_positions=80, n_chassis=40)

    for key in (
        "chassis_min",
        "chassis_at_x",
        "chassis_at_rear",
        "overhang_min",
        "overhang_at_x",
        "overhang_at_rear",
    ):
        assert key in m, f"missing key: {key}"
