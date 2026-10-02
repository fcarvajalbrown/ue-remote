import struct
import zlib
from math import cos, pi, sin

import numpy as np


def canvas(size, background=(255, 255, 255)):
    image = np.zeros((size, size, 3), dtype=np.uint8)
    image[:, :] = background
    return image


class View:
    def __init__(self, cx, cy, span, size):
        self.cx, self.cy, self.span, self.size = cx, cy, span, size
        self.scale = size / span

    def to_px(self, x, y):
        return (
            (x - self.cx) * self.scale + self.size / 2.0,
            self.size / 2.0 - (y - self.cy) * self.scale,
        )


def draw_line(image, view, a, b, colour, width=1):
    size = image.shape[0]
    x0, y0 = view.to_px(*a)
    x1, y1 = view.to_px(*b)
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    if steps > 20000:
        return
    xs = np.linspace(x0, x1, steps)
    ys = np.linspace(y0, y1, steps)
    for ox in range(-(width // 2), width // 2 + 1):
        for oy in range(-(width // 2), width // 2 + 1):
            px = np.round(xs + ox).astype(int)
            py = np.round(ys + oy).astype(int)
            keep = (px >= 0) & (px < size) & (py >= 0) & (py < size)
            image[py[keep], px[keep]] = colour


def draw_path(image, view, points, colour, width=1, close=False):
    ring = list(points)
    if close and ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    for i in range(len(ring) - 1):
        draw_line(image, view, ring[i], ring[i + 1], colour, width)


def draw_marker(image, view, point, colour, radius=4):
    size = image.shape[0]
    px, py = view.to_px(*point)
    px, py = int(round(px)), int(round(py))
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius:
                x, y = px + dx, py + dy
                if 0 <= x < size and 0 <= y < size:
                    image[y, x] = colour


def _chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def save(image, path):
    height, width, _ = image.shape
    raw = b"".join(b"\x00" + image[row].tobytes() for row in range(height))
    body = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 6))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(body)
    return path


GLYPHS = {
    "A": "0,0 3,10 6,0|1,4 5,4",
    "B": "0,0 0,10 4,10 6,8 6,7 4,5 0,5|4,5 6,3 6,2 4,0 0,0",
    "C": "6,8 4,10 2,10 0,8 0,2 2,0 4,0 6,2",
    "D": "0,0 0,10 4,10 6,8 6,2 4,0 0,0",
    "E": "6,10 0,10 0,0 6,0|0,5 4,5",
    "F": "6,10 0,10 0,0|0,5 4,5",
    "G": "6,8 4,10 2,10 0,8 0,2 2,0 4,0 6,2 6,4 3,4",
    "H": "0,10 0,0|6,10 6,0|0,5 6,5",
    "I": "1,10 5,10|3,10 3,0|1,0 5,0",
    "J": "6,10 6,2 4,0 2,0 0,2",
    "K": "0,10 0,0|6,10 0,4|2,6 6,0",
    "L": "0,10 0,0 6,0",
    "M": "0,0 0,10 3,5 6,10 6,0",
    "N": "0,0 0,10 6,0 6,10",
    "O": "2,10 4,10 6,8 6,2 4,0 2,0 0,2 0,8 2,10",
    "P": "0,0 0,10 4,10 6,8 6,6 4,4 0,4",
    "Q": "2,10 4,10 6,8 6,2 4,0 2,0 0,2 0,8 2,10|4,2 6,0",
    "R": "0,0 0,10 4,10 6,8 6,6 4,4 0,4|3,4 6,0",
    "S": "6,8 4,10 2,10 0,8 0,6 2,5 4,5 6,4 6,2 4,0 2,0 0,2",
    "T": "0,10 6,10|3,10 3,0",
    "U": "0,10 0,2 2,0 4,0 6,2 6,10",
    "V": "0,10 3,0 6,10",
    "W": "0,10 1,0 3,6 5,0 6,10",
    "X": "0,10 6,0|0,0 6,10",
    "Y": "0,10 3,5 6,10|3,5 3,0",
    "Z": "0,10 6,10 0,0 6,0",
    "0": "2,10 4,10 6,8 6,2 4,0 2,0 0,2 0,8 2,10|1,2 5,8",
    "1": "1,8 3,10 3,0|1,0 5,0",
    "2": "0,8 2,10 4,10 6,8 6,6 0,0 6,0",
    "3": "0,10 6,10 3,6|3,6 6,4 6,2 4,0 2,0 0,2",
    "4": "5,0 5,10 0,4 6,4",
    "5": "6,10 0,10 0,6 4,6 6,4 6,2 4,0 2,0 0,2",
    "6": "5,10 2,10 0,8 0,2 2,0 4,0 6,2 6,4 4,6 2,6 0,4",
    "7": "0,10 6,10 2,0",
    "8": "2,5 0,7 0,9 2,10 4,10 6,9 6,7 4,5 2,5 0,3 0,1 2,0 4,0 6,1 6,3 4,5",
    "9": "1,0 4,0 6,2 6,8 4,10 2,10 0,8 0,6 2,5 4,5 6,6",
    "-": "1,5 5,5",
    "_": "0,0 6,0",
    ".": "2,0 4,0",
    ",": "3,1 2,-1",
    ":": "3,2 3,3|3,6 3,7",
    "/": "0,0 6,10",
    "(": "4,10 2,7 2,3 4,0",
    ")": "2,10 4,7 4,3 2,0",
    "+": "3,8 3,2|1,5 5,5",
    "'": "3,10 3,7",
    " ": "",
}

_PARSED = {
    ch: [
        [tuple(float(v) for v in pt.split(",")) for pt in run.split(" ") if pt]
        for run in spec.split("|")
        if run
    ]
    for ch, spec in GLYPHS.items()
}

GLYPH_W = 6.0
GLYPH_H = 10.0


def _line_px(image, a, b, colour, width):
    size_y, size_x = image.shape[0], image.shape[1]
    steps = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
    xs = np.linspace(a[0], b[0], steps)
    ys = np.linspace(a[1], b[1], steps)
    for ox in range(width):
        for oy in range(width):
            px = np.round(xs + ox - width // 2).astype(int)
            py = np.round(ys + oy - width // 2).astype(int)
            keep = (px >= 0) & (px < size_x) & (py >= 0) & (py < size_y)
            image[py[keep], px[keep]] = colour


def text_width(text, size, tracking=0.32):
    return len(text) * size * (GLYPH_W / GLYPH_H + tracking)


def fold(text):
    return text.translate(FOLD).upper()


FOLD = str.maketrans({
    "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
    "á": "A", "é": "E", "í": "I", "ó": "O", "ú": "U",
    "Ñ": "N", "ñ": "N", "Ü": "U", "ü": "U",
    "À": "A", "È": "E", "Ì": "I", "Ò": "O", "Ù": "U",
})


def draw_text(image, text, x, y, size, colour, width=2, anchor="left", tracking=0.32, angle=0.0):
    text = text.translate(FOLD)
    scale = size / GLYPH_H
    advance = size * (GLYPH_W / GLYPH_H + tracking)
    total = len(text) * advance
    shift = 0.0
    if anchor == "centre":
        shift = -total / 2.0
    elif anchor == "right":
        shift = -total
    radians = angle * pi / 180.0
    ca, sa = cos(radians), sin(radians)

    def place(dx, dy):
        return (x + dx * ca - dy * sa, y + dx * sa + dy * ca)

    cursor = shift
    for ch in text.upper():
        for run in _PARSED.get(ch, []):
            for i in range(len(run) - 1):
                a = place(cursor + run[i][0] * scale, -run[i][1] * scale)
                b = place(cursor + run[i + 1][0] * scale, -run[i + 1][1] * scale)
                _line_px(image, a, b, colour, width)
        cursor += advance


def draw_disc(image, cx, cy, radius, colour):
    h, w = image.shape[0], image.shape[1]
    x0, x1 = max(0, int(cx - radius) - 1), min(w, int(cx + radius) + 2)
    y0, y1 = max(0, int(cy - radius) - 1), min(h, int(cy + radius) + 2)
    if x0 >= x1 or y0 >= y1:
        return
    ys, xs = np.ogrid[y0:y1, x0:x1]
    image[y0:y1, x0:x1][(xs - cx) ** 2 + (ys - cy) ** 2 <= radius * radius] = colour


def draw_ring(image, cx, cy, radius, thickness, colour):
    h, w = image.shape[0], image.shape[1]
    x0, x1 = max(0, int(cx - radius) - 1), min(w, int(cx + radius) + 2)
    y0, y1 = max(0, int(cy - radius) - 1), min(h, int(cy + radius) + 2)
    if x0 >= x1 or y0 >= y1:
        return
    ys, xs = np.ogrid[y0:y1, x0:x1]
    d2 = (xs - cx) ** 2 + (ys - cy) ** 2
    inner = max(0.0, radius - thickness)
    image[y0:y1, x0:x1][(d2 <= radius * radius) & (d2 >= inner * inner)] = colour


def draw_arrowhead(image, tail, head, size, colour):
    dx, dy = head[0] - tail[0], head[1] - tail[1]
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / length, dy / length
    for spread in (0.42, -0.42):
        bx = head[0] - size * (ux * cos(spread) - uy * sin(spread))
        by = head[1] - size * (uy * cos(spread) + ux * sin(spread))
        _line_px(image, (bx, by), head, colour, 7)


def wrap(text, size, room, tracking=0.32):
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if current and text_width(trial, size, tracking) > room:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def fit_lines(text, base_size, room, max_lines=3, floor=12):
    size = base_size
    while size > floor:
        lines = wrap(text, size, room)
        if len(lines) <= max_lines and all(text_width(l, size) <= room for l in lines):
            return lines, size
        size -= 1
    return wrap(text, floor, room)[:max_lines], floor
