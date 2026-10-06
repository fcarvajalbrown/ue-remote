import statistics

import ezdxf

MIN_MEASUREMENT = 1e-6
TOP_SAMPLES = 8


def linear_dimensions(document):
    samples = []
    for entity in document.modelspace().query("DIMENSION"):
        measurement = entity.dxf.get("actual_measurement", 0.0)
        if measurement <= MIN_MEASUREMENT:
            continue
        if not (entity.dxf.hasattr("defpoint2") and entity.dxf.hasattr("defpoint3")):
            continue
        distance = entity.dxf.defpoint2.distance(entity.dxf.defpoint3)
        if distance <= MIN_MEASUREMENT:
            continue
        samples.append((measurement, distance, entity.dxf.layer))
    return samples


def calibration_report(path):
    document = ezdxf.readfile(path)
    samples = linear_dimensions(document)
    if not samples:
        return "no usable linear dimensions"
    ratios = [distance / measurement for measurement, distance, _ in samples]
    median = statistics.median(ratios)
    spread = statistics.pstdev(ratios) / median if median else 0.0
    lines = [
        f"linear dimensions used: {len(samples)}",
        f"drawing units per measured unit, median: {median:.4f} (relative spread {spread:.3f})",
        "samples (measured, drawing distance):",
    ]
    for measurement, distance, layer in samples[:TOP_SAMPLES]:
        lines.append(f"  {measurement:.3f}  {distance:.3f}  {layer}")
    return "\n".join(lines)
