"""Regression tests for input validation, the i18n catalogue and the
matplotlib figure-lifecycle fix.

These guard three bugs fixed after the deep review:

* the non-interactive CLI path used to skip clearance / wheelbase /
  overhang validation, so ``ramp_optimizer 136 540 -w 0`` crashed with a
  raw ``ZeroDivisionError`` (clearance) or produced silent ``inf``/``nan``
  results (wheelbase);
* Spanish translation values must keep the exact ``{placeholder}`` set of
  their English key, otherwise ``t(s).format(**kw)`` raises ``KeyError``;
* ``_save_fig`` must close every figure it saves, otherwise the long-lived
  GUI process leaks a Figure per blueprint on each run.
"""

import re

import pytest

import ramp_optimizer as ro
from ramp_i18n import _TRANSLATIONS_ES


# --------------------------------------------------------------------- #
#  CLI validation guards (non-interactive path)
# --------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "argv",
    [
        ["ramp_optimizer", "136", "540", "-w", "0"],      # wheelbase = 0
        ["ramp_optimizer", "136", "540", "-c", "0"],      # clearance = 0
        ["ramp_optimizer", "136", "540", "-c", "-5"],     # clearance < 0
        ["ramp_optimizer", "136", "540", "-f", "-1"],     # front overhang < 0
        ["ramp_optimizer", "136", "540", "-r", "-1"],     # rear overhang < 0
        ["ramp_optimizer", "0", "540"],                   # rise = 0
        ["ramp_optimizer", "136", "0"],                   # run = 0
    ],
)
def test_invalid_car_or_ramp_params_exit_cleanly(argv, monkeypatch):
    """Bad numeric parameters must raise SystemExit (a controlled exit
    with a friendly message), never an uncaught arithmetic error."""
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit):
        ro.parse_inputs()


def test_valid_params_do_not_raise(monkeypatch):
    """A well-formed invocation parses without raising."""
    monkeypatch.setattr("sys.argv", ["ramp_optimizer", "136", "540"])
    ramp, car, *_ = ro.parse_inputs()
    assert car.wheelbase > 0 and car.clearance > 0
    assert ramp.rise == 136.0 and ramp.run == 540.0


# --------------------------------------------------------------------- #
#  i18n catalogue integrity
# --------------------------------------------------------------------- #
def _placeholders(s: str) -> set:
    return set(re.findall(r"\{[^}]*\}", s))


def test_translations_keep_placeholder_sets():
    """Every Spanish value uses exactly the placeholders of its English
    key, so no ``.format(**kw)`` on a translated string can KeyError."""
    mismatches = {
        k: (_placeholders(k), _placeholders(v))
        for k, v in _TRANSLATIONS_ES.items()
        if _placeholders(k) != _placeholders(v)
    }
    assert not mismatches, f"placeholder mismatches: {mismatches}"


# --------------------------------------------------------------------- #
#  matplotlib figure lifecycle
# --------------------------------------------------------------------- #
def test_sensitivity_preserves_run_order():
    """The candidate runs are optimised in parallel; the returned rows
    must still line up with the input ``runs`` order."""
    car = ro.Car(clearance=14.0, wheelbase=269.0,
                 front_overhang=87.0, rear_overhang=0.0)
    ramp = ro.Ramp(rise=136.0, run=540.0)
    runs = [540.0, 620.0]
    rows = ro.sensitivity(car, ramp, runs)
    assert [r[0] for r in rows] == runs
    # A longer run can only help, so its worst score is >= the base run's.
    assert rows[1][3] >= rows[0][3]


def test_save_fig_closes_the_figure(monkeypatch):
    """_save_fig must release the figure so repeated GUI runs do not leak
    Figure objects into matplotlib's global registry."""
    plt = pytest.importorskip("matplotlib.pyplot")
    # Skip disk writes; we only care that the figure is closed afterwards.
    monkeypatch.setattr(ro, "_OUTPUT_PNG", False)
    monkeypatch.setattr(ro, "_OUTPUT_PDF", False)

    before = set(plt.get_fignums())
    fig = plt.figure()
    assert set(plt.get_fignums()) - before, "figure was not created"

    ro._save_fig(fig, "unused_blueprint.png")

    assert fig.number not in plt.get_fignums(), "figure was not closed"
