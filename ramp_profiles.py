"""Ramp profile generators (pure geometry, no I/O or plotting)."""
from __future__ import annotations

import ramp_env  # noqa: F401  # pin BLAS threads before numpy
import math

import numpy as np

from ramp_i18n import t
from ramp_model import Car, Ramp  # noqa: F401

try:
    from scipy.interpolate import PchipInterpolator
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def linear_profile(ramp: Ramp, n: int = 2000):
    x = np.linspace(0.0, ramp.run, n)
    y = ramp.rise * x / ramp.run
    return x, y


def three_segment_profile(
    ramp: Ramp, theta: float, r_top_frac: float, n: int = 2000
):
    """
    Bottom concave-up arc + straight middle + top concave-down arc.
    All segments are tangent at their joins.

    Closure:
        S * sin(theta) + L_m * cos(theta) = run
        S * (1 - cos(theta)) + L_m * sin(theta) = rise
    where S = R_bottom + R_top.  Solving for S and L_m:
        S   = (run * sin(theta) - rise * cos(theta)) / (1 - cos(theta))
        L_m = (rise * sin(theta) - run * (1 - cos(theta))) / (1 - cos(theta))
    """
    sin_t, cos_t = math.sin(theta), math.cos(theta)
    omc = 1.0 - cos_t
    if omc < 1e-9:
        return linear_profile(ramp, n)

    sum_r = (ramp.run * sin_t - ramp.rise * cos_t) / omc
    L_m = (ramp.rise * sin_t - ramp.run * omc) / omc
    if sum_r < -1e-6 or L_m < -1e-6:
        raise ValueError(f"theta={math.degrees(theta):.2f} deg out of range")
    sum_r = max(0.0, sum_r)
    L_m = max(0.0, L_m)

    r_top = sum_r * r_top_frac
    r_bot = sum_r - r_top

    # Distribute samples by arc length / segment length.
    arc_b = r_bot * theta
    arc_t = r_top * theta
    total_len = arc_b + L_m + arc_t
    if total_len < 1e-9:
        return linear_profile(ramp, n)
    n_b = max(2, int(round(n * arc_b / total_len)))
    n_m = max(2, int(round(n * L_m / total_len))) if L_m > 1e-6 else 0
    n_t = max(2, n - n_b - n_m)

    # Bottom arc: centre (0, r_bot), tangent horizontal at the start.
    s_b = np.linspace(0.0, theta, n_b)
    x_b = r_bot * np.sin(s_b)
    y_b = r_bot * (1.0 - np.cos(s_b))

    x_b_end = float(x_b[-1])
    y_b_end = float(y_b[-1])

    # Straight middle (skip its first point to avoid duplication).
    if n_m > 0:
        s_m = np.linspace(0.0, L_m, n_m + 1)[1:]
        x_m = x_b_end + s_m * cos_t
        y_m = y_b_end + s_m * sin_t
        x_m_end = float(x_m[-1])
        y_m_end = float(y_m[-1])
    else:
        x_m = np.empty(0)
        y_m = np.empty(0)
        x_m_end = x_b_end
        y_m_end = y_b_end

    # Top arc: centre offset r_top to the right and below the join along
    # the inward normal (sin theta, -cos theta).
    cx = x_m_end + r_top * sin_t
    cy = y_m_end - r_top * cos_t
    a = np.linspace(math.pi / 2 + theta, math.pi / 2, n_t + 1)[1:]
    x_t = cx + r_top * np.cos(a)
    y_t = cy + r_top * np.sin(a)

    x = np.concatenate([x_b, x_m, x_t])
    y = np.concatenate([y_b, y_m, y_t])
    # Snap endpoints to exact target.
    x[0], y[0] = 0.0, 0.0
    x[-1], y[-1] = ramp.run, ramp.rise
    return x, y


def n_slope_profile(
    ramp: Ramp,
    breakpoints,           # list of (xi, yi) interior break points
    fillet: float = 30.0,
    n: int = 2400,
):
    """
    Piecewise-linear profile through (0, 0), the interior breakpoints,
    and (run, rise), with a circular fillet of the given radius at every
    kink (start, each interior breakpoint, end).
    """
    pts = [(0.0, 0.0)] + [(float(x), float(y)) for x, y in breakpoints] + \
          [(ramp.run, ramp.rise)]

    # Validate monotonicity in x and y.
    for i in range(len(pts) - 1):
        if pts[i + 1][0] <= pts[i][0] + 1e-6:
            raise ValueError(f"x not increasing at index {i}")
        if pts[i + 1][1] < pts[i][1] - 1e-6:
            raise ValueError(f"y not non-decreasing at index {i}")

    pre = (-200.0, 0.0)
    post = (ramp.run + 200.0, ramp.rise)

    def fillet_arc(p_prev, p_corner, p_next, r):
        v1 = np.array(p_corner) - np.array(p_prev)
        v2 = np.array(p_next) - np.array(p_corner)
        L1 = float(np.linalg.norm(v1))
        L2 = float(np.linalg.norm(v2))
        if L1 < 1e-9 or L2 < 1e-9:
            return [p_corner]
        u1 = v1 / L1
        u2 = v2 / L2
        cos_phi = float(np.clip(np.dot(u1, u2), -1.0, 1.0))
        phi = math.acos(cos_phi)
        if phi < 1e-6:
            return [p_corner]
        t = r / math.tan((math.pi - phi) / 2.0)
        t = min(t, 0.45 * L1, 0.45 * L2)
        if t < 1e-6:
            return [p_corner]
        a = np.array(p_corner) - u1 * t
        b = np.array(p_corner) + u2 * t
        nrm1 = np.array([-u1[1], u1[0]])
        if np.dot(nrm1, u2) < 0:
            nrm1 = -nrm1
        r_eff = t * math.tan((math.pi - phi) / 2.0)
        c = a + nrm1 * r_eff
        ang_a = math.atan2(a[1] - c[1], a[0] - c[0])
        ang_b = math.atan2(b[1] - c[1], b[0] - c[0])
        d = ang_b - ang_a
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        m = max(8, int(40 * abs(d) / math.pi))
        ts = np.linspace(0.0, 1.0, m)
        ang = ang_a + d * ts
        return [(c[0] + r_eff * math.cos(t_), c[1] + r_eff * math.sin(t_))
                for t_ in ang]

    path = [pts[0]]
    # Fillet at start (between virtual pre and pts[1]).
    path += fillet_arc(pre, pts[0], pts[1], fillet)
    for i in range(1, len(pts) - 1):
        path += [pts[i]]
        path += fillet_arc(pts[i - 1], pts[i], pts[i + 1], fillet)
    path += [pts[-1]]
    # Fillet at end (between pts[-2] and virtual post).
    path += fillet_arc(pts[-2], pts[-1], post, fillet)

    arr = np.array(path)
    order = np.argsort(arr[:, 0])
    arr = arr[order]
    keep = np.concatenate([[True], np.diff(arr[:, 0]) > 1e-6])
    arr = arr[keep]
    xs = np.linspace(0.0, ramp.run, n)
    ys = np.interp(xs, arr[:, 0], arr[:, 1])
    return xs, ys


def smooth_profile(
    ramp: Ramp,
    interior_x_frac, interior_y_frac,
    n: int = 2400,
):
    """
    Smooth profile defined by K interior control points at fractional
    positions along x in (0, 1) and fractional y in (0, 1).  Endpoints
    are pinned to (0, 0) and (run, rise).  PCHIP gives a monotone cubic
    interpolation (no overshoot, no spurious wiggles).
    """
    if not HAS_SCIPY:
        raise RuntimeError("scipy is required for the smooth profile")

    xs_int = np.asarray(interior_x_frac, dtype=float) * ramp.run
    ys_int = np.asarray(interior_y_frac, dtype=float) * ramp.rise
    order = np.argsort(xs_int)
    xs_int = xs_int[order]
    ys_int = ys_int[order]
    # Force monotone non-decreasing in y as well.
    ys_int = np.maximum.accumulate(ys_int)

    xs_ctrl = np.concatenate([[0.0], xs_int, [ramp.run]])
    ys_ctrl = np.concatenate([[0.0], ys_int, [ramp.rise]])

    # Deduplicate close-by xs_ctrl entries.
    keep = np.concatenate([[True], np.diff(xs_ctrl) > 1e-6])
    xs_ctrl = xs_ctrl[keep]
    ys_ctrl = ys_ctrl[keep]

    pchip = PchipInterpolator(xs_ctrl, ys_ctrl, extrapolate=False)
    xs = np.linspace(0.0, ramp.run, n)
    ys = np.asarray(pchip(xs))
    # Numerical safety: clamp tiny excursions and force endpoints exact.
    ys = np.maximum.accumulate(ys)
    ys[0] = 0.0
    ys[-1] = ramp.rise
    return xs, ys, xs_ctrl, ys_ctrl


def three_slope_profile(
    ramp: Ramp,
    x1: float, y1: float,   # break point between slope 1 and slope 2
    x2: float, y2: float,   # break point between slope 2 and slope 3
    fillet: float = 30.0,   # radius of the small rounding at every kink
    n: int = 2400,
):
    """
    Three straight slopes joined by small circular fillets at every
    kink (start, between slope 1 and 2, between 2 and 3, end).

    Constraints checked:
        0 < x1 < x2 < run
        0 < y1 < y2 < rise
    The slopes increase monotonically; typically the design has a
    gentle bottom slope, a steep middle slope, and a gentle top slope.
    """
    if not (0 < x1 < x2 < ramp.run):
        raise ValueError("require 0 < x1 < x2 < run")
    if not (0 < y1 < y2 < ramp.rise):
        raise ValueError("require 0 < y1 < y2 < rise")

    # Slope angles of the three straight sections.
    a0 = 0.0
    a1 = math.atan2(y1, x1)
    a2 = math.atan2(y2 - y1, x2 - x1)
    a3 = math.atan2(ramp.rise - y2, ramp.run - x2)
    a4 = 0.0

    # Note: the gentle-steep-gentle shape (a1 < a2 > a3) is not enforced
    # here on purpose — the caller (search_three_slope) already constrains
    # the grid to that family, and callers that build ad-hoc profiles are
    # allowed any monotone shape.

    pts = [(0.0, 0.0)]

    def fillet_arc(p_prev, p_corner, p_next, r):
        """
        Insert a tangent arc at p_corner that smoothly joins the line
        p_prev->p_corner with the line p_corner->p_next.
        """
        v1 = np.array(p_corner) - np.array(p_prev)
        v2 = np.array(p_next) - np.array(p_corner)
        L1 = float(np.linalg.norm(v1))
        L2 = float(np.linalg.norm(v2))
        if L1 < 1e-9 or L2 < 1e-9:
            return [p_corner]
        u1 = v1 / L1
        u2 = v2 / L2
        # Half angle between the two tangent directions.
        cos_phi = float(np.clip(np.dot(u1, u2), -1.0, 1.0))
        phi = math.acos(cos_phi)          # external angle change
        if phi < 1e-6:
            return [p_corner]
        t = r / math.tan((math.pi - phi) / 2.0)  # tangent offset from corner
        t = min(t, 0.45 * L1, 0.45 * L2)
        if t < 1e-6:
            return [p_corner]
        a = np.array(p_corner) - u1 * t   # arc start (on incoming line)
        b = np.array(p_corner) + u2 * t   # arc end   (on outgoing line)
        # Centre is perpendicular to u1 from a, on the inside of the turn.
        # The inside is the side that the outgoing direction turns toward.
        nrm1 = np.array([-u1[1], u1[0]])
        # Pick the normal that points toward u2.
        if np.dot(nrm1, u2) < 0:
            nrm1 = -nrm1
        # Effective radius from geometry (tangent length t, half angle (pi-phi)/2)
        r_eff = t * math.tan((math.pi - phi) / 2.0)
        c = a + nrm1 * r_eff
        # Sweep from a to b around c.
        ang_a = math.atan2(a[1] - c[1], a[0] - c[0])
        ang_b = math.atan2(b[1] - c[1], b[0] - c[0])
        # Take the short way around.
        d = ang_b - ang_a
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        m = max(8, int(40 * abs(d) / math.pi))
        ts = np.linspace(0.0, 1.0, m)
        ang = ang_a + d * ts
        arc = [(c[0] + r_eff * math.cos(t_), c[1] + r_eff * math.sin(t_))
               for t_ in ang]
        return arc

    # We build the path: virtual point well to the left (flat), origin,
    # corner1 = (x1, y1), corner2 = (x2, y2), top = (run, rise), virtual
    # right point well past the top.
    pre = (-200.0, 0.0)
    p0 = (0.0, 0.0)
    p1 = (x1, y1)
    p2 = (x2, y2)
    p3 = (ramp.run, ramp.rise)
    post = (ramp.run + 200.0, ramp.rise)

    path = [p0]
    path += fillet_arc(pre, p0, p1, fillet)
    path += [p1]
    path += fillet_arc(p0, p1, p2, fillet)
    path += [p2]
    path += fillet_arc(p1, p2, p3, fillet)
    path += [p3]
    path += fillet_arc(p2, p3, post, fillet)

    # Sort by x and dedupe.
    arr = np.array(path)
    order = np.argsort(arr[:, 0])
    arr = arr[order]
    keep = np.concatenate([[True], np.diff(arr[:, 0]) > 1e-6])
    arr = arr[keep]
    # Resample uniformly.
    xs = np.linspace(0.0, ramp.run, n)
    ys = np.interp(xs, arr[:, 0], arr[:, 1])
    return xs, ys


def three_slope_keypoints(ramp: Ramp, x1: float, y1: float,
                          x2: float, y2: float, fillet: float):
    """
    Compute the labeled keypoints of the 3-slope profile (kink corners
    and the start/end of each fillet arc), so a worker can mark them
    on the ground.  Returns a list of (label, x, y, kind) tuples in
    increasing x order, where kind is "kink" or "fillet".
    """
    pre = (-200.0, 0.0)
    p0 = (0.0, 0.0)
    p1 = (x1, y1)
    p2 = (x2, y2)
    p3 = (ramp.run, ramp.rise)
    post = (ramp.run + 200.0, ramp.rise)

    def fillet_endpoints(p_prev, p_corner, p_next, r):
        v1 = np.array(p_corner) - np.array(p_prev)
        v2 = np.array(p_next) - np.array(p_corner)
        L1 = float(np.linalg.norm(v1))
        L2 = float(np.linalg.norm(v2))
        if L1 < 1e-9 or L2 < 1e-9:
            return None
        u1 = v1 / L1
        u2 = v2 / L2
        cos_phi = float(np.clip(np.dot(u1, u2), -1.0, 1.0))
        phi = math.acos(cos_phi)
        if phi < 1e-6:
            return None
        t = r / math.tan((math.pi - phi) / 2.0)
        t = min(t, 0.45 * L1, 0.45 * L2)
        if t < 1e-6:
            return None
        a = np.array(p_corner) - u1 * t
        b = np.array(p_corner) + u2 * t
        r_eff = t * math.tan((math.pi - phi) / 2.0)
        return (float(a[0]), float(a[1])), (float(b[0]), float(b[1])), r_eff

    pts = []
    # Esquina en p0 (inicio de la rampa, sobre el suelo del garaje).
    f = fillet_endpoints(pre, p0, p1, fillet)
    pts.append((t("Start of the ramp (corner)"), p0[0], p0[1], "kink", None))
    if f is not None:
        pts.append((t("End of the start fillet"), f[1][0], f[1][1], "fillet", f[2]))

    # Esquina entre el tramo 1 y el tramo 2.
    f = fillet_endpoints(p0, p1, p2, fillet)
    if f is not None:
        pts.append((t("Start of fillet before kink 1"), f[0][0], f[0][1], "fillet", f[2]))
    pts.append((t("Kink 1 (theoretical corner)"), p1[0], p1[1], "kink", None))
    if f is not None:
        pts.append((t("End of fillet after kink 1"), f[1][0], f[1][1], "fillet", f[2]))

    # Esquina entre el tramo 2 y el tramo 3.
    f = fillet_endpoints(p1, p2, p3, fillet)
    if f is not None:
        pts.append((t("Start of fillet before kink 2"), f[0][0], f[0][1], "fillet", f[2]))
    pts.append((t("Kink 2 (theoretical corner)"), p2[0], p2[1], "kink", None))
    if f is not None:
        pts.append((t("End of fillet after kink 2"), f[1][0], f[1][1], "fillet", f[2]))

    # Esquina superior (final de la rampa sobre la calle).
    f = fillet_endpoints(p2, p3, post, fillet)
    if f is not None:
        pts.append((t("Start of fillet at the top"), f[0][0], f[0][1], "fillet", f[2]))
    pts.append((t("End of the ramp (corner)"), p3[0], p3[1], "kink", None))

    return pts
