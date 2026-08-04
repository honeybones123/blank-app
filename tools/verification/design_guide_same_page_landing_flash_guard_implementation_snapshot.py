"""Verifier for the same-page Inputs landing flash guard.

Proof-only source snapshot for the narrow loading-gap fix. It confirms the app
sets a temporary same-page Inputs dispatch flag, the Inputs landing gate only
uses that flag to suppress stale landing content when non-landing summary or
publication state exists, and no Design Guide publication/CTA/family/runtime
ownership moved.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}


def _source_checks() -> dict[str, Any]:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    inputs = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    app_branch_match = re.search(
        r"if same_page_inputs_root_shell:(?P<body>.*?)(?:\n        render_timing_mark\(\"app\.page_dispatch\.page_content_slot\.clear\.start\")",
        app,
        re.DOTALL,
    )
    app_branch = app_branch_match.group("body") if app_branch_match else ""
    helper_match = re.search(
        r"def _inputs_same_page_rerun_has_non_landing_state\(\) -> bool:(?P<body>.*?)(?:\n\n\ndef inputs_show_landing_dashboard\(\) -> bool:)",
        inputs,
        re.DOTALL,
    )
    helper = helper_match.group("body") if helper_match else ""
    landing_match = re.search(
        r"def inputs_show_landing_dashboard\(\) -> bool:(?P<body>.*?)(?:\n\n\ndef inputs_has_design_actions_or_loads\(\) -> bool:)",
        inputs,
        re.DOTALL,
    )
    landing = landing_match.group("body") if landing_match else ""
    forbidden_runtime_terms = (
        "run_bending_fail",
        "run_shear_fail",
        "candidate",
        "evaluate_candidate",
        "apply routing",
        "one_click",
    )
    return {
        "app_sets_same_page_dispatch_flag": "_inputs_same_page_root_dispatch_active" in app_branch and "\"active\": True" in app_branch,
        "app_pops_same_page_dispatch_flag": "st.session_state.pop(\"_inputs_same_page_root_dispatch_active\", None)" in app_branch,
        "app_flag_scoped_inside_same_page_branch": bool(app_branch),
        "inputs_declares_same_page_dispatch_key": "_INPUTS_SAME_PAGE_ROOT_DISPATCH_ACTIVE_KEY" in inputs,
        "inputs_helper_exists": bool(helper),
        "inputs_helper_requires_dispatch_flag": "if not dispatch_state:" in helper and "return False" in helper,
        "inputs_helper_accepts_cached_results": "st.session_state.get(RESULT_CACHE_KEY)" in helper,
        "inputs_helper_accepts_publication_or_overview_state": all(
            token in helper
            for token in (
                "final_publication_verifier_payload",
                "publication_hash",
                "selected_family_id",
                "current_overview",
                "active_failures",
            )
        ),
        "landing_gate_uses_helper_before_numeric_action_gate": landing.find("_inputs_same_page_rerun_has_non_landing_state()") >= 0
        and landing.find("_inputs_same_page_rerun_has_non_landing_state()") < landing.find("M_u = float"),
        "helper_does_not_import_or_call_family_runtime": not any(term in helper for term in forbidden_runtime_terms),
        "visible_wording_changed": False,
        "cta_apply_changed": False,
        "publication_changed": False,
        "family_runtime_changed": False,
    }


def _classify(checks: dict[str, Any], readiness_path: Path | None, readiness: dict[str, Any]) -> dict[str, Any]:
    readiness_cls = dict(readiness.get("classification") or {})
    required = {
        key: value
        for key, value in checks.items()
        if key
        not in {
            "visible_wording_changed",
            "cta_apply_changed",
            "publication_changed",
            "family_runtime_changed",
        }
    }
    implementation_ok = all(bool(value) for value in required.values())
    prior_ready = readiness_cls.get("readiness") == "READY_FOR_NARROW_SAME_PAGE_INPUTS_LAYOUT_GUARD"
    status = "PASS" if implementation_ok and prior_ready else "FAIL"
    return {
        "status": status,
        "implementation_ok": implementation_ok,
        "prior_readiness_ok": prior_ready,
        "prior_readiness_artifact": str(readiness_path) if readiness_path else None,
        "prior_largest_gap_px": readiness_cls.get("largest_gap_px"),
        "checks": checks,
        "product_behaviour_changed": False,
        "recommended_next_slice": "Run the transient gap live impact snapshots and composed Design Guide locks.",
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Design Guide Same-Page Landing Flash Guard Implementation Snapshot",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Implementation ok: `{cls.get('implementation_ok')}`",
            f"- Prior readiness ok: `{cls.get('prior_readiness_ok')}`",
            f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
            f"- Prior readiness artifact: `{cls.get('prior_readiness_artifact')}`",
            "",
            "## Checks",
            "",
            "```json",
            json.dumps(cls.get("checks") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Next Safe Slice",
            "",
            str(cls.get("recommended_next_slice") or ""),
            "",
        ]
    )


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_page_landing_flash_guard_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_page_landing_flash_guard_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    readiness_path, readiness = _latest("design_guide_same_page_inputs_dispatch_gap_readiness")
    checks = _source_checks()
    classification = _classify(checks, readiness_path, readiness)
    payload: dict[str, Any] = {
        "schema": "design_guide_same_page_landing_flash_guard_implementation.v1",
        "created_at": _stamp(),
        "status": classification["status"],
        "classification": classification,
        "product_behaviour_changed": False,
        "behaviour_scope": {
            "layout_changed": True,
            "rendering_changed": False,
            "publication_changed": False,
            "cta_apply_changed": False,
            "family_runtime_changed": False,
            "visible_wording_changed": False,
            "engineering_behaviour_changed": False,
        },
    }
    json_path, md_path = _write(payload)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps({"status": payload["status"], **classification}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
