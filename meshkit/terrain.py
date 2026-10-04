import math

import numpy as np

import meshkit as mk

PATH_SAMPLE_METRES = 1.0
PATH_LIFT_METRES = 0.08


class Ground:
    def __init__(self, world):
        self.spec = world["terrain"]
        self.pads = [(b["at"][0], b["at"][1], b["pad"]) for b in world["buildings"]]
        self.pads += [(p["at"][0], p["at"][1], p["pad"]) for p in world["props"]]
        self.axis = None
        self.grid = None

    @staticmethod
    def smoothstep(t):
        t = min(max(t, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    def raw(self, x, y):
        s = self.spec
        wave, ripple = s["wave"], s["ripple"]
        return s["slope"] * y + wave[0] * math.sin(x / wave[1]) * math.cos(y / wave[2]) + ripple[0] * math.sin(x / ripple[1] + y / ripple[2])

    def height(self, x, y):
        value = self.raw(x, y)
        for cx, cy, radius in self.pads:
            weight = 1.0 - self.smoothstep((math.hypot(x - cx, y - cy) - radius) / self.spec["pad_blend"])
            if weight > 0:
                value = value * (1 - weight) + self.raw(cx, cy) * weight
        return value

    def surface_grid(self):
        if self.grid is None:
            self.axis = axis_coordinates(self.spec)
            self.grid = np.array([[self.height(x, y) for x in self.axis] for y in self.axis])
        return self.axis, self.grid

    def mesh_height(self, x, y):
        axis, grid = self.surface_grid()
        col = min(max(int(np.searchsorted(axis, x)) - 1, 0), len(axis) - 2)
        row = min(max(int(np.searchsorted(axis, y)) - 1, 0), len(axis) - 2)
        u = (x - axis[col]) / (axis[col + 1] - axis[col])
        v = (y - axis[row]) / (axis[row + 1] - axis[row])
        h00, h10, h11, h01 = grid[row, col], grid[row, col + 1], grid[row + 1, col + 1], grid[row + 1, col]
        if u >= v:
            return float(h00 + u * (h10 - h00) + v * (h11 - h10))
        return float(h00 + u * (h11 - h01) + v * (h01 - h00))

    def pad_height(self, x, y):
        return self.raw(x, y)


def axis_coordinates(spec):
    positive = [0.0]
    while positive[-1] < spec["near_limit"]:
        positive.append(positive[-1] + spec["near_cell"])
    step = spec["near_cell"]
    while positive[-1] < spec["half_extent"]:
        step *= spec["growth"]
        positive.append(positive[-1] + step)
    positive[-1] = spec["half_extent"]
    return np.array(sorted({-v for v in positive} | set(positive)))


def terrain_mesh(ground):
    axis, heights = ground.surface_grid()
    size = len(axis)
    triangles = []
    for row in range(size - 1):
        for col in range(size - 1):
            p00 = (axis[col], axis[row], heights[row, col])
            p10 = (axis[col + 1], axis[row], heights[row, col + 1])
            p11 = (axis[col + 1], axis[row + 1], heights[row + 1, col + 1])
            p01 = (axis[col], axis[row + 1], heights[row + 1, col])
            triangles += [(p00, p10, p11), (p00, p11, p01)]
    return mk.Mesh().add(ground.spec.get("material", "grass"), np.array(triangles))


def ribbon_mesh(ground, points, width, lift=PATH_LIFT_METRES):
    samples = []
    for start, end in zip(points[:-1], points[1:]):
        count = max(int(math.dist(start, end) / PATH_SAMPLE_METRES), 1)
        samples += [(start[0] + (end[0] - start[0]) * i / count, start[1] + (end[1] - start[1]) * i / count) for i in range(count)]
    samples.append(tuple(points[-1]))
    rows = []
    for index, (x, y) in enumerate(samples):
        ahead, behind = samples[min(index + 1, len(samples) - 1)], samples[max(index - 1, 0)]
        dx, dy = ahead[0] - behind[0], ahead[1] - behind[1]
        norm = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / norm * width / 2, dx / norm * width / 2
        row = []
        for sx, sy in ((x + nx, y + ny), (x, y), (x - nx, y - ny)):
            row.append((sx, sy, ground.mesh_height(sx, sy) + lift))
        rows.append(row)
    triangles = []
    for r0, r1 in zip(rows[:-1], rows[1:]):
        for side in (0, 1):
            a, b, c, d = r0[side + 1], r1[side + 1], r1[side], r0[side]
            triangles += [(a, b, c), (a, c, d)]
    return np.array(triangles)


def paths_mesh(ground, world):
    mesh = mk.Mesh()
    for path in world["paths"]:
        mesh.add(path.get("material", "dirt"), ribbon_mesh(ground, path["points"], path["width"]))
    return mesh
