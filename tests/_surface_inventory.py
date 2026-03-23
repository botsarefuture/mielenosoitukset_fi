import ast
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "mielenosoitukset_fi"


def _iter_python_files():
    yield from sorted(APP_ROOT.rglob("*.py"))


def _parse_blueprint_prefixes() -> Dict[str, str]:
    """
    Parse app.py to extract blueprint registrations and their URL prefixes.
    
    Returns
    -------
    Dict[str, str]
        Mapping of blueprint variable names to their effective URL prefixes.
    """
    app_py = APP_ROOT / "app.py"
    try:
        tree = ast.parse(app_py.read_text(encoding="utf-8"))
    except SyntaxError:
        return {}
    
    prefixes = {}
    for node in ast.walk(tree):
        # Look for app.register_blueprint(...) calls
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "register_blueprint":
            continue
        
        # Get blueprint name from first argument
        if not node.args:
            continue
        bp_arg = node.args[0]
        bp_name = None
        if isinstance(bp_arg, ast.Name):
            bp_name = bp_arg.id
        
        if not bp_name:
            continue
        
        # Look for url_prefix keyword argument
        for keyword in node.keywords:
            if keyword.arg == "url_prefix" and isinstance(keyword.value, ast.Constant):
                prefixes[bp_name] = keyword.value.value
                break
    
    return prefixes


def _get_blueprint_prefix_for_file(path: Path, bp_prefixes: Dict[str, str]) -> Optional[str]:
    """
    Determine the blueprint and its URL prefix for a given file.
    
    Parameters
    ----------
    path : Path
        Path to the Python file containing routes.
    bp_prefixes : Dict[str, str]
        Mapping of blueprint names to their URL prefixes from app.py.
    
    Returns
    -------
    Optional[str]
        The effective URL prefix for the blueprint, or None if not found.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    
    # Find Blueprint definitions in this file
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        
        # Look for assignments like: bp_var = Blueprint(...)
        if not isinstance(node.value, ast.Call):
            continue
        if isinstance(node.value.func, ast.Name) and node.value.func.id != "Blueprint":
            continue
        
        # Get the blueprint variable name
        bp_var_name = None
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            bp_var_name = node.targets[0].id
        
        if not bp_var_name:
            continue
        
        # Look for url_prefix in Blueprint() call
        for keyword in node.value.keywords:
            if keyword.arg == "url_prefix" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value
        
        # If no prefix in Blueprint definition, check app.py registration
        if bp_var_name in bp_prefixes:
            return bp_prefixes[bp_var_name]
    
    return None


def _route_entries_for_file(path: Path, bp_prefix: Optional[str] = None):
    """
    Extract route entries from a Python file.
    
    Parameters
    ----------
    path : Path
        Path to the Python file.
    bp_prefix : Optional[str]
        The blueprint's URL prefix to include in each route entry.
    
    Returns
    -------
    List[Dict]
        List of route entries with function name, route, methods, and prefix.
    """
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
                    "prefix": bp_prefix,  # Include the blueprint prefix
                }
            )
    return entries


def _sha256(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def collect_route_surfaces():
    """
    Collect all route surfaces from the application, including blueprint prefixes.
    
    Returns
    -------
    Dict[str, Dict]
        Mapping of relative file paths to their route surface metadata
        (count and SHA256 hash including blueprint prefixes).
    """
    # First, parse app.py to get all blueprint prefix registrations
    bp_prefixes = _parse_blueprint_prefixes()
    
    surfaces = {}
    for path in _iter_python_files():
        # Determine the blueprint prefix for this file
        bp_prefix = _get_blueprint_prefix_for_file(path, bp_prefixes)
        
        # Extract routes with the blueprint prefix
        entries = _route_entries_for_file(path, bp_prefix)
        if not entries:
            continue
        
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        
        # Sort entries for consistent hashing, including the prefix
        serializable = sorted(
            entries,
            key=lambda item: (
                item["prefix"] or "",
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
    """
    Collect API route entries with their blueprint prefix.
    
    Returns
    -------
    List[Dict]
        List of API route entries including their prefix.
    """
    bp_prefixes = _parse_blueprint_prefixes()
    bp_prefix = _get_blueprint_prefix_for_file(APP_ROOT / "api" / "routes.py", bp_prefixes)
    return _route_entries_for_file(APP_ROOT / "api" / "routes.py", bp_prefix)


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
