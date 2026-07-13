"""Optimisers that search each profile family for the least-scraping
ramp, plus the evaluate() clearance simulator."""
from __future__ import annotations

import ramp_env  # noqa: F401  # pin BLAS threads before numpy
import math

import numpy as np

from ramp_model import Car, Ramp
from ramp_profiles import (
    n_slope_profile,
    smooth_profile,
    three_segment_profile,
    three_slope_keypoints,
    three_slope_profile,
)

try:
    from scipy.optimize import differential_evolution
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def evaluate(x_p, y_p, car: Car, ramp: Ramp, pad: float = 400.0,
             n_positions: int = 1500, n_chassis: int = 250):
    """
    Slide the car along the profile (extended with flat sections before
    and after) and return the worst clearance under the chassis between
    the wheels (high-centering) and under the overhangs (bumpers).
    """
    x_pre = np.linspace(-pad, 0.0, 200, endpoint=False)
    y_pre = np.zeros_like(x_pre)
    x_post = np.linspace(ramp.run, ramp.run + pad, 200)[1:]
    y_post = np.full_like(x_post, ramp.rise)

    x_road = np.concatenate([x_pre, x_p, x_post])
    y_road = np.concatenate([y_pre, y_p, y_post])
    order = np.argsort(x_road)
    x_road, y_road = x_road[order], y_road[order]
    keep = np.concatenate([[True], np.diff(x_road) > 1e-9])
    x_road, y_road = x_road[keep], y_road[keep]

    rear_xs = np.linspace(
        x_road[0] + 1.0, x_road[-1] - car.wheelbase - 1.0, n_positions
    )

    chassis_min = math.inf
    chassis_at = chassis_pos = None
    overhang_min = math.inf
    overhang_at = overhang_pos = None

    for x_rear in rear_xs:
        x_front = x_rear + car.wheelbase
        h_rear = float(np.interp(x_rear, x_road, y_road))
        h_front = float(np.interp(x_front, x_road, y_road))

        x_pts = np.linspace(
            x_rear - car.rear_overhang,
            x_front + car.front_overhang,
            n_chassis,
        )
        t = (x_pts - x_rear) / car.wheelbase
        chassis_y = h_rear + t * (h_front - h_rear) + car.clearance
        road_y = np.interp(x_pts, x_road, y_road)
        clr = chassis_y - road_y

        between = (x_pts >= x_rear) & (x_pts <= x_front)
        if between.any():
            i = int(np.argmin(clr[between]))
            v = float(clr[between][i])
            if v < chassis_min:
                chassis_min = v
                chassis_at = float(x_pts[between][i])
                chassis_pos = float(x_rear)

        out = ~between
        if out.any():
            i = int(np.argmin(clr[out]))
            v = float(clr[out][i])
            if v < overhang_min:
                overhang_min = v
                overhang_at = float(x_pts[out][i])
                overhang_pos = float(x_rear)

    return dict(
        chassis_min=chassis_min,
        chassis_at_x=chassis_at,
        chassis_at_rear=chassis_pos,
        overhang_min=overhang_min,
        overhang_at_x=overhang_at,
        overhang_at_rear=overhang_pos,
    )


def search(ramp: Ramp, car: Car, n_theta: int = 25, n_frac: int = 25,
           refine: int = 9, min_r_top: float | None = None):
    theta_lo = math.atan(ramp.rise / ramp.run)        # linear ramp limit
    theta_hi = 2.0 * math.atan(ramp.rise / ramp.run)  # zero straight middle

    # Hard-floor R_top so the crest never collapses to a near-kink.  The
    # high-centering sagitta of a wheelbase-length chord on a circle of
    # radius R is W^2 / (8R); setting R_top >= W^2 / (8C) makes that
    # sagitta no worse than the ground clearance.  We default to that
    # value so the optimiser is forced to produce a genuinely flat crest.
    if min_r_top is None:
        min_r_top = (car.wheelbase ** 2) / (8.0 * car.clearance)

    def coarse_search(t_lo, t_hi, f_lo, f_hi, nt, nf):
        best_local = None
        for theta in np.linspace(t_lo, t_hi, nt):
            for frac in np.linspace(f_lo, f_hi, nf):
                try:
                    x, y = three_segment_profile(ramp, theta, frac, n=1200)
                except ValueError:
                    continue
                # Reject splits where R_top is below the high-centering
                # floor -- they look "good" only because they trade a
                # crest scrape for a mid-slope scrape.
                sin_t, omc = math.sin(theta), 1.0 - math.cos(theta)
                if omc < 1e-9:
                    continue
                sum_r = (ramp.run * sin_t - ramp.rise * math.cos(theta)) / omc
                r_top = sum_r * frac
                if r_top < min_r_top:
                    continue
                m = evaluate(x, y, car, ramp, n_positions=1000, n_chassis=200)
                score = min(m["chassis_min"], m["overhang_min"])
                if best_local is None or score > best_local["score"]:
                    best_local = dict(
                        theta=theta, theta_deg=math.degrees(theta),
                        r_top_frac=frac, score=score, x=x, y=y, **m,
                    )
        return best_local

    # Stage 1: coarse grid.
    best = coarse_search(
        theta_lo + 1e-4, theta_hi - 1e-4, 0.05, 0.98, n_theta, n_frac
    )
    if best is None:
        raise RuntimeError("search failed")

    # Stage 2: refine around the best point.
    dt = (theta_hi - theta_lo) / n_theta
    df = 0.93 / n_frac
    refined = coarse_search(
        max(theta_lo + 1e-4, best["theta"] - dt),
        min(theta_hi - 1e-4, best["theta"] + dt),
        max(0.05, best["r_top_frac"] - df),
        min(0.98, best["r_top_frac"] + df),
        refine, refine,
    )
    if refined and refined["score"] > best["score"]:
        best = refined

    # Recompute geometry numbers for reporting.
    sin_t, cos_t = math.sin(best["theta"]), math.cos(best["theta"])
    omc = 1.0 - cos_t
    sum_r = (ramp.run * sin_t - ramp.rise * cos_t) / omc
    L_m = (ramp.rise * sin_t - ramp.run * omc) / omc
    best["sum_r"] = sum_r
    best["L_m"] = max(0.0, L_m)
    best["r_top"] = sum_r * best["r_top_frac"]
    best["r_bot"] = sum_r - best["r_top"]
    best["x_b_end"] = best["r_bot"] * sin_t
    best["y_b_end"] = best["r_bot"] * omc
    best["x_m_end"] = best["x_b_end"] + best["L_m"] * cos_t
    best["y_m_end"] = best["y_b_end"] + best["L_m"] * sin_t

    # Evaluate at high resolution on the chosen profile.
    final = evaluate(best["x"], best["y"], car, ramp,
                     n_positions=3000, n_chassis=400)
    best.update(final)
    best["score"] = min(best["chassis_min"], best["overhang_min"])
    return best


def search_n_slope(
    ramp: Ramp, car: Car, n_segments: int,
    fillet: float = 30.0,
    de_maxiter: int = 35, de_popsize: int = 12, seed: int = 7,
):
    """
    Differential-evolution search over the (n_segments - 1) interior
    breakpoints of an n-slope profile.  Each breakpoint contributes
    (x, y) coordinates, so 2 * (n_segments - 1) free parameters.
    """
    if not HAS_SCIPY:
        raise RuntimeError("scipy is required for the n-slope search")

    K = n_segments - 1                        # number of interior breakpoints
    grade = ramp.rise / ramp.run

    # Search bounds: x_i in (0, run), y_i in (0, rise).  We let the
    # objective enforce ordering and monotonicity via a heavy penalty.
    bounds = []
    for k in range(K):
        # Spread initial bounds roughly evenly along the slope to give the
        # optimiser a sensible starting region.
        x_lo = 0.05 * ramp.run + (k / K) * 0.10 * ramp.run
        x_hi = (k + 1) / K * ramp.run + 0.10 * ramp.run
        x_hi = min(x_hi, 0.95 * ramp.run)
        bounds.append((x_lo, x_hi))
    for k in range(K):
        y_lo = 0.05 * ramp.rise + (k / K) * 0.10 * ramp.rise
        y_hi = (k + 1) / K * ramp.rise + 0.10 * ramp.rise
        y_hi = min(y_hi, 0.97 * ramp.rise)
        bounds.append((y_lo, y_hi))

    def unpack(params):
        xs_int = np.asarray(params[:K], dtype=float)
        ys_int = np.asarray(params[K:], dtype=float)
        # Sort both, so the optimiser can never produce out-of-order
        # breakpoints (this is an extra safety net on top of the bounds).
        xs_int = np.sort(xs_int)
        ys_int = np.sort(ys_int)
        # Make sure breakpoints are reasonably spaced apart in x.
        for i in range(1, K):
            if xs_int[i] - xs_int[i - 1] < 30:
                xs_int[i] = xs_int[i - 1] + 30
        # Reject if last x is past the slope, or last y past the top.
        if xs_int[-1] > ramp.run - 30 or ys_int[-1] > ramp.rise - 0.5:
            return None
        return list(zip(xs_int, ys_int))

    def objective(params):
        breaks = unpack(params)
        if breaks is None:
            return 1e3
        try:
            xp, yp = n_slope_profile(ramp, breaks, fillet=fillet, n=600)
        except ValueError:
            return 1e3
        try:
            m = evaluate(xp, yp, car, ramp,
                         n_positions=400, n_chassis=100, pad=300)
        except Exception:
            return 1e3
        score = min(m["chassis_min"], m["overhang_min"])
        return -score

    # Use the legacy RandomState here -- the existing seed (7) was tuned
    # against scipy's default RandomState behaviour, and switching to
    # ``default_rng`` shifts the RNG stream onto a different PCG64
    # sequence, which lands DE in a worse 4-slope optimum for the typical
    # garage geometry.  Passing the RandomState explicitly also avoids
    # the scipy 1.15+ deprecation warning attached to ``seed=int``.
    result = differential_evolution(
        objective, bounds,
        maxiter=de_maxiter, popsize=de_popsize,
        seed=np.random.RandomState(seed),
        tol=1e-3, mutation=(0.4, 1.2), recombination=0.85,
        polish=True, workers=1, updating="deferred",
    )

    breaks = unpack(result.x)
    if breaks is None:
        raise RuntimeError(f"{n_segments}-slope search failed to converge")
    xp, yp = n_slope_profile(ramp, breaks, fillet=fillet, n=1500)
    m = evaluate(xp, yp, car, ramp, n_positions=3000, n_chassis=400)
    out = dict(
        n_segments=n_segments,
        breaks=breaks,
        fillet=fillet,
        x=xp, y=yp,
        score=min(m["chassis_min"], m["overhang_min"]),
        **m,
    )
    # Slope angles for reporting.
    pts = [(0.0, 0.0)] + list(breaks) + [(ramp.run, ramp.rise)]
    out["segments"] = []
    for i in range(len(pts) - 1):
        xa, ya = pts[i]
        xb, yb = pts[i + 1]
        dx, dy = xb - xa, yb - ya
        out["segments"].append(dict(
            i=i + 1,
            x_a=xa, y_a=ya, x_b=xb, y_b=yb,
            angle_deg=math.degrees(math.atan2(dy, dx)),
            percent=100.0 * dy / dx,
            length=math.hypot(dx, dy),
        ))
    return out


def search_smooth(
    ramp: Ramp, car: Car,
    K: int = 5,                  # number of interior control points
    de_maxiter: int = 50, de_popsize: int = 14, seed: int = 11,
):
    """
    Optimise the K interior control points of a monotone cubic-spline
    profile.  Each control point contributes (x_frac, y_frac) in (0, 1).
    """
    if not HAS_SCIPY:
        raise RuntimeError("scipy is required for the smooth-profile search")

    # Seed the optimiser with a roughly S-shaped start (concave-up bottom,
    # concave-down top), which is what we expect the answer to look like.
    bounds_x = [(k / (K + 1) - 0.5 / (K + 1),
                 k / (K + 1) + 0.5 / (K + 1))
                for k in range(1, K + 1)]
    bounds_y = [(0.001, 0.999) for _ in range(K)]
    bounds = bounds_x + bounds_y

    def objective(params):
        xfs = np.asarray(params[:K])
        yfs = np.asarray(params[K:])
        try:
            xp, yp, _, _ = smooth_profile(ramp, xfs, yfs, n=600)
        except Exception:
            return 1e3
        try:
            m = evaluate(xp, yp, car, ramp,
                         n_positions=400, n_chassis=100, pad=300)
        except Exception:
            return 1e3
        score = min(m["chassis_min"], m["overhang_min"])
        return -score

    # Use modern PCG64 via ``default_rng`` for the smooth search -- it
    # samples the design space differently from the legacy MT19937 and
    # in our geometry it consistently finds a better (less-scratching)
    # PCHIP optimum.  Passing a Generator explicitly also pins the RNG
    # stream, so consecutive runs of the same input cannot land on
    # different control points.
    result = differential_evolution(
        objective, bounds,
        maxiter=de_maxiter, popsize=de_popsize,
        seed=np.random.default_rng(seed),
        tol=1e-3, mutation=(0.4, 1.3), recombination=0.85,
        polish=True, workers=1, updating="deferred",
    )

    xfs = np.asarray(result.x[:K])
    yfs = np.asarray(result.x[K:])
    xp, yp, xs_ctrl, ys_ctrl = smooth_profile(ramp, xfs, yfs, n=2400)
    m = evaluate(xp, yp, car, ramp, n_positions=3000, n_chassis=400)
    out = dict(
        K=K,
        xs_ctrl=xs_ctrl, ys_ctrl=ys_ctrl,
        x=xp, y=yp,
        score=min(m["chassis_min"], m["overhang_min"]),
        **m,
    )
    return out


def search_three_slope(ramp: Ramp, car: Car, n_grid: int = 11,
                       fillet: float = 30.0) -> dict:
    """
    Search the four-parameter space (x1, y1, x2, y2) for the best
    three-slope profile.  Coarse grid + refinement.
    """
    grade = ramp.rise / ramp.run

    def grid_search(x1_lo, x1_hi, y1_lo, y1_hi,
                    x2_lo, x2_hi, y2_lo, y2_hi, n):
        best_local = None
        for x1 in np.linspace(x1_lo, x1_hi, n):
            for x2 in np.linspace(max(x1 + 30, x2_lo), x2_hi, n):
                if x2 <= x1 + 30:
                    continue
                for y1 in np.linspace(y1_lo, y1_hi, n):
                    if y1 / x1 >= grade:    # bottom slope must be gentler than mean
                        continue
                    for y2 in np.linspace(max(y1 + 5, y2_lo), y2_hi, n):
                        if y2 <= y1:
                            continue
                        if (ramp.rise - y2) / (ramp.run - x2) >= grade:
                            continue        # top slope must be gentler than mean
                        try:
                            x, y = three_slope_profile(
                                ramp, x1, y1, x2, y2, fillet=fillet, n=1200
                            )
                        except ValueError:
                            continue
                        m = evaluate(x, y, car, ramp,
                                     n_positions=900, n_chassis=180)
                        sc = min(m["chassis_min"], m["overhang_min"])
                        if best_local is None or sc > best_local["score"]:
                            best_local = dict(
                                x1=x1, y1=y1, x2=x2, y2=y2,
                                fillet=fillet, score=sc, x=x, y=y, **m,
                            )
        return best_local

    # Coarse pass.
    best = grid_search(
        0.10 * ramp.run, 0.45 * ramp.run,
        0.5,             0.30 * ramp.rise,
        0.55 * ramp.run, 0.92 * ramp.run,
        0.55 * ramp.rise, 0.97 * ramp.rise,
        n_grid,
    )
    if best is None:
        raise RuntimeError("three-slope search failed")

    # Refine around the best point.
    dx = ramp.run / n_grid
    dy = ramp.rise / n_grid
    refined = grid_search(
        max(20.0, best["x1"] - dx),  best["x1"] + dx,
        max(0.5,  best["y1"] - dy),  best["y1"] + dy,
        max(best["x1"] + 40, best["x2"] - dx), min(ramp.run - 20.0, best["x2"] + dx),
        max(best["y1"] + 5, best["y2"] - dy), min(ramp.rise - 0.5, best["y2"] + dy),
        max(7, n_grid // 2 + 1),
    )
    if refined and refined["score"] > best["score"]:
        best = refined

    # Final high-resolution evaluation.
    final = evaluate(best["x"], best["y"], car, ramp,
                     n_positions=3000, n_chassis=400)
    best.update(final)
    best["score"] = min(best["chassis_min"], best["overhang_min"])
    # Slope angles for reporting.
    best["slope1_deg"] = math.degrees(math.atan2(best["y1"], best["x1"]))
    best["slope2_deg"] = math.degrees(math.atan2(
        best["y2"] - best["y1"], best["x2"] - best["x1"]
    ))
    best["slope3_deg"] = math.degrees(math.atan2(
        ramp.rise - best["y2"], ramp.run - best["x2"]
    ))
    return best
