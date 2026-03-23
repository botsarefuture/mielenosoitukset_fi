import ast
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "mielenosoitukset_fi"


def _iter_python_files():
    yield from sorted(APP_ROOT.rglob("*.py"))


def _route_entries_for_file(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    entries = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr != "route":
                continue

            route = None
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                route = decorator.args[0].value

            methods = ["GET"]
            for keyword in decorator.keywords:
                if keyword.arg != "methods":
                    continue
                if isinstance(keyword.value, (ast.List, ast.Tuple)):
                    methods = [
                        item.value
                        for item in keyword.value.elts
                        if isinstance(item, ast.Constant)
                    ]

            entries.append(
                {
                    "function": node.name,
                    "route": route,
                    "methods": methods,
                }
            )
    return entries


def _sha256(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def collect_route_surfaces():
    surfaces = {}
    for path in _iter_python_files():
        entries = _route_entries_for_file(path)
        if not entries:
            continue
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        serializable = sorted(
            entries,
            key=lambda item: (
                item["route"] or "",
                ",".join(item["methods"]),
                item["function"],
            ),
        )
        surfaces[rel_path] = {
            "count": len(entries),
            "sha256": _sha256(serializable),
        }
    return surfaces


def collect_api_route_entries():
    return _route_entries_for_file(APP_ROOT / "api" / "routes.py")


def collect_background_job_surface():
    path = APP_ROOT / "background_jobs" / "definitions.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    keys = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "JobDefinition":
            continue
        for keyword in node.keywords:
            if keyword.arg == "key" and isinstance(keyword.value, ast.Constant):
                keys.append(keyword.value.value)
        if node.args and isinstance(node.args[0], ast.Constant):
            keys.append(node.args[0].value)
    keys = sorted(set(keys))
    return {
        "count": len(keys),
        "sha256": _sha256(keys),
    }


def collect_socketio_surface():
    path = APP_ROOT / "users" / "BPs" / "chat_ws.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    entries = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr != "on":
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            entries.append(
                {
                    "function": node.name,
                    "event": decorator.args[0].value,
                }
            )

    serializable = sorted(entries, key=lambda item: (item["event"], item["function"]))
    return {
        "count": len(entries),
        "sha256": _sha256(serializable),
    }
