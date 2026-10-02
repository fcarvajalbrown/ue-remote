from math import acos, atan2, cos, degrees, hypot, pi, sin, tan

from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

AVENUE_CLASSES = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "motorway_link",
    "trunk_link",
    "primary_link",
    "secondary_link",
    "tertiary_link",
}

RESERVE = {"avenue": 20.0, "residential": 15.0}
CALZADA = {"avenue": 9.0, "residential": 7.0}
KERB_RADIUS = {"avenue": 6.0, "residential": 4.0}
ARC_SEGMENTS = 10
FLAT_CORNER_DEG = 175.0


def classify(highway):
    return "avenue" if highway in AVENUE_CLASSES else "residential"


def resolve_classes(streets_data, plane):
    weight = {}
    for street in streets_data:
        name = street["name"]
        if not name:
            continue
        length = LineString(plane.forward_ring(street["coords"])).length
        bucket = weight.setdefault(name, {"avenue": 0.0, "residential": 0.0})
        bucket[classify(street["highway"])] += length
    resolved = {}
    for name, bucket in weight.items():
        resolved[name] = "avenue" if bucket["avenue"] > bucket["residential"] else "residential"
    return resolved


def kind_of(street, resolved):
    name = street["name"] if street else None
    if name and name in resolved:
        return resolved[name]
    return classify(street["highway"] if street else "residential")


def half_reserve(kind):
    return RESERVE[kind] / 2.0


def vereda(kind):
    return (RESERVE[kind] - CALZADA[kind]) / 2.0


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = hypot(dx, dy)
    if length == 0.0:
        return None
    return (dx / length, dy / length)


def _left(u):
    return (-u[1], u[0])


def _meet(p1, u1, p2, u2):
    denominator = u1[0] * u2[1] - u1[1] * u2[0]
    if abs(denominator) < 1e-9:
        return None
    t = ((p2[0] - p1[0]) * u2[1] - (p2[1] - p1[1]) * u2[0]) / denominator
    return (p1[0] + u1[0] * t, p1[1] + u1[1] * t)


def edge_classes(block, streets, plane, resolved=None):
    if resolved is None:
        resolved = resolve_classes(streets, plane)
    ring = orient(block, sign=1.0)
    points = list(ring.exterior.coords)[:-1]
    lines = [(LineString(plane.forward_ring(s["coords"])), s) for s in streets]
    found = []
    for i, point in enumerate(points):
        nxt = points[(i + 1) % len(points)]
        middle = ((point[0] + nxt[0]) / 2.0, (point[1] + nxt[1]) / 2.0)
        probe = LineString([point, nxt]).interpolate(0.5, normalized=True)
        best, best_distance = None, None
        for line, street in lines:
            distance = line.distance(probe)
            if best_distance is None or distance < best_distance:
                best_distance, best = distance, street
        found.append(
            {
                "index": i,
                "midpoint": middle,
                "street": best["name"] if best else None,
                "highway": best["highway"] if best else "residential",
                "kind": kind_of(best, resolved),
            }
        )
    return ring, points, found


def _outside_strip(a, b, u, n, inset, margin):
    ax = a[0] - u[0] * margin
    ay = a[1] - u[1] * margin
    bx = b[0] + u[0] * margin
    by = b[1] + u[1] * margin
    deep = margin + inset
    return Polygon(
        [
            (ax - n[0] * deep, ay - n[1] * deep),
            (bx - n[0] * deep, by - n[1] * deep),
            (bx + n[0] * inset, by + n[1] * inset),
            (ax + n[0] * inset, ay + n[1] * inset),
        ]
    )


def offset_inward(points, insets, block=None):
    count = len(points)
    if block is None:
        block = Polygon(points)
    if not block.is_valid:
        block = block.buffer(0)
    if block.is_empty or block.geom_type != "Polygon":
        return None

    strips = []
    for i in range(count):
        a, b = points[i], points[(i + 1) % count]
        u = _unit(a, b)
        if u is None:
            continue
        n = _left(u)
        margin = max(insets[i], insets[(i + 1) % count], insets[i - 1]) * 1.5
        strips.append(_outside_strip(a, b, u, n, insets[i], margin))

    if not strips:
        return None
    result = block.difference(unary_union(strips))
    if result.is_empty:
        return None
    if result.geom_type == "MultiPolygon":
        result = max(result.geoms, key=lambda g: g.area)
    if result.geom_type != "Polygon" or result.area <= 0:
        return None
    return result


def _fallback(block, insets):
    shrunk = block.buffer(-sum(insets) / len(insets))
    if shrunk.is_empty or shrunk.geom_type != "Polygon":
        return None
    return shrunk


def property_line(block, streets, plane, resolved=None):
    ring, points, classes = edge_classes(block, streets, plane, resolved)
    insets = [half_reserve(edge["kind"]) for edge in classes]
    result = offset_inward(points, insets, ring)
    if result is None:
        result = _fallback(ring, insets)
        print(f"  WARNING: property line fell back to uniform buffer")
    return result, classes


def _edge_radius(a, b, points, classes):
    direction = _unit(a, b)
    if direction is None:
        return KERB_RADIUS["residential"]
    middle = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    best, score = None, None
    for edge in classes:
        i = edge["index"]
        other = _unit(points[i], points[(i + 1) % len(points)])
        if other is None:
            continue
        alignment = abs(direction[0] * other[0] + direction[1] * other[1])
        gap = hypot(middle[0] - edge["midpoint"][0], middle[1] - edge["midpoint"][1])
        rating = alignment * 1000.0 - gap
        if score is None or rating > score:
            score, best = rating, edge
    return KERB_RADIUS[best["kind"]] if best else KERB_RADIUS["residential"]


def _fillet(ring_points, radius_at, segments=ARC_SEGMENTS):
    count = len(ring_points)
    out = []
    for i in range(count):
        a = ring_points[i - 1]
        v = ring_points[i]
        b = ring_points[(i + 1) % count]
        u1, u2 = _unit(v, a), _unit(v, b)
        if u1 is None or u2 is None:
            out.append(v)
            continue
        if (a[0] - v[0]) * (b[1] - v[1]) - (a[1] - v[1]) * (b[0] - v[0]) <= 0:
            out.append(v)
            continue
        cosine = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        theta = acos(cosine)
        if degrees(theta) > FLAT_CORNER_DEG or theta < 1e-6:
            out.append(v)
            continue
        radius = radius_at(i)
        tangent = radius / tan(theta / 2.0)
        limit = 0.45 * min(hypot(*(a[0] - v[0], a[1] - v[1])), hypot(*(b[0] - v[0], b[1] - v[1])))
        if tangent > limit:
            tangent = limit
            radius = tangent * tan(theta / 2.0)
        if radius <= 0.05:
            out.append(v)
            continue
        bisector = _unit((0.0, 0.0), (u1[0] + u2[0], u1[1] + u2[1]))
        if bisector is None:
            out.append(v)
            continue
        centre = (
            v[0] + bisector[0] * radius / sin(theta / 2.0),
            v[1] + bisector[1] * radius / sin(theta / 2.0),
        )
        start = atan2(v[1] + u1[1] * tangent - centre[1], v[0] + u1[0] * tangent - centre[0])
        end = atan2(v[1] + u2[1] * tangent - centre[1], v[0] + u2[0] * tangent - centre[0])
        sweep = (end - start + pi) % (2 * pi) - pi
        for step in range(segments + 1):
            angle = start + sweep * step / segments
            out.append((centre[0] + radius * cos(angle), centre[1] + radius * sin(angle)))
    return out


def kerb_line(block, streets, plane, resolved=None, rounded=True):
    ring, points, classes = edge_classes(block, streets, plane, resolved)
    insets = [half_reserve(edge["kind"]) - vereda(edge["kind"]) for edge in classes]
    result = offset_inward(points, insets, ring)
    if result is None:
        result = _fallback(ring, insets)
    if result is None or not rounded:
        return result

    kerb_points = list(result.exterior.coords)[:-1]

    def radius_at(index):
        previous = kerb_points[index - 1]
        current = kerb_points[index]
        following = kerb_points[(index + 1) % len(kerb_points)]
        return max(
            _edge_radius(previous, current, points, classes),
            _edge_radius(current, following, points, classes),
        )

    filleted = Polygon(_fillet(kerb_points, radius_at))
    if not filleted.is_valid:
        filleted = filleted.buffer(0)
    if filleted.is_empty or filleted.geom_type != "Polygon":
        return result
    return filleted
