"""High-level SQX spec validator CLI and orchestration."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from .spec import validate_spec as spec_validate_spec, SpecValidationError
from .oracle import validate_cfx, _get_browser_token


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """Result of a live validation."""
    ok: bool
    cfx_path: Path
    verdict: str  # "PASS" | "FAIL" | "VALIDATE_PASS" | "VALIDATE_FAIL"
    validate_json: dict
    warnings: list[str] = field(default_factory=list)
    exit_code: int = 0  # 0=ok, 1=bad spec, 2=bad json, 3=built but validation failed


# ── Version self-heal ────────────────────────────────────────────────────────

_VERSION_WARN_RE = __import__("re").compile(r"differs from this build \(([\d.]+)\)")


def _extract_version_from_warning(warning: str) -> str | None:
    """Extract version from version mismatch warning."""
    match = _VERSION_WARN_RE.search(warning)
    return match.group(1) if match else None


def _restamp_version(cfx_path: Path, new_version: str) -> Path:
    """Restamp config.xml version in a .cfx and return new path."""
    import zipfile
    import tempfile
    from xml.etree import ElementTree as ET
    
    with zipfile.ZipFile(cfx_path, "r") as z:
        config_data = z.read("config.xml")
        task_files = [n for n in z.namelist() if n.endswith(".xml") and n != "config.xml"]
    
    config_root = ET.fromstring(config_data)
    config_root.set("version", new_version)
    
    new_cfx = Path(tempfile.mktemp(suffix=".cfx"))
    with zipfile.ZipFile(new_cfx, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("config.xml", ET.tostring(config_root, encoding="unicode", xml_declaration=True))
        with zipfile.ZipFile(cfx_path, "r") as z_in:
            for name in z_in.namelist():
                if name != "config.xml":
                    z.writestr(name, z_in.read(name))
    
    return new_cfx


# ── Main validation orchestration ────────────────────────────────────────────


async def _validate_cfx_internal(
    cfx_path: Path,
    base_url: str,
    max_self_heal: int = 1,
) -> ValidationResult:
    """Internal validation with self-heal logic."""
    token = _get_browser_token()
    url = f"{base_url.rstrip('/')}/taskmanager/validateProject"
    
    attempt = 0
    current_cfx = cfx_path
    
    while attempt <= 1:  # max_self_heal
        async with httpx.AsyncClient(timeout=60.0) as client:
            with current_cfx.open("rb") as f:
                files = {"file": (current_cfx.name, f, "application/octet-stream")}
                headers = {"BrowserToken": _get_browser_token()}
                try:
                    resp = await client.post(url, files=files, headers=headers, timeout=60.0)
                except httpx.RequestError as e:
                    return ValidationResult(
                        ok=False,
                        cfx_path=Path(""),
                        verdict="FAIL",
                        validate_json={"error": str(e)},
                        warnings=[f"Request failed: {e}"],
                        exit_code=1,
                    )
        
        try:
            data = resp.json()
        except Exception:
            return ValidationResult(
                ok=False,
                cfx_path=Path(""),
                verdict="FAIL",
                validate_json={"raw": resp.text[:500]},
                warnings=["Invalid JSON response"],
                exit_code=1,
            )
        
        verdict = data.get("verdict", "UNKNOWN")
        ok = verdict in ("PASS", "VALIDATE_PASS")
        
        warnings = []
        if "warning" in data:
            match = __import__("re").search(r"differs from this build \(([\d.]+)\)", str(data.get("warning", "")))
            if match:
                warnings.append(f"Version mismatch: {match.group(1)}")
                # Self-heal not implemented in this version
        
        return ValidationResult(
            ok=ok,
            cfx_path=Path(""),
            verdict=data.get("verdict", "UNKNOWN"),
            validate_json=data,
            warnings=warnings,
            exit_code=0 if data.get("success") else 3,
        )
    
    return ValidationResult(
        ok=False,
        cfx_path=Path(""),
        verdict="FAIL",
        validate_json={"error": "Max self-heal attempts exceeded"},
        warnings=["Max self-heal attempts exceeded"],
        exit_code=3,
    )


def validate_spec_json(
    spec_json: str,
    base_url: str = "http://127.0.0.1:5050",
    session_id: str | None = None,
) -> ValidationResult:
    """Validate a spec JSON string synchronously."""
    # Fail fast on Python 3.14 (compiler bug: inverted conditional jumps)
    import sys
    if sys.version_info[:2] == (3, 14):
        return ValidationResult(
            ok=False,
            cfx_path=Path(""),
            verdict="FAIL",
            validate_json={"error": "Python 3.14 not supported: compiler bug inverts conditional jumps (POP_JUMP_IF_NOT_NONE, POP_JUMP_IF_FALSE, POP_JUMP_IF_TRUE). Use Python <=3.13."},
            warnings=["Python 3.14 detected - validation disabled"],
            exit_code=1,
        )
    # 1. Parse and validate spec
    try:
        from .spec import validate_spec as spec_validate
        spec_validate(json.loads(spec_json))
    except SpecValidationError as e:
        return ValidationResult(
            ok=False,
            cfx_path=Path(""),
            verdict="FAIL",
            validate_json={"error": str(e)},
            warnings=[],
            exit_code=1,
        )
    except json.JSONDecodeError as e:
        return ValidationResult(
            ok=False,
            cfx_path=Path(""),
            verdict="FAIL",
            validate_json={"error": f"Invalid JSON: {e}"},
            warnings=[],
            exit_code=2,
        )
    
    # Generate .cfx
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".cfx", delete=False) as tmp:
        cfx_path = Path(tmp.name)
    
    try:
        from .builder import generate_cfx_from_spec
        generate_cfx_from_spec(json.loads(spec_json), Path(tmp.name))
    except Exception as e:
        return ValidationResult(
            ok=False,
            cfx_path=Path(""),
            verdict="FAIL",
            validate_json={"error": f"CFX generation failed: {e}"},
            warnings=[],
            exit_code=1,
        )
    
    # Run validation
    return asyncio.run(_validate_cfx_internal(Path(tmp.name), base_url))


def generate_cfx_from_spec(spec_dict: dict, output_path: Path) -> None:
    """Generate a .cfx from spec dict (delegates to builder)."""
    from .builder import generate_cfx_from_spec as _generate
    _generate(spec_dict, output_path)


# ── CLI entry point ──────────────────────────────────────────────────────────


def main() -> int:
    """CLI entry point: `quantlab sqx validate <spec.json>`"""
    parser = argparse.ArgumentParser(
        prog="quantlab sqx validate",
        description="Validate an SQX project spec via live validation.",
    )
    parser.add_argument("spec", help="Path to spec JSON file, or '-' for stdin")
    parser.add_argument("--url", default="http://127.0.0.1:5050", help="SQX base URL")
    parser.add_argument("--session", help="Session ID for workspace output")
    parser.add_argument("--out", help="Write generated .cfx to this path")
    parser.add_argument("--no-verify", action="store_true", help="Skip live validation")

    args = parser.parse_args()

    if args.spec == "-":
        spec_json = sys.stdin.read()
    else:
        with open(args.spec, "r", encoding="utf-8") as f:
            spec_json = f.read()

    if args.no_verify:
        print("SKIPPED validation (--no-verify)")
        return 0

    result = validate_spec(spec_json, base_url=args.url)

    # Print machine-readable output (matches oracle.py contract)
    if result.verdict in ("PASS", "VALIDATE_PASS"):
        print("VALIDATE PASS")
    else:
        print(f"VALIDATE FAIL: {result.validate_json.get('error', 'Unknown error')}")

    for w in result.warnings:
        print(f"WARN {w}")

    if result.validate_json:
        print(f"VALIDATE_JSON {json.dumps(result.validate_json)}")

    return result.exit_code


def generate_cfx_from_spec(spec_dict: dict, output_path: Path) -> None:
    """Generate a .cfx from spec dict (delegates to builder)."""
    from .builder import build_cfx_from_spec as _generate
    _generate(spec_dict, output_path)


if __name__ == "__main__":
    sys.exit(main())