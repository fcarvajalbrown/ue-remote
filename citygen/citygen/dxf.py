COLOUR_DEFAULT = 7

COLOUR_BY_PREFIX = (
    ("LINEA_OFICIAL", 3),
    ("SOLERA", 4),
    ("EJE_AVENIDA", 1),
    ("EJE_CALLE", 8),
    ("BLOCK_CENTRE", 253),
    ("BLOCK", 8),
    ("LOT", 251),
    ("STREET", 5),
    ("EDIFICIO_OSM", 30),
    ("EDIFICIO_MS", 140),
)


def _pair(code, value):
    return f"{code}\n{value}\n"


def _header(extents):
    xmin, ymin, xmax, ymax = extents
    return (
        _pair(0, "SECTION")
        + _pair(2, "HEADER")
        + _pair(9, "$ACADVER")
        + _pair(1, "AC1009")
        + _pair(9, "$INSUNITS")
        + _pair(70, 6)
        + _pair(9, "$EXTMIN")
        + _pair(10, f"{xmin:.4f}")
        + _pair(20, f"{ymin:.4f}")
        + _pair(30, "0.0")
        + _pair(9, "$EXTMAX")
        + _pair(10, f"{xmax:.4f}")
        + _pair(20, f"{ymax:.4f}")
        + _pair(30, "0.0")
        + _pair(0, "ENDSEC")
    )


def _tables(layers):
    body = (
        _pair(0, "SECTION")
        + _pair(2, "TABLES")
        + _pair(0, "TABLE")
        + _pair(2, "LTYPE")
        + _pair(70, 1)
        + _pair(0, "LTYPE")
        + _pair(2, "CONTINUOUS")
        + _pair(70, 64)
        + _pair(3, "Solid line")
        + _pair(72, 65)
        + _pair(73, 0)
        + _pair(40, "0.0")
        + _pair(0, "ENDTAB")
        + _pair(0, "TABLE")
        + _pair(2, "LAYER")
        + _pair(70, len(layers))
    )
    for name, colour in layers:
        body += (
            _pair(0, "LAYER")
            + _pair(2, name)
            + _pair(70, 0)
            + _pair(62, colour)
            + _pair(6, "CONTINUOUS")
        )
    return body + _pair(0, "ENDTAB") + _pair(0, "ENDSEC")


def _polyline(layer, points, closed=True):
    body = (
        _pair(0, "POLYLINE")
        + _pair(8, layer)
        + _pair(66, 1)
        + _pair(70, 1 if closed else 0)
        + _pair(10, "0.0")
        + _pair(20, "0.0")
        + _pair(30, "0.0")
    )
    for x, y in points:
        body += (
            _pair(0, "VERTEX")
            + _pair(8, layer)
            + _pair(10, f"{x:.4f}")
            + _pair(20, f"{y:.4f}")
            + _pair(30, "0.0")
        )
    return body + _pair(0, "SEQEND") + _pair(8, layer)


def _sanitise(name):
    return "".join(c if c.isalnum() or c in "_-$" else "_" for c in name).upper()[:31]


def write(path, entities, extents):
    layers, seen = [], set()
    for layer, _, _ in entities:
        clean = _sanitise(layer)
        if clean in seen:
            continue
        seen.add(clean)
        colour = COLOUR_DEFAULT
        for prefix, value in COLOUR_BY_PREFIX:
            if clean.startswith(prefix):
                colour = value
                break
        layers.append((clean, colour))

    body = _header(extents) + _tables(layers)
    body += _pair(0, "SECTION") + _pair(2, "ENTITIES")
    for layer, points, closed in entities:
        ring = list(points)
        if closed and len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        body += _polyline(_sanitise(layer), ring, closed)
    body += _pair(0, "ENDSEC") + _pair(0, "EOF")

    path.write_text(body, encoding="ascii", errors="replace")
    return len(layers)
