import sys
from pathlib import Path

import unreal

HERE = Path(__file__).resolve().parent


def parse_args(pairs):
    values = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator:
            raise SystemExit(f"expected key=value, got '{pair}'")
        values.setdefault(key, []).append(value)
    return values


def resolve(name):
    candidate = Path(name)
    if candidate.is_absolute():
        return candidate
    return HERE / "scripts" / name


def main(argv):
    if not argv:
        raise SystemExit("usage: py <path>/run_in_editor.py <script.py> [key=value ...]")
    script = resolve(argv[0])
    namespace = {"__name__": "__main__", "ARGS": parse_args(argv[1:])}
    exec(compile(script.read_text(encoding="utf-8"), str(script), "exec"), namespace)


main(sys.argv[1:])
