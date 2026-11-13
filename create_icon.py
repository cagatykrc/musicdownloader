"""Çok boyutlu geçerli .ico üretir (Explorer + PyInstaller uyumlu)."""

from __future__ import annotations

import math
import struct
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


def make(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(1, size // 16)
    r = max(2, size // 5)
    d.rounded_rectangle(
        [pad, pad, size - pad - 1, size - pad - 1],
        radius=r,
        fill=(18, 20, 24, 255),
    )
    cx, cy = size / 2, size / 2 - size * 0.04
    w, h = size * 0.52, size * 0.22
    amber = (196, 163, 90, 255)
    amber_dim = (160, 130, 70, 255)
    pts: list[tuple[float, float]] = []
    for i in range(64):
        t = i / 63
        pts.append((cx + (t - 0.5) * w * 2, cy - h * math.sin(math.pi * t) * 0.95))
    for i in range(64):
        t = 1 - i / 63
        pts.append((cx + (t - 0.5) * w * 2, cy + h * math.sin(math.pi * t) * 0.75))
    d.line(pts + [pts[0]], fill=amber, width=max(1, size // 48))
    iris_r = size * 0.11
    d.ellipse(
        [cx - iris_r, cy - iris_r * 0.95, cx + iris_r, cy + iris_r * 0.95],
        outline=amber,
        width=max(1, size // 64),
    )
    pupil = max(1, size * 0.045)
    d.ellipse([cx - pupil, cy - pupil, cx + pupil, cy + pupil], fill=amber)
    hl = max(1, size * 0.018)
    d.ellipse(
        [
            cx - iris_r * 0.35 - hl,
            cy - iris_r * 0.4 - hl,
            cx - iris_r * 0.35 + hl,
            cy - iris_r * 0.4 + hl,
        ],
        fill=(240, 220, 170, 220),
    )
    if size >= 24:
        bar_y = cy + h * 1.55
        bars = [0.35, 0.7, 1.0, 0.55, 0.28]
        bw = max(1, size * 0.035)
        gap = max(1, size * 0.028)
        total = len(bars) * bw + (len(bars) - 1) * gap
        x0 = cx - total / 2
        for i, hmult in enumerate(bars):
            bh = max(1, size * 0.09 * hmult)
            x = x0 + i * (bw + gap)
            d.rounded_rectangle(
                [x, bar_y - bh, x + bw, bar_y],
                radius=max(1, size // 80),
                fill=amber_dim,
            )
    return img


def write_ico(images: list[Image.Image], path: Path) -> None:
    entries: list[tuple[int, int, int]] = []
    blobs: list[bytes] = []
    for im in images:
        bio = BytesIO()
        im.save(bio, format="PNG")
        blob = bio.getvalue()
        w, h = im.size
        entries.append((0 if w >= 256 else w, 0 if h >= 256 else h, len(blob)))
        blobs.append(blob)

    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory = b""
    for w, h, size in entries:
        directory += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, size, offset)
        offset += size
    path.write_bytes(header + directory + b"".join(blobs))


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = [make(s) for s in sizes]
    imgs[-1].save(ASSETS / "icon.png")
    write_ico(imgs, ASSETS / "icon.ico")
    print(f"Wrote {ASSETS / 'icon.ico'} ({(ASSETS / 'icon.ico').stat().st_size} bytes)")


if __name__ == "__main__":
    main()
