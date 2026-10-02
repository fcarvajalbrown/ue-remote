import argparse
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_ENGINE_ROOT = Path("D:/EpicGames/UE_5.5")
CLIENT_SUBPATH = Path("Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python")
DISCOVERY_SECONDS = 3.0


def load_client(engine_root):
    client_dir = engine_root / CLIENT_SUBPATH
    if not (client_dir / "remote_execution.py").is_file():
        sys.exit(f"remote_execution.py not found under {client_dir}")
    sys.path.insert(0, str(client_dir))
    import remote_execution

    return remote_execution


def discover(client, wait_seconds):
    session = client.RemoteExecution()
    session.start()
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        time.sleep(0.25)
    return session, session.remote_nodes


def pick_node(nodes, project):
    matches = [n for n in nodes if n.get("project_name", "").lower() == project.lower()]
    if not matches:
        names = ", ".join(sorted(n.get("project_name", "?") for n in nodes)) or "none"
        sys.exit(f"no open editor for project '{project}' (found: {names})")
    if len(matches) > 1:
        sys.exit(f"{len(matches)} editors open for project '{project}', close all but one")
    return matches[0]


def parse_script_args(pairs):
    values = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            sys.exit(f"--arg expects key=value, got '{pair}'")
        values.setdefault(key, []).append(value)
    return values


def read_code(args):
    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
    elif args.code:
        body = args.code
    else:
        body = sys.stdin.read()
    return f"ARGS = {parse_script_args(args.arg)!r}\n{body}"


def run(args, client):
    session, nodes = discover(client, args.wait)
    try:
        node = pick_node(nodes, args.project)
        session.open_command_connection(node["node_id"])
        result = session.run_command(read_code(args), unattended=True, exec_mode=client.MODE_EXEC_FILE)
    finally:
        session.stop()
    for line in result.get("output", []):
        stream = sys.stderr if line.get("type") in ("Warning", "Error") else sys.stdout
        print(line.get("output", "").rstrip("\n"), file=stream)
    if not result.get("success"):
        print(result.get("result", ""), file=sys.stderr)
        return 1
    return 0


def list_nodes(args, client):
    session, nodes = discover(client, args.wait)
    session.stop()
    print(json.dumps([n for n in nodes], indent=2))
    return 0 if nodes else 1


def parse_args():
    parser = argparse.ArgumentParser(description="Run Python inside an open Unreal Editor via Remote Execution.")
    parser.add_argument("--engine", type=Path, default=Path(os.environ.get("UE_ROOT", DEFAULT_ENGINE_ROOT)))
    parser.add_argument("--wait", type=float, default=DISCOVERY_SECONDS, help="seconds to listen for editors")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list open editors with Remote Execution enabled")
    exec_parser = sub.add_parser("exec", help="run Python in one editor")
    exec_parser.add_argument("project", help="project name, e.g. san_igna or StoryFramework")
    source = exec_parser.add_mutually_exclusive_group()
    source.add_argument("-f", "--file", help="Python file to run")
    source.add_argument("-c", "--code", help="Python source to run")
    exec_parser.add_argument("--arg", action="append", default=[], help="key=value, repeatable; exposed to the script as ARGS[key] (a list)")
    return parser.parse_args()


def main():
    args = parse_args()
    client = load_client(args.engine)
    if args.command == "list":
        return list_nodes(args, client)
    return run(args, client)


if __name__ == "__main__":
    sys.exit(main())
