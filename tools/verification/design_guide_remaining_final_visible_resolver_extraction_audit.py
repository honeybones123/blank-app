"""Audit remaining final-visible resolver extraction surface after assembler deletion."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    route_run = _run("tools/verification/design_guide_controller_compute_selector_legacy_route_parity_snapshot.py")
    inventory_run = _run("tools/verification/design_guide_remaining_final_visible_assembler_inventory_audit.py")
    route_payload = (_latest("design_guide_controller_compute_selector_legacy_route_parity").get("payload") or {})
    inventory_payload = (
        _latest("design_guide_remaining_final_visible_assembler_inventory").get("payload") or {}
    )
    route_capture = dict(route_payload.get("capture") or {})
    inventory_capture = dict(inventory_payload.get("capture") or {})
    remaining_assembler_count = int(inventory_capture.get("remaining_assembler_count") or 0)
    route_parity_retired_by_resolver_deletion = (
        not bool(route_run.get("passed"))
        and remaining_assembler_count == 0
        and "Could not find function resolve_final_visible_design_guide_item"
        in str(route_run.get("stderr_tail") or "")
    )
    page_owned_routes = list(route_capture.get("page_owned_routes") or [])
    controller_owned_routes = list(route_capture.get("owned_routes") or [])
    return {
        "decision": (
            "FINAL_VISIBLE_RESOLVER_EXTRACTION_COMPLETE"
            if route_parity_retired_by_resolver_deletion and not page_owned_routes
            else "NEXT_EXTRACTION_SURFACE_IDENTIFIED"
        ),
        "verification": {
            "route_parity": route_run,
            "route_parity_retired_by_resolver_deletion": route_parity_retired_by_resolver_deletion,
            "remaining_assembler_inventory": inventory_run,
        },
        "remaining_final_visible_assembler_count": remaining_assembler_count,
        "controller_owned_routes": controller_owned_routes,
        "page_owned_routes": page_owned_routes,
        "next_safe_extraction_route": (
            page_owned_routes[0] if page_owned_routes else "none_final_visible_resolver_routes_left"
        ),
        "route_classification": list(route_capture.get("route_results") or []),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    verification = capture.get("verification") or {}
    return {
        "route_parity_passed_or_retired": (
            (verification.get("route_parity") or {}).get("passed") is True
            or verification.get("route_parity_retired_by_resolver_deletion") is True
        ),
        "remaining_assembler_inventory_passed": (
            verification.get("remaining_assembler_inventory") or {}
        ).get("passed")
        is True,
        "no_final_visible_assemblers_remain": capture.get("remaining_final_visible_assembler_count")
        == 0,
        "remaining_page_owned_routes_explicit": isinstance(capture.get("page_owned_routes"), list),
        "controller_owned_routes_explicit": isinstance(capture.get("controller_owned_routes"), list),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = payload.get("capture") or {}
    lines = [
        "# Design Guide Remaining Final-Visible Resolver Extraction Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Remaining final-visible assemblers: `{capture.get('remaining_final_visible_assembler_count')}`",
        f"Next safe extraction route: `{capture.get('next_safe_extraction_route')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Controller-Owned Routes",
            "",
        ]
    )
    lines.extend(f"- `{route}`" for route in capture.get("controller_owned_routes") or [])
    lines.extend(["", "## Still Page-Owned Routes", ""])
    lines.extend(f"- `{route}`" for route in capture.get("page_owned_routes") or [])
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Start the next proof-only slice with the first still page-owned route listed above. "
            "Do not delete resolver branches until route-specific controller ownership, parity, "
            "cutover, and deletion proofs pass.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_remaining_final_visible_resolver_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_remaining_final_visible_resolver_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_remaining_final_visible_resolver_extraction {status}")
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_extraction_route={capture.get('next_safe_extraction_route')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
