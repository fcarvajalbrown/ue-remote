import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def editor_open(project):
    result = subprocess.run([sys.executable, str(HERE / "ue_remote.py"), "list"], capture_output=True, text=True)
    try:
        nodes = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return any(node.get("project_name", "").lower() == project.lower() for node in nodes)


def pick(document, dotted):
    for part in dotted.split("."):
        document = document[part]
    return document


def format_value(value):
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def apply(lines, section, values):
    header = f"[{section}]"
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(header)
        start = len(lines) - 1
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    changes = []
    for name, value in values.items():
        wanted = f"{name}={format_value(value)}"
        pattern = re.compile(rf"^\+?{re.escape(name)}=", re.IGNORECASE)
        index = next((i for i in range(start + 1, end) if pattern.match(lines[i].strip())), None)
        if index is None:
            lines.insert(end, wanted)
            end += 1
            changes.append(f"added   {wanted}")
        elif lines[index].strip() != wanted:
            changes.append(f"changed {lines[index].strip()} -> {wanted}")
            lines[index] = wanted
    return changes


def main():
    parser = argparse.ArgumentParser(description="Write console variables from a JSON spec into a project's ini, with the editor closed.")
    parser.add_argument("--ini", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--key", required=True, help="dotted path to an object of name: value pairs, for example fog.cvars")
    parser.add_argument("--section", default="SystemSettings")
    parser.add_argument("--project", help="project name; refuses to run while its editor is open")
    args = parser.parse_args()

    if len(args.section) > 1 and args.section[1] == ":":
        raise SystemExit(f"section {args.section} looks like a Windows path; in Git Bash set MSYS_NO_PATHCONV=1 so /Script/... is not rewritten")
    if args.project and editor_open(args.project):
        raise SystemExit(f"the editor for {args.project} is open; close it first, the ini is read at startup")
    values = pick(json.loads(args.spec.read_text(encoding="utf-8")), args.key)
    text = args.ini.read_text(encoding="utf-8") if args.ini.exists() else ""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    changes = apply(lines, args.section, values)
    if not changes:
        print("ini already matches the spec")
        return
    args.ini.write_text(newline.join(lines) + newline, encoding="utf-8")
    for change in changes:
        print(change)


if __name__ == "__main__":
    main()
