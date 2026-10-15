"""Live validation oracle for generated .cfx files.

Mirrors the 145 engine's oracle.py: one POST to the RUNNING SQX's
`taskmanager/validateProject` - the side-effect-free project validator.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

import httpx


# ── Constants ────────────────────────────────────────────────────────────────

VALIDATE_ENDPOINT = "/taskmanager/validateProject"
_VERSION_WARN_RE = re.compile(r"differs from this build \(([\d.]+)\)")


# ── Browser token resolution ─────────────────────────────────────────────────


def _read_browser_token() -> str | None:
    """Read the browser token from the SQX settings file."""
    from pathlib import Path
    
    for p in [
        Path("user/settings/settings.xml"),
        Path("user/settings/Configs/settings.xml"),
        Path.home() / ".config" / "strategyquantx" / "browser_token",
    ]:
        if p.exists():
            try:
                import xml.etree.ElementTree as ET
                root = ET.parse(p).getroot()
                for elem in root.iter("BrowserToken"):
                    if elem.text:
                        return elem.text.strip()
            except Exception:
                pass
    
    return None


def _get_browser_token() -> str:
    """Get browser token or raise."""
    token = _read_browser_token()
    if not token:
        token = __import__("os").environ.get("SQX_BROWSER_TOKEN")
    if not token:
        raise RuntimeError(
            "Browser token not found. Set SQX_BROWSER_TOKEN or ensure "
            "user/settings/settings.xml has <BrowserToken>."
        )
    return token


# ── Version self-heal ────────────────────────────────────────────────────────

_VERSION_WARN_RE = re.compile(r"differs from this build \(([\d.]+)\)")


def _extract_version_from_warning(warning: str) -> str | None:
    """Extract version from version mismatch warning."""
    match = re.search(r"differs from this build \(([\d.]+)\)", warning)
    return match.group(1) if match else None


def _restamp_version(cfx_path: Path, new_version: str) -> Path:
    """Restamp config.xml version in a .cfx and return new path."""
    import tempfile
    import zipfile
    from xml.etree import ElementTree as ET
    
    with zipfile.ZipFile(cfx_path, "r") as z:
        config_data = z.read("config.xml")
        task_files = [n for n in z.namelist() if n.endswith(".xml") and n != "config.xml"]
    
    config_root = ET.fromstring(config_data)
    config_root.set("version", new_version)
    
    new_cfx = Path(tempfile.mktemp(suffix=".cfx"))
    with zipfile.ZipFile(new_cfx, "w", compression=zipfile.ZIP_DEFLATED) as z:
        import xml.etree.ElementTree as ET
        z.writestr("config.xml", ET.tostring(ET.fromstring(ET.tostring(ET.fromstring(z.read("config.xml"))), encoding="unicode")))
        # Simplified: just copy other files
        with zipfile.ZipFile(cfx_path, "r") as z_in:
            for name in z_in.namelist():
                if name != "config.xml":
                    z.writestr(name, z_in.read(name))
    
    return new_cfx


# ── Live validation ──────────────────────────────────────────────────────────


async def validate_cfx(
    cfx_path: Path,
    base_url: str = "http://127.0.0.1:5050",
    max_self_heal: int = 1,
) -> dict:
    """
    Submit a .cfx to SQX's side-effect-free validator.
    
    Returns:
        {
            "ok": bool,
            "verdict": "PASS" | "FAIL" | "VALIDATE_PASS" | "VALIDATE_FAIL",
            "validate_json": dict,
            "warnings": list[str],
            "exit_code": int,
        }
    """
    token = _get_browser_token()
    url = f"{base_url.rstrip('/')}/taskmanager/validateProject"
    
    attempt = 0
    current_cfx = cfx_path
    
    while attempt <= max_self_heal:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with current_cfx.open("rb") as f:
                files = {"file": (current_cfx.name, f, "application/octet-stream")}
                headers = {"BrowserToken": _get_browser_token()}
                try:
                    resp = await client.post(
                        f"{base_url.rstrip('/')}/taskmanager/validateProject",
                        files=files, headers=headers, timeout=60.0
                    )
                except httpx.RequestError as e:
                    return {
                        "ok": False,
                        "verdict": "FAIL",
                        "validate_json": {"error": str(e)},
                        "warnings": [f"Request failed: {e}"],
                        "exit_code": 1,
                    }
        
        # Parse response
        try:
            data = resp.json()
        except Exception:
            return {
                "ok": False,
                "verdict": "FAIL",
                "validate_json": {"raw": resp.text[:500]},
                "warnings": ["Invalid JSON response"],
                "exit_code": 1,
            }
        
        verdict = data.get("verdict", "UNKNOWN")
        ok = verdict in ("PASS", "VALIDATE_PASS")
        
        # Check for version self-heal warning
        warnings = []
        if "warning" in data:
            msg = str(data.get("warning", ""))
            match = re.search(r"differs from this build \(([\d.]+)\)", msg)
            if match:
                version = match.group(1)
                warnings.append(f"Version mismatch: {version}")
                if attempt < max_self_heal:
                    # Self-heal: restamp version and retry
                    new_cfx = _restamp_version(cfx_path, version)
                    cfx_path = Path(cfx_path)  # Update path
                    attempt += 1
                    continue
        
        return {
            "ok": ok,
            "verdict": verdict,
            "validate_json": data,
            "warnings": warnings,
            "exit_code": 0 if data.get("success") else 3,
        }
    
    return {
        "ok": False,
        "verdict": "FAIL",
        "validate_json": {"error": "Max self-heal attempts exceeded"},
        "warnings": ["Max self-heal attempts exceeded"],
        "exit_code": 3,
    }


def validate(cfx_path: Path, base_url: str = "http://127.0.0.1:5050") -> tuple[bool, dict]:
    """
    Synchronous wrapper for validation.
    
    Returns:
        (ok, verdict_dict)
    """
    import asyncio
    result = asyncio.run(validate_cfx(cfx_path, base_url))
    return result["ok"], result


# ── CLI ──────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python oracle.py <path-to-.cfx>")
        sys.exit(1)
    
    cfx_path = Path(sys.argv[1])
    if not cfx_path.exists():
        print(f"Error: {cfx_path} not found")
        sys.exit(1)
    
    ok, result = validate(cfx_path)
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    if not ok:
        print(f"Error: {result.get('validate_json', {}).get('error', 'Unknown')}")
    sys.exit(0 if ok else 1)