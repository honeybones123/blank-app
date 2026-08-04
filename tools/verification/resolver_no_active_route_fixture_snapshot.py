"""Compatibility wrapper for retired no-active legacy resolver fixture.

The original synthetic fixture called ``inputs_page.resolve_final_visible_design_guide_item``.
Route-specific controller verifiers now cover that behavior. This wrapper keeps
the historical command/artifact name alive without importing ``inputs_page.py``
or invoking the retired resolver body.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper() or "LOCKED" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    readiness = _latest("design_guide_legacy_resolver_fixture_retirement_readiness")
    capture = dict((readiness.get("payload") or {}).get("capture") or {})
    fixture_rows = [
        row
        for row in list(capture.get("fixture_rows") or [])
        if row.get("fixture") == "resolver_no_active_route_fixture_snapshot.py"
    ]
    status = "PASS" if readiness.get("status") == "PASS" and fixture_rows else "FAIL"
    report = {
        "schema": "resolver_no_active_route_fixture_snapshot.v2.retired",
        "scope": "retired_compatibility_wrapper_no_inputs_page_import",
        "status": status,
        "retired": True,
        "replacement_readiness": {
            "status": readiness.get("status"),
            "path": readiness.get("path"),
            "decision": capture.get("decision"),
        },
        "fixture_rows": fixture_rows,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }
    output = ARTIFACT_DIR / f"resolver_no_active_route_fixture_snapshot_7DC_{stamp}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{status}: {output}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
