from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "src-tauri" / "icons"
PNG_PATH = ICON_DIR / "icon-1024.png"
ICO_PATH = ICON_DIR / "icon.ico"
ICO_SIZES = (256, 128, 64, 48, 32, 16)


def clamp(value: float) -> int:
    return max(0, min(255, int(round(value))))


def mix(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def blend(pixels: bytearray, size: int, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if x < 0 or y < 0 or x >= size or y >= size:
        return
    index = (y * size + x) * 4
    sr, sg, sb, sa = color
    alpha = sa / 255.0
    inv = 1.0 - alpha
    pixels[index] = clamp(sr * alpha + pixels[index] * inv)
    pixels[index + 1] = clamp(sg * alpha + pixels[index + 1] * inv)
    pixels[index + 2] = clamp(sb * alpha + pixels[index + 2] * inv)
    pixels[index + 3] = 255


def draw_circle(
    pixels: bytearray,
    size: int,
    cx: float,
    cy: float,
    radius: float,
    color: tuple[int, int, int, int],
    softness: float = 1.6,
) -> None:
    min_x = max(0, int(cx - radius - softness - 1))
    max_x = min(size - 1, int(cx + radius + softness + 1))
    min_y = max(0, int(cy - radius - softness - 1))
    max_y = min(size - 1, int(cy + radius + softness + 1))
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            distance = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if distance <= radius + softness:
                falloff = max(0.0, min(1.0, (radius + softness - distance) / softness))
                alpha = int(color[3] * falloff)
                if alpha:
                    blend(pixels, size, x, y, (color[0], color[1], color[2], alpha))


def draw_line(
    pixels: bytearray,
    size: int,
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    color: tuple[int, int, int, int],
    glow: float = 0.0,
) -> None:
    x1, y1 = start
    x2, y2 = end
    length = max(1.0, math.hypot(x2 - x1, y2 - y1))
    steps = max(1, int(length / max(1.0, width * 0.45)))
    if glow:
        for index in range(steps + 1):
            t = index / steps
            x = mix(x1, x2, t)
            y = mix(y1, y2, t)
            draw_circle(pixels, size, x, y, width * 0.5 + glow, (color[0], color[1], color[2], 32), glow)
    for index in range(steps + 1):
        t = index / steps
        x = mix(x1, x2, t)
        y = mix(y1, y2, t)
        draw_circle(pixels, size, x, y, width * 0.5, color, max(1.0, width * 0.35))


def point_in_poly(x: float, y: float, points: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(points) - 1
    for i, point in enumerate(points):
        xi, yi = point
        xj, yj = points[j]
        crosses = (yi > y) != (yj > y)
        if crosses:
            x_intersect = (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
            if x < x_intersect:
                inside = not inside
        j = i
    return inside


def draw_polygon(
    pixels: bytearray,
    size: int,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
) -> None:
    scaled = [(x * size, y * size) for x, y in points]
    min_x = max(0, int(min(x for x, _ in scaled)))
    max_x = min(size - 1, int(max(x for x, _ in scaled)) + 1)
    min_y = max(0, int(min(y for _, y in scaled)))
    max_y = min(size - 1, int(max(y for _, y in scaled)) + 1)
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            if point_in_poly(x + 0.5, y + 0.5, scaled):
                blend(pixels, size, x, y, color)


def draw_polyline(
    pixels: bytearray,
    size: int,
    points: list[tuple[float, float]],
    width: float,
    color: tuple[int, int, int, int],
    glow: float = 0.0,
) -> None:
    scaled = [(x * size, y * size) for x, y in points]
    for start, end in zip(scaled, scaled[1:]):
        draw_line(pixels, size, start, end, width, color, glow)


def draw_rounded_border(pixels: bytearray, size: int) -> None:
    radius = size * 0.18
    margin = size * 0.035
    thickness = max(2.0, size * 0.012)
    for y in range(size):
        for x in range(size):
            px = x + 0.5
            py = y + 0.5
            qx = abs(px - size / 2) - (size / 2 - margin - radius)
            qy = abs(py - size / 2) - (size / 2 - margin - radius)
            outside = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius
            distance = abs(outside)
            if -thickness * 0.6 <= outside <= thickness:
                alpha = max(0, 150 - int(distance * 30))
                blend(pixels, size, x, y, (132, 238, 255, alpha))


def make_icon(size: int) -> bytearray:
    pixels = bytearray(size * size * 4)
    center_x = size * 0.48
    center_y = size * 0.46

    for y in range(size):
        for x in range(size):
            nx = x / max(1, size - 1)
            ny = y / max(1, size - 1)
            radial = math.hypot(nx - 0.52, ny - 0.45)
            diagonal = max(0.0, 1.0 - abs((nx - ny) - 0.03) * 2.4)
            nebula = max(0.0, 1.0 - radial * 1.45)
            r = 7 + nebula * 16 + diagonal * 16
            g = 14 + nebula * 32 + diagonal * 26
            b = 28 + nebula * 70 + diagonal * 54
            index = (y * size + x) * 4
            pixels[index:index + 4] = bytes((clamp(r), clamp(g), clamp(b), 255))

    # Deterministic star field.
    star_count = max(18, size // 3)
    for i in range(star_count):
        x = ((i * 73 + 29) % 997) / 997 * size
        y = ((i * 151 + 47) % 991) / 991 * size
        if 0.18 * size < x < 0.84 * size and 0.24 * size < y < 0.82 * size:
            continue
        radius = max(0.7, size * (0.0015 + (i % 3) * 0.0008))
        draw_circle(pixels, size, x, y, radius, (170, 235, 255, 120), radius)

    draw_rounded_border(pixels, size)

    # Open-book silhouette.
    left_page = [(0.18, 0.58), (0.48, 0.38), (0.50, 0.78), (0.29, 0.86), (0.17, 0.72)]
    right_page = [(0.52, 0.38), (0.82, 0.58), (0.83, 0.72), (0.71, 0.86), (0.50, 0.78)]
    draw_polygon(pixels, size, left_page, (214, 244, 255, 76))
    draw_polygon(pixels, size, right_page, (196, 236, 255, 68))
    draw_polyline(pixels, size, left_page + [left_page[0]], max(1.4, size * 0.006), (149, 231, 255, 150), size * 0.01)
    draw_polyline(pixels, size, right_page + [right_page[0]], max(1.4, size * 0.006), (121, 255, 217, 145), size * 0.01)
    draw_line(
        pixels,
        size,
        (center_x, size * 0.39),
        (center_x + size * 0.01, size * 0.79),
        max(1.5, size * 0.008),
        (217, 252, 255, 180),
        size * 0.015,
    )

    # Page ribs.
    for offset in (-0.10, -0.04, 0.05, 0.12):
        draw_line(
            pixels,
            size,
            (size * (0.50 + offset * 0.35), size * 0.47),
            (size * (0.50 + offset), size * 0.78),
            max(1.0, size * 0.0025),
            (165, 234, 255, 65),
            0,
        )

    # Orbit arc through the icon.
    arc_points: list[tuple[float, float]] = []
    for i in range(58):
        t = -0.18 + i / 57 * 1.36
        angle = math.pi * (0.96 + t)
        x = 0.50 + 0.40 * math.cos(angle)
        y = 0.56 + 0.18 * math.sin(angle) + 0.045 * t
        arc_points.append((x, y))
    draw_polyline(pixels, size, arc_points, max(1.6, size * 0.008), (77, 236, 255, 190), size * 0.022)

    # Story graph constellation.
    nodes = [
        (0.50, 0.31, 0.020),
        (0.36, 0.44, 0.014),
        (0.64, 0.45, 0.014),
        (0.30, 0.62, 0.012),
        (0.50, 0.60, 0.016),
        (0.70, 0.63, 0.012),
        (0.41, 0.73, 0.010),
        (0.60, 0.74, 0.010),
    ]
    edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 4), (2, 5), (4, 6), (4, 7), (5, 7)]
    for a, b in edges:
        start = (nodes[a][0] * size, nodes[a][1] * size)
        end = (nodes[b][0] * size, nodes[b][1] * size)
        draw_line(pixels, size, start, end, max(1.0, size * 0.004), (101, 255, 226, 155), size * 0.012)

    for index, (x, y, radius) in enumerate(nodes):
        glow_color = (71, 239, 255, 52) if index != 0 else (146, 255, 236, 70)
        core_color = (213, 255, 255, 235) if index == 0 else (128, 251, 236, 220)
        draw_circle(pixels, size, x * size, y * size, radius * size * 2.4, glow_color, radius * size * 1.8)
        draw_circle(pixels, size, x * size, y * size, max(1.2, radius * size), core_color, max(1.0, radius * size * 0.45))

    # Lower silver-blue base shadow.
    shadow_points = [(0.24, 0.79), (0.50, 0.88), (0.76, 0.79), (0.63, 0.90), (0.37, 0.90)]
    draw_polygon(pixels, size, shadow_points, (48, 101, 130, 78))
    draw_polyline(pixels, size, shadow_points + [shadow_points[0]], max(1.0, size * 0.004), (152, 235, 255, 62), 0)

    return pixels


def png_bytes(size: int, pixels: bytearray) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    rows = bytearray()
    stride = size * 4
    for y in range(size):
        rows.append(0)
        start = y * stride
        rows.extend(pixels[start:start + stride])

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(bytes(rows), 9)),
            chunk(b"IEND", b""),
        ]
    )


def write_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    payload = bytearray()
    for size, data in images:
        width = 0 if size >= 256 else size
        entries.extend(
            struct.pack("<BBBBHHII", width, width, 0, 0, 1, 32, len(data), offset)
        )
        payload.extend(data)
        offset += len(data)
    return header + bytes(entries) + bytes(payload)


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    source_pixels = make_icon(1024)
    PNG_PATH.write_bytes(png_bytes(1024, source_pixels))

    ico_images = []
    for size in ICO_SIZES:
        ico_images.append((size, png_bytes(size, make_icon(size))))
    ICO_PATH.write_bytes(write_ico(ico_images))
    print(f"Wrote {PNG_PATH}")
    print(f"Wrote {ICO_PATH}")


if __name__ == "__main__":
    main()
