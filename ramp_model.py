"""Car and Ramp value objects (geometry, all in cm)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Car:
    """
    Car geometry, all in cm.

    `front_overhang` is the horizontal distance from the front axle to
    the lowest point of the FRONT of the car (front lip / spoiler / valance).
    Set to 0 if your front bumper is appreciably higher than the underbody
    and not at risk of scraping.

    `rear_overhang` is the same for the rear.  In most cars the rear
    bumper sits higher than the underbody and is not at risk, so the
    default is 0.  Increase it if you want to check rear-bumper drag
    when the car climbs out of the garage.
    """
    clearance: float        # underbody-to-ground on flat
    wheelbase: float        # front-axle to rear-axle
    front_overhang: float = 0.0
    rear_overhang: float = 0.0


@dataclass(frozen=True)
class Ramp:
    rise: float  # vertical change of the slope
    run: float   # horizontal length of the slope
