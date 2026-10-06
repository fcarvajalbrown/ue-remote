from collections import Counter, defaultdict

import ezdxf
from ezdxf import bbox

UNIT_NAMES = {
    0: "unitless", 1: "inches", 2: "feet", 3: "miles", 4: "millimetres", 5: "centimetres",
    6: "metres", 7: "kilometres", 8: "microinches", 9: "mils", 10: "yards",
}
TOP_LAYERS = 25
TOP_TEXTS = 12


def is_closed(entity):
    if entity.dxftype() == "LWPOLYLINE":
        return bool(entity.closed)
    if entity.dxftype() == "POLYLINE":
        return bool(entity.is_closed)
    return entity.dxftype() in ("CIRCLE", "ELLIPSE", "HATCH", "SOLID")


def collect(document):
    layers = defaultdict(Counter)
    closed = Counter()
    texts = []
    for entity in document.modelspace():
        kind = entity.dxftype()
        layer = entity.dxf.layer
        layers[layer][kind] += 1
        if is_closed(entity):
            closed[layer] += 1
        if kind in ("TEXT", "MTEXT") and len(texts) < 400:
            texts.append(entity.dxf.text if kind == "TEXT" else entity.text)
    return layers, closed, texts


def extents(document):
    box = bbox.extents(document.modelspace(), fast=True)
    if not box.has_data:
        return None
    return box.extmin, box.extmax


def layer_extents(document):
    boxes = {}
    for entity in document.modelspace():
        box = bbox.extents([entity], fast=True)
        if not box.has_data:
            continue
        name = entity.dxf.layer
        low, high = box.extmin, box.extmax
        if name not in boxes:
            boxes[name] = [low.x, low.y, high.x, high.y]
        else:
            current = boxes[name]
            boxes[name] = [min(current[0], low.x), min(current[1], low.y), max(current[2], high.x), max(current[3], high.y)]
    return boxes


def extents_report(path):
    document = ezdxf.readfile(path)
    lines = ["layer extents (min x, min y, max x, max y, width x height):"]
    for name, (x0, y0, x1, y1) in sorted(layer_extents(document).items()):
        lines.append(f"  {name}: {x0:.1f} {y0:.1f} {x1:.1f} {y1:.1f}  {x1 - x0:.1f} x {y1 - y0:.1f}")
    return "\n".join(lines)


def summary(path):
    document = ezdxf.readfile(path)
    layers, closed, texts = collect(document)
    unit_code = document.header.get("$INSUNITS", 0)
    lines = [f"file: {path}", f"dxf version: {document.dxfversion}", f"units: {UNIT_NAMES.get(unit_code, unit_code)}"]
    box = extents(document)
    if box:
        low, high = box
        lines.append(f"extents: x {low.x:.1f}..{high.x:.1f}  y {low.y:.1f}..{high.y:.1f}  z {low.z:.1f}..{high.z:.1f}")
        lines.append(f"size: {high.x - low.x:.1f} x {high.y - low.y:.1f}")
    ranked = sorted(layers.items(), key=lambda item: -sum(item[1].values()))
    lines.append(f"layers: {len(layers)} (top {min(TOP_LAYERS, len(ranked))} by entity count)")
    for name, counter in ranked[:TOP_LAYERS]:
        kinds = ", ".join(f"{kind} {count}" for kind, count in counter.most_common(4))
        lines.append(f"  {name}: {sum(counter.values())} [{kinds}] closed {closed[name]}")
    cleaned = []
    for text in texts:
        value = " ".join(str(text).split())
        if value and value not in cleaned:
            cleaned.append(value)
    if cleaned:
        lines.append("texts: " + " | ".join(cleaned[:TOP_TEXTS]))
    return "\n".join(lines)
