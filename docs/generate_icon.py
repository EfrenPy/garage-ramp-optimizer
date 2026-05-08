"""Generate a simple Windows .ico (and .png) for rampa.exe.

Renders a stylised garage ramp: a green smooth curve from the lower
left to the upper right of a rounded square, with light "garage floor"
and "street" segments at the corners.  Matplotlib only — no Pillow
dependency.

Run from the project root:

    python docs/generate_icon.py

Outputs:
    docs/icon.png   (256x256 master image)
    docs/icon.ico   (multi-size Windows icon: 16, 32, 48, 64, 128, 256)
"""

from __future__ import annotations

import io
import math
import struct
import zlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
PNG_PATH = HERE / "icon.png"
ICO_PATH = HERE / "icon.ico"


def _smooth_ramp(n: int = 200):
    """A small smoothstep-like profile from (0, 0) to (1, 1)."""
    t = np.linspace(0.0, 1.0, n)
    # 5-th order smoothstep, gentle ends, steep middle.
    y = 6 * t**5 - 15 * t**4 + 10 * t**3
    return t, y


def _render_png(size: int) -> bytes:
    """Render the icon at *size*x*size* pixels and return PNG bytes."""
    fig = plt.figure(
        figsize=(size / 100, size / 100),
        dpi=100,
        facecolor="white",
    )
    ax = fig.add_subplot(111)

    # Outer rounded background (a darker frame).
    pad = 0.04
    ax.add_patch(plt.Rectangle(
        (pad, pad), 1 - 2 * pad, 1 - 2 * pad,
        facecolor="#0d47a1", edgecolor="none",
    ))
    # Inner cream area where the slope sits.
    inner_pad = pad + 0.05
    ax.add_patch(plt.Rectangle(
        (inner_pad, inner_pad),
        1 - 2 * inner_pad, 1 - 2 * inner_pad,
        facecolor="#f5f5f5", edgecolor="none",
    ))

    # Garage floor (lower left flat) and street (upper right flat).
    flat_color = "#222"
    floor_y = inner_pad + 0.08
    street_y = 1 - inner_pad - 0.08
    ax.plot(
        [inner_pad + 0.02, inner_pad + 0.18],
        [floor_y, floor_y],
        color=flat_color, linewidth=max(2, size / 80),
    )
    ax.plot(
        [1 - inner_pad - 0.18, 1 - inner_pad - 0.02],
        [street_y, street_y],
        color=flat_color, linewidth=max(2, size / 80),
    )

    # The smooth ramp curve, tucked between the two flats.
    t, y = _smooth_ramp()
    x_lo, x_hi = inner_pad + 0.18, 1 - inner_pad - 0.18
    y_lo, y_hi = floor_y, street_y
    xs = x_lo + t * (x_hi - x_lo)
    ys = y_lo + y * (y_hi - y_lo)
    ax.plot(xs, ys, color="#2e7d32", linewidth=max(3, size / 50))

    # Tiny "car wheels" hint to make it obvious this is a ramp for a
    # vehicle (two small dots near the top of the curve).
    car_x = x_lo + 0.78 * (x_hi - x_lo)
    car_y = y_lo + (6 * 0.78**5 - 15 * 0.78**4 + 10 * 0.78**3) * (y_hi - y_lo)
    wheel_r = 0.025
    for dx in (-0.05, 0.05):
        ax.add_patch(plt.Circle(
            (car_x + dx, car_y + 0.025), wheel_r,
            facecolor="#0d47a1", edgecolor="none",
        ))

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """Read the IHDR chunk to get (width, height)."""
    # PNG header is 8 bytes; IHDR chunk starts at offset 8.
    width = int.from_bytes(png_bytes[16:20], "big")
    height = int.from_bytes(png_bytes[20:24], "big")
    return width, height


def _build_ico(images: list[bytes]) -> bytes:
    """Pack a list of PNG byte strings into a single .ico file.

    Modern Windows accepts PNG-encoded entries inside .ico, so we
    avoid having to write the legacy DIB format ourselves.
    """
    if not images:
        raise ValueError("at least one image is required")

    # ICONDIR header (6 bytes).
    out = bytearray()
    out += struct.pack("<HHH", 0, 1, len(images))  # reserved, type=icon, count

    # ICONDIRENTRY blocks (16 bytes each), then the image bytes.
    image_offset = 6 + 16 * len(images)
    entries = bytearray()
    payload = bytearray()
    for png in images:
        w, h = _png_dimensions(png)
        # ICONDIRENTRY: width, height, color count, reserved, planes,
        # bitcount, bytes-in-resource, image-offset.
        entries += struct.pack(
            "<BBBBHHII",
            0 if w >= 256 else w,    # 0 means 256
            0 if h >= 256 else h,
            0,    # color palette count
            0,    # reserved
            1,    # color planes
            32,   # bits per pixel
            len(png),
            image_offset,
        )
        payload += png
        image_offset += len(png)
    out += entries
    out += payload
    return bytes(out)


def main() -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    print(f"Rendering {len(sizes)} sizes ...")
    pngs = []
    for s in sizes:
        png = _render_png(s)
        pngs.append(png)
        if s == 256:
            PNG_PATH.write_bytes(png)
            print(f"  saved master PNG: {PNG_PATH}")

    ICO_PATH.write_bytes(_build_ico(pngs))
    print(f"  saved Windows icon: {ICO_PATH}  ({ICO_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
