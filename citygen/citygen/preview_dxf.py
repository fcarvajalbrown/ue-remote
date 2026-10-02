import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from citygen import preview

COLOURS = {"EDIFICIO_OSM": (40, 40, 40), "EDIFICIO_MS": (200, 90, 40), "SOLERA": (120, 160, 200), "EJE_CALLE": (190, 190, 190), "EJE_AVENIDA": (220, 120, 120)}


def polylines(path):
    pairs = Path(path).read_text(encoding="ascii", errors="replace").split("\n")
    pairs = list(zip(pairs[0::2], pairs[1::2]))
    layer, closed, points, inside, vertex = None, False, [], False, False
    for code, value in pairs:
        code = code.strip()
        if code == "0":
            vertex = value == "VERTEX"
            if value == "POLYLINE":
                layer, closed, points, inside = None, False, [], True
            elif value == "SEQEND" and inside:
                yield layer, closed, points
                inside = False
        elif inside and not vertex and code == "8" and layer is None:
            layer = value
        elif inside and not vertex and code == "70":
            closed = int(value) & 1 == 1
        elif vertex and code == "10":
            points.append([float(value), None])
        elif vertex and code == "20" and points and points[-1][1] is None:
            points[-1][1] = float(value)


def main():
    parser = argparse.ArgumentParser(description="Render chosen layers of an R12 DXF to PNG.")
    parser.add_argument("dxf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--centre", type=float, nargs=2, default=(0.0, 0.0))
    parser.add_argument("--span", type=float, default=900.0)
    parser.add_argument("--size", type=int, default=1600)
    args = parser.parse_args()

    image = preview.canvas(args.size)
    view = preview.View(args.centre[0], args.centre[1], args.span, args.size)
    counts = {}
    for layer, closed, points in polylines(args.dxf):
        key = next((name for name in COLOURS if layer.startswith(name)), None)
        if key is None or len(points) < 2:
            continue
        counts[key] = counts.get(key, 0) + 1
        preview.draw_path(image, view, [tuple(point) for point in points], COLOURS[key], 1, closed)
    preview.save(image, args.out)
    print(counts, "->", args.out)


if __name__ == "__main__":
    main()
