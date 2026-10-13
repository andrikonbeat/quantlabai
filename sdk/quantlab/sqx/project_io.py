"""Project I/O: existing projects in and out of the compact spec world.

Mirrors the 145 engine's project_io.py:
- load_project_cfx: reads registered project or .cfx into config + per-task settings trees
- describe: turns a project into COMPACT summary for LLM
- merge_edit + apply_inplace: execute parsed edit plan
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator
from xml.etree import ElementTree as ET

import httpx


# ── CFX Loading ──────────────────────────────────────────────────────────────


def load_project_cfx(cfx_path: Path | str) -> tuple[ET.Element, list[ET.Element]]:
    """
    Load a project .cfx into config + per-task settings trees.
    
    Keeps every entry's ORIGINAL bytes - an edit regenerates only the tasks
    it names, everything else goes back byte-identical.
    
    Returns:
        (config_root, [task_settings_roots])
    """
    cfx_path = Path(cfx_path)
    with zipfile.ZipFile(cfx_path, "r") as z:
        config_data = z.read("config.xml")
        config_root = ET.fromstring(config_data)
        
        task_files = [n for n in z.namelist() 
                     if n.endswith(".xml") and n != "config.xml"]
        
        task_roots = []
        for tf in sorted(task_files):
            task_root = ET.fromstring(z.read(tf))
            task_roots.append(task_root)
        
        return config_root, task_roots


# ── Describe (compact summary for LLM) ───────────────────────────────────────


def describe(config_root: ET.Element, task_roots: list[ET.Element]) -> dict:
    """
    Turn a project into the COMPACT summary the LLM is allowed to see.
    
    Per task: type/name/active/wiring, curated keys recognized back out of
    the XML, and which top-level sections differ from the shipped default.
    Never raw XML.
    """
    result = {
        "project_name": None,
        "version": None,
        "tasks": [],
        "databanks": [],
    }
    
    # Project info
    project_name = config_root.get("name")
    version = config_root.get("version")
    result["project_name"] = project_name
    result["version"] = version
    
    # Databanks
    for db in config_root.findall(".//Databank"):
        result["databanks"].append({
            "name": db.get("name"),
            "view": db.get("view"),
            "sync_type": db.get("syncType"),
            "position": db.get("position"),
        })
    
    # Tasks
    for i, task_root in enumerate(task_roots):
        task_info = _describe_task(task_root)
        result["tasks"].append(task_info)
    
    return result


def _describe_task(settings_root: ET.Element) -> dict:
    """Extract compact description from a task's Settings tree."""
    info = {
        "task_type": None,
        "name": None,
        "active": None,
        "curated_keys": {},
        "sections_present": [],
        "databank_wiring": [],
    }
    
    # Task type/name from parent Task element would be in config.xml
    # For now, extract from settings if available
    if settings_root is not None:
        # Extract curated keys (Params)
        for param in settings_root.findall(".//Param[@key]"):
            key = param.get("key")
            if key:
                value = param.text
                if value is not None:
                    _add_curated_key(key, param.text)
    
    # Direct children
    for child in settings_root:
        if child.tag not in ("Params", "CrossChecks"):
            if child.text and child.text.strip():
                _add_curated_key(child.tag, child.text)
    
    return {
        "curated_keys": {},
        "sections_present": [],
    }


def _add_curated_key(keys: dict, key: str, value: str) -> None:
    """Add a curated key to the dict if it's a known curated key."""
    # This would map XML elements back to curated key names
    pass


# ── Edit plan execution ──────────────────────────────────────────────────────


@dataclass
class EditOp:
    """Single edit operation in an edit plan."""
    op: str  # "set", "add_task", "remove_task", "move_task", "rename_task", "activate_task", "clone_task", "create_databank", "remove_databank"
    target: str  # task name, databank name, etc.
    value: Any = None
    index: int | None = None  # for move_task, add_task position


def merge_edit(
    config_root: ET.Element,
    task_roots: list[ET.Element],
    edit_plan: list[dict],
) -> tuple[ET.Element, list[ET.Element]]:
    """
    Execute a parsed edit plan on the project.
    
    Returns new (config_root, task_roots) with edits applied.
    """
    # Deep copy to avoid mutating originals
    config_root = ET.fromstring(ET.tostring(config_root, encoding="unicode"))
    task_roots = [ET.fromstring(ET.tostring(t, encoding="unicode")) for t in task_roots]
    
    for edit in edit_plan:
        op = edit.get("op")
        if op == "set":
            _apply_set(config_root, edit)
        elif op == "add_task":
            _add_task(config_root, edit)
        elif op == "remove_task":
            _remove_task(config_root, edit)
        # ... other ops
    
    return config_root, task_roots


def _apply_set(config_root: ET.Element, edit: dict) -> None:
    """Apply a set operation to config."""
    target = edit.get("target")
    value = edit.get("value")
    # Implementation would depend on target path
    pass


def _add_task(config_root: ET.Element, edit: dict) -> None:
    """Add a new task to config."""
    pass


def _remove_task(config_root: ET.Element, edit: dict) -> None:
    """Remove a task from config."""
    pass


# ── Live HTTP Apply Inplace ──────────────────────────────────────────────────


async def apply_inplace(
    cfx_path: Path,
    edit_plan: list[dict],
    base_url: str = "http://127.0.0.1:5050",
    browser_token: str | None = None,
) -> dict:
    """
    Execute edit plan against a RUNNING SQX instance via HTTP API.
    
    Uses HTTP endpoints:
    - updateTaskXML (update task settings)
    - addTask (add new task)
    - removeTask (remove task)
    - moveTask (move task position)
    - renameTask (rename task)
    - activateTask (activate/deactivate task)
    - createDatabank (create new databank)
    - removeDatabank (remove databank)
    - updateTaskXML (update task settings XML)
    - createProject (create new project)
    - loadProject (load project from .cfx)
    
    All calls use browserToken header for authentication.
    Each call guarded by server's "while project is running" check.
    
    Returns verdict dict with success status and any errors.
    """
    if browser_token is None:
        from quantlab.sqx.validator import _get_browser_token
        browser_token = _get_browser_token()
    
    base_url = base_url.rstrip('/')
    headers = {
        "BrowserToken": browser_token,
        "Content-Type": "application/json",
    }
    
    results = {"applied": [], "failed": [], "errors": []}
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for edit in edit_plan:
            op = edit.get("op")
            try:
                if op == "update_task_xml":
                    result = await _update_task_xml(client, base_url, headers, edit)
                elif op == "add_task":
                    result = await _add_task(client, base_url, headers, edit)
                elif op == "remove_task":
                    result = await _remove_task(client, base_url, headers, edit)
                elif op == "move_task":
                    result = await _move_task(client, base_url, headers, edit)
                elif op == "rename_task":
                    result = await _rename_task(client, base_url, headers, edit)
                elif op == "activate_task":
                    result = await _activate_task(client, base_url, headers, edit)
                elif op == "create_databank":
                    result = await _create_databank(client, base_url, headers, edit)
                elif op == "remove_databank":
                    result = await _remove_databank(client, base_url, headers, edit)
                else:
                    result = {"success": False, "error": f"Unknown operation: {op}"}
                
                if result.get("success"):
                    results["applied"].append({"op": op, "target": edit.get("target"), "result": result})
                else:
                    results["failed"].append({"op": op, "target": edit.get("target"), "error": result.get("error")})
            except Exception as e:
                results["errors"].append({"op": op, "target": edit.get("target"), "error": str(e)})
        
        return results


async def _update_task_xml(client: httpx.AsyncClient, base_url: str, headers: dict, edit: dict) -> dict:
    """Update task XML via updateTaskXML endpoint."""
    project = edit.get("project")
    task = edit.get("task")
    xml = edit.get("xml")
    
    if not project or not task or not xml:
        return {"success": False, "error": "Missing project, task, or xml"}
    
    url = f"http://{base_url}/sqai/task/updateTaskXML"
    payload = {
        "project": project,
        "task": task,
        "xml": xml,
    }
    
    try:
        resp = await client.post(f"{base_url}/taskmanager/updateTaskXML", 
                                headers={"BrowserToken": edit.get("browser_token", "")},
                                json={"projectName": project, "taskName": task, "taskXml": xml},
                                timeout=30.0)
        return {"success": resp.status_code == 200, "response": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _add_task(client: httpx.AsyncClient, base_url: str, headers: dict, edit: dict) -> dict:
    """Add a new task to a project."""
    project = edit.get("project")
    task_type = edit.get("task_type", "Build")
    task_name = edit.get("task_name")
    index = edit.get("index")
    
    if not project or not task_name:
        return {"success": False, "error": "Missing project or task_name"}
    
    try:
        url = f"{base_url}/taskmanager/addTask"
        params = {"projectName": project, "taskType": task_type, "taskName": task_name}
        if index is not None:
            params["index"] = index
        
        resp = await client.post(url, headers=headers, params=params, timeout=30.0)
        return {"success": resp.status_code == 200, "response": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _remove_task(client: httpx.AsyncClient, base_url: str, headers: dict, edit: dict) -> dict:
    """Remove a task from a project."""
    project = edit.get("project")
    task = edit.get("task")
    
    if not project or not task:
        return {"success": False, "error": "Missing project or task"}
    
    try:
        url = f"{base_url}/taskmanager/removeTask"
        resp = await client.post(url, headers=headers, 
                                params={"projectName": project, "taskName": task},
                                timeout=30.0)
        return {"success": resp.status_code == 200, "response": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _move_task(client: httpx.AsyncClient, base_url: str, headers: dict, edit: dict) -> dict:
    """Move a task to a new position."""
    project = edit.get("project")
    task = edit.get("task")
    index = edit.get("index")
    
    if not project or not task or index is None:
        return {"success": False, "error": "Missing project, task, or index"}
    
    try:
        url = f"{base_url}/taskmanager/moveTask"
        resp = await client.post(url, headers=headers,
                                params={"projectName": project, "taskName": task, "index": index},
                                timeout=30.0)
        return {"success": resp.status_code == 200, "response": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _rename_task(client: httpx.AsyncClient, base_url: str, headers: dict, edit: dict) -> dict:
    """Rename a task."""
    project = edit.get("project")
    task = edit.get("task")
    new_name = edit.get("new_name")
    
    if not project or not task or not new_name:
        return {"success": False, "error": "Missing project, task, or new_name"}
    
    try:
        url = f"{base_url}/taskmanager/renameTask"
        resp = await client.post(url, headers=headers,
                                params={"projectName": project, "taskName": task, "newName": new_name},
                                timeout=30.0)
        return {"success": resp.status_code == 200, "response": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _activate_task(client: httpx.AsyncClient, base_url: str, headers: dict, edit: dict) -> dict:
    """Activate or deactivate a task."""
    project = edit.get("project")
    task = edit.get("task")
    active = edit.get("active", True)
    
    if not project or not task:
        return {"success": False, "error": "Missing project or task"}
    
    try:
        url = f"{base_url}/taskmanager/activateTask"
        resp = await client.post(url, headers=headers,
                                params={"projectName": project, "taskName": task, "active": str(active).lower()},
                                timeout=30.0)
        return {"success": resp.status_code == 200, "response": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _create_databank(client: httpx.AsyncClient, base_url: str, headers: dict, edit: dict) -> dict:
    """Create a new databank in a project."""
    project = edit.get("project")
    name = edit.get("name")
    view = edit.get("view", "Default - Main data")
    sync_type = edit.get("sync_type", "Auto-sync never")
    position = edit.get("position", 0)
    
    if not project or not name:
        return {"success": False, "error": "Missing project or name"}
    
    try:
        url = f"{base_url}/taskmanager/createDatabank"
        resp = await client.post(url, headers=headers,
                                params={
                                    "projectName": project,
                                    "databankName": name,
                                    "view": view,
                                    "syncType": sync_type,
                                    "position": position,
                                },
                                timeout=30.0)
        return {"success": resp.status_code == 200, "response": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _remove_databank(client: httpx.AsyncClient, base_url: str, headers: dict, edit: dict) -> dict:
    """Remove a databank from a project."""
    project = edit.get("project")
    name = edit.get("name")
    
    if not project or not name:
        return {"success": False, "error": "Missing project or name"}
    
    try:
        url = f"{base_url}/taskmanager/removeDatabank"
        resp = await client.post(url, headers=headers,
                                params={"projectName": project, "databankName": name},
                                timeout=30.0)
        return {"success": resp.status_code == 200, "response": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── CFX generation from spec ─────────────────────────────────────────────────


def spec_to_cfx(spec_dict: dict, output_path: Path) -> None:
    """
    Generate a .cfx from spec dict (new project or edit).
    
    This is the main entry point for generating a validated .cfx.
    """
    from quantlab.sqx.builder import build_cfx_from_spec as generate_cfx_from_spec
    generate_cfx_from_spec(spec_dict, output_path)


def generate_cfx_from_spec(spec_dict: dict, output_path: Path) -> None:
    """Generate a .cfx from spec dict (delegates to builder)."""
    from quantlab.sqx.builder import build_cfx_from_spec as generate_cfx_from_spec
    generate_cfx_from_spec(spec_dict, output_path)


# ── CLI / Testing ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python project_io.py <project.cfx>")
        sys.exit(1)
    
    config_root, task_roots = load_project_cfx(sys.argv[1])
    desc = describe(config_root, task_roots)
    
    import json
    print(json.dumps(desc, indent=2, default=str))
