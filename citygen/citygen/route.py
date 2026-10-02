import heapq
from math import hypot

from shapely.geometry import LineString, MultiPoint, Point

SNAP_M = 3.0


def _key(point):
    return (round(point[0] / SNAP_M), round(point[1] / SNAP_M))


def build_graph(streets_data, plane, resolved=None):
    nodes, graph = {}, {}
    for street in streets_data:
        ring = plane.forward_ring(street["coords"])
        for i in range(len(ring) - 1):
            a, b = ring[i], ring[i + 1]
            ka, kb = _key(a), _key(b)
            if ka == kb:
                continue
            nodes.setdefault(ka, a)
            nodes.setdefault(kb, b)
            cost = hypot(b[0] - a[0], b[1] - a[1])
            graph.setdefault(ka, []).append((kb, cost, street["name"]))
            graph.setdefault(kb, []).append((ka, cost, street["name"]))
    return nodes, graph


def nearest_node(nodes, target):
    return min(nodes, key=lambda k: hypot(nodes[k][0] - target[0], nodes[k][1] - target[1]))


def shortest_path(graph, nodes, start, goal):
    seen, came, best = set(), {}, {start: 0.0}
    queue = [(0.0, start)]
    while queue:
        cost, node = heapq.heappop(queue)
        if node in seen:
            continue
        seen.add(node)
        if node == goal:
            break
        for neighbour, step, name in graph.get(node, []):
            candidate = cost + step
            if candidate < best.get(neighbour, float("inf")):
                best[neighbour] = candidate
                came[neighbour] = (node, name)
                heapq.heappush(queue, (candidate, neighbour))
    if goal not in best:
        return None, None, []
    path, streets_used, cursor = [], [], goal
    while cursor != start:
        path.append(nodes[cursor])
        previous, name = came[cursor]
        streets_used.append(name)
        cursor = previous
    path.append(nodes[start])
    path.reverse()
    streets_used.reverse()
    ordered = []
    for name in streets_used:
        if name and (not ordered or ordered[-1] != name):
            ordered.append(name)
    return path, best[goal], ordered


def town_hull(chunks):
    return MultiPoint(
        [p for _, polygon in chunks for p in polygon.exterior.coords]
    ).convex_hull


def entrances(streets_data, plane, hull, resolved, kind_of):
    found = []
    boundary = hull.boundary
    for street in streets_data:
        if kind_of(street, resolved) != "avenue":
            continue
        line = LineString(plane.forward_ring(street["coords"]))
        crossing = line.intersection(boundary)
        if crossing.is_empty:
            continue
        points = [crossing] if crossing.geom_type == "Point" else list(getattr(crossing, "geoms", []))
        for point in points:
            if point.geom_type != "Point":
                continue
            found.append({"name": street["name"], "local": (point.x, point.y)})
    unique = []
    for item in found:
        if all(hypot(item["local"][0] - u["local"][0], item["local"][1] - u["local"][1]) > 40 for u in unique):
            unique.append(item)
    return unique


def blocks_touched(path, chunks, reach=25.0):
    corridor = LineString(path).buffer(reach)
    return [cid for cid, polygon in chunks if polygon.intersects(corridor)]
