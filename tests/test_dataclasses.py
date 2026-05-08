"""Sanity checks on the Ramp and Car dataclasses."""

import pytest

import ramp_optimizer as ro


def test_ramp_basic_properties():
    ramp = ro.Ramp(rise=136.0, run=540.0)
    assert ramp.rise == pytest.approx(136.0)
    assert ramp.run == pytest.approx(540.0)


def test_ramp_is_frozen():
    ramp = ro.Ramp(rise=136.0, run=540.0)
    with pytest.raises(Exception):  # FrozenInstanceError, but that's a private subclass
        ramp.rise = 200.0  # type: ignore[misc]


def test_car_default_overhangs():
    car = ro.Car(clearance=14.0, wheelbase=269.0)
    assert car.front_overhang == 0.0
    assert car.rear_overhang == 0.0


def test_car_named_args():
    car = ro.Car(
        clearance=14.0,
        wheelbase=269.0,
        front_overhang=87.0,
        rear_overhang=0.0,
    )
    assert car.clearance == 14.0
    assert car.wheelbase == 269.0
    assert car.front_overhang == 87.0
