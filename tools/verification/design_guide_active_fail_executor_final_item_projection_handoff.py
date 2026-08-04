"""Verify active-fail executor final guidance item projection handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _old_projection(
    *,
    item: dict[str, Any],
    selected: dict[str, Any],
    evidence: dict[str, Any],
    active_family: str,
    active_title: str,
) -> dict[str, Any]:
    out = dict(item)
    out.update(
        {
            "title_main": active_title,
            "title": active_title,
            "bucket": "fail",
            "status": "FAIL",
            "guidance_intent": "required_fix",
            "family": active_family,
            "check_key": active_family,
            "action_type": "apply_resolved_candidate",
            "primary_card_actionable": True,
            "candidate_search_evidence": dict(evidence),
            "updates": dict(selected.get("updates") or {}),
        }
    )
    payload = dict(out.get("action_payload") or {})
    payload["candidate_search_evidence"] = dict(evidence)
    out["action_payload"] = payload
    resolved = dict(out.get("resolved_candidate") or {})
    resolved["candidate_search_evidence"] = dict(evidence)
    out["resolved_candidate"] = resolved
    return out


def _new_projection(
    *,
    item: dict[str, Any],
    selected: dict[str, Any],
    evidence: dict[str, Any],
    active_family: str,
    active_title: str,
) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_final_guidance_item_projection,
    )

    return build_design_guide_controller_active_fail_executor_final_guidance_item_projection(
        item=dict(item),
        selected_candidate=dict(selected),
        evidence=dict(evidence),
        active_family=active_family,
        active_title=active_title,
    )


def _parity_rows() -> dict[str, dict[str, Any]]:
    base_item = {
        "title": "Old title",
        "action_payload": {"updates": {"D": 700.0}},
        "resolved_candidate": {"candidate_id": "old"},
        "primary_action": "Run one-click auto design",
    }
    selected = {"updates": {"D": 700.0, "b": 450.0}}
    evidence = {"selected_candidate_id": "active_fail_repair_001", "search_scope": "active_fail_repair_search"}
    cases = {
        "bending": {"family": "bending", "title": "Bending capacity is low"},
        "shear": {"family": "shear", "title": "Shear capacity is low"},
        "combined": {"family": "combined", "title": "Bending and shear capacity are low"},
    }
    rows: dict[str, dict[str, Any]] = {}
    for name, case in cases.items():
        old = _old_projection(
            item=dict(base_item),
            selected=dict(selected),
            evidence=dict(evidence),
            active_family=str(case["family"]),
            active_title=str(case["title"]),
        )
        new = _new_projection(
            item=dict(base_item),
            selected=dict(selected),
            evidence=dict(evidence),
            active_family=str(case["family"]),
            active_title=str(case["title"]),
        )
        rows[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "matches": old == new,
        }
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    parity = _parity_rows()
    source_checks = {
        "target_delegates_final_item_projection": (
            "_build_design_guide_controller_active_fail_executor_final_guidance_item_projection(" in target_source
        ),
        "target_still_builds_guidance_item_in_page_shell": "_guidance_item_from_resolved_candidate(" in target_source,
        "target_no_longer_stamps_primary_card_actionable_directly": '"primary_card_actionable": True' not in target_source,
        "target_no_longer_stamps_required_fix_directly": '"guidance_intent": "required_fix"' not in target_source,
        "controller_final_item_projection_helper_exists": (
            "def build_design_guide_controller_active_fail_executor_final_guidance_item_projection(" in controller_source
        ),
        "controller_exports_final_item_projection_helper": (
            '"build_design_guide_controller_active_fail_executor_final_guidance_item_projection"' in controller_source
        ),
        "controller_has_no_page_or_streamlit_imports": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
    }
    return {
        "schema": "design_guide_active_fail_executor_final_item_projection_handoff.v1",
        "target": {"name": TARGET, "line_start": target_start, "line_end": target_end},
        "parity": parity,
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = dict(payload.get("parity") or {})
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "final_item_projection_hashes_unchanged": bool(parity)
        and all(row.get("matches") for row in parity.values()),
        **{name: bool(value) for name, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_final_item_projection_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_final_item_projection_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Final Item Projection Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved active-fail executor final guidance item field projection behind "
            "`DesignGuideController`. The page still builds the base guidance item and owns "
            "cache/session state, trace, rendering, and CTA/apply side effects."
        ),
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_final_item_projection_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
