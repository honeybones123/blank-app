"""CTA/apply binding bypass readiness snapshot.

Proof-only. This verifier classifies whether repeated page-side CTA/apply
payload binding can be skipped on stable no-input reruns keyed by
FinalDesignGuidePublication.cta hash. It does not implement a bypass, move CTA
authority, change apply routing, or change visible wording.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
PRIMARY_APPLY_PAYLOAD = ROOT / "inputs_page_modules" / "design_guide" / "primary_apply_payload.py"
PRIMARY_APPLY_PAYLOAD_RECORDER = ROOT / "inputs_page_modules" / "design_guide" / "primary_apply_payload_recorder.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

REQUIRED_LOCKS = {
    "live_cta_authority_cutover": "design_guide_live_cta_authority_cutover",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "next_smoothness_hotspot_audit": "design_guide_next_smoothness_hotspot_audit",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _count_call(source: str, name: str) -> int:
    return len(re.findall(rf"(?<!def )\b{re.escape(name)}\s*\(", source))


def _line_numbers(source: str, token: str, *, limit: int = 10) -> list[int]:
    out: list[int] = []
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            out.append(index)
            if len(out) >= limit:
                break
    return out


def _decision(
    *,
    current_cta_hash: str | None,
    previous_cta_hash: str | None,
    existing_payload: bool,
    debug_mode: bool = False,
    post_click_or_apply_in_flight: bool = False,
    stale_payload: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if debug_mode:
        reasons.append("debug_mode_forces_rebuild")
    if post_click_or_apply_in_flight:
        reasons.append("post_click_or_apply_in_flight_forces_rebuild")
    if stale_payload:
        reasons.append("stale_payload_forces_rebuild")
    if not current_cta_hash:
        reasons.append("missing_current_cta_hash")
    if not previous_cta_hash:
        reasons.append("missing_previous_cta_hash")
    if current_cta_hash and previous_cta_hash and current_cta_hash != previous_cta_hash:
        reasons.append("cta_hash_changed")
    if not existing_payload:
        reasons.append("missing_existing_apply_payload")
    bypass_ready = not reasons
    return {
        "current_cta_hash": current_cta_hash,
        "previous_cta_hash": previous_cta_hash,
        "existing_payload": existing_payload,
        "debug_mode": debug_mode,
        "post_click_or_apply_in_flight": post_click_or_apply_in_flight,
        "stale_payload": stale_payload,
        "decision": "SKIP_BINDING_REBUILD_READY" if bypass_ready else "REBUILD_REQUIRED",
        "bypass_ready": bypass_ready,
        "reasons": reasons,
    }


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    input_source = "\n".join(
        [
            INPUTS_PAGE.read_text(encoding="utf-8", errors="replace"),
            APP_CONTRACT_BRIDGE.read_text(encoding="utf-8", errors="replace"),
            PRIMARY_APPLY_PAYLOAD.read_text(encoding="utf-8", errors="replace"),
            PRIMARY_APPLY_PAYLOAD_RECORDER.read_text(encoding="utf-8", errors="replace"),
        ]
    )
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
    scenarios = {
        "stable_same_cta_hash": _decision(
            current_cta_hash="cta-stable",
            previous_cta_hash="cta-stable",
            existing_payload=True,
        ),
        "changed_cta_hash": _decision(
            current_cta_hash="cta-new",
            previous_cta_hash="cta-stable",
            existing_payload=True,
        ),
        "missing_current_hash": _decision(
            current_cta_hash=None,
            previous_cta_hash="cta-stable",
            existing_payload=True,
        ),
        "missing_existing_payload": _decision(
            current_cta_hash="cta-stable",
            previous_cta_hash="cta-stable",
            existing_payload=False,
        ),
        "debug_mode": _decision(
            current_cta_hash="cta-stable",
            previous_cta_hash="cta-stable",
            existing_payload=True,
            debug_mode=True,
        ),
        "post_click_apply_in_flight": _decision(
            current_cta_hash="cta-stable",
            previous_cta_hash="cta-stable",
            existing_payload=True,
            post_click_or_apply_in_flight=True,
        ),
        "stale_payload": _decision(
            current_cta_hash="cta-stable",
            previous_cta_hash="cta-stable",
            existing_payload=True,
            stale_payload=True,
        ),
    }
    source_checks = {
        "cta_authority_constant_present": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"'
        in input_source,
        "records_primary_apply_payload": "def _record_rendered_design_guide_primary_apply_payload(" in input_source,
        "builds_primary_apply_payload": "def _build_design_guide_primary_apply_payload(" in input_source,
        "current_state_apply_guard_present": "_design_guide_apply_updates_current_state_guard" in input_source,
        "stale_payload_audit_surface_present": "stale_apply_payload_blocked" in input_source,
        "final_publication_cta_hash_present": "final_publication_cta_hash" in input_source,
        "apply_routing_remains_page_owned": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in final_source,
        "final_publication_has_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
    }
    errors: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            errors.append(f"{name}_not_passed")
    if not all(source_checks.values()):
        errors.append("source_checks_failed")
    if not scenarios["stable_same_cta_hash"]["bypass_ready"]:
        errors.append("stable_same_cta_hash_not_ready")
    for name, scenario in scenarios.items():
        if name != "stable_same_cta_hash" and scenario["bypass_ready"]:
            errors.append(f"{name}_incorrectly_ready")
    return {
        "schema": "design_guide_cta_apply_binding_bypass_readiness.v1",
        "status": "PASS" if not errors else "FAIL",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "product_behavior_changed": False,
        "ready_for_live_cta_apply_binding_churn_proof": not errors,
        "ready_for_live_bypass_implementation": False,
        "source_checks": source_checks,
        "scenarios": scenarios,
        "inventory": {
            "record_primary_apply_payload_calls": _count_call(
                input_source,
                "_record_rendered_design_guide_primary_apply_payload",
            ),
            "build_primary_apply_payload_calls": _count_call(
                input_source,
                "_build_design_guide_primary_apply_payload",
            ),
            "final_publication_cta_hash_tokens": input_source.count("final_publication_cta_hash"),
            "primary_apply_payload_lines": _line_numbers(
                input_source,
                "_record_rendered_design_guide_primary_apply_payload",
            ),
        },
        "locks": {
            name: {"path": lock.get("path"), "passed": lock.get("passed"), "found": lock.get("found")}
            for name, lock in locks.items()
        },
        "errors": errors,
        "next_slice": (
            "Create browser/live CTA/apply binding churn proof: compare stable same-CTA-hash rerun, changed hash, "
            "debug, post-click/apply-in-flight, stale payload, and missing-payload cases before implementing any bypass."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["generated_at"].replace(":", "-")
    payload["snapshot_hash"] = _stable_hash(
        {
            "scenarios": payload["scenarios"],
            "source_checks": payload["source_checks"],
            "inventory": payload["inventory"],
        }
    )
    json_path = ARTIFACT_DIR / f"design_guide_cta_apply_binding_bypass_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_cta_apply_binding_bypass_readiness_{stamp}.md"
    lines = [
        "# Design Guide CTA/Apply Binding Bypass Readiness",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"Ready for live churn proof: `{payload['ready_for_live_cta_apply_binding_churn_proof']}`",
        f"Ready for live bypass implementation: `{payload['ready_for_live_bypass_implementation']}`",
        "",
        "## Scenario Decisions",
        "",
        "| Scenario | Decision | Reasons |",
        "| --- | --- | --- |",
    ]
    for name, scenario in payload["scenarios"].items():
        lines.append(
            f"| `{name}` | `{scenario['decision']}` | `{', '.join(scenario['reasons']) or 'none'}` |"
        )
    lines.extend(["", "## Source Checks", ""])
    for key, value in payload["source_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Slice", "", payload["next_slice"]])
    if payload["errors"]:
        lines.extend(["", "## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```"])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_cta_apply_binding_bypass_readiness {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["errors"]:
        print("errors=" + json.dumps(payload["errors"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
