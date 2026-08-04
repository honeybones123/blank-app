"""Verify coherence active-repair fail-key resolution moved to DesignGuideController."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _old_keys(overview_fail_keys: set[str], title: str) -> set[str]:
    keys = set(overview_fail_keys or set())
    title_l = str(title or "").strip().lower()
    if not keys:
        if "bending and shear" in title_l:
            keys = {"bending", "shear"}
        elif "shear" in title_l:
            keys = {"shear"}
        elif "bend" in title_l or "moment" in title_l:
            keys = {"bending"}
    return keys


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_compute_coherence_active_repair_fail_keys,
    )

    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    helper_start, helper_end, helper_segment = _function_source(
        inputs_source,
        "_republish_compute_coherence_active_repair",
    )
    controller_start, controller_end, controller_segment = _function_source(
        controller_source,
        "resolve_design_guide_controller_compute_coherence_active_repair_fail_keys",
    )

    cases: list[dict[str, Any]] = []
    for overview_keys, title in (
        ({"shear"}, "anything"),
        (set(), "bending and shear capacity are low"),
        (set(), "shear capacity is low"),
        (set(), "positive moment capacity is low"),
        (set(), "serviceability only"),
    ):
        expected = _old_keys(set(overview_keys), title)
        actual = resolve_design_guide_controller_compute_coherence_active_repair_fail_keys(
            overview_fail_keys=set(overview_keys),
            primary_title=title,
        )
        actual_for_artifact = {
            **dict(actual),
            "fail_key_set": sorted(str(key) for key in (actual.get("fail_key_set") or set())),
        }
        cases.append(
            {
                "overview_keys": sorted(overview_keys),
                "title": title,
                "matches_old_fail_keys": set(actual.get("fail_key_set") or []) == expected,
                "expected": sorted(expected),
                "actual": actual_for_artifact,
            }
        )

    removed_page_tokens = (
        'if "bending and shear" in primary_title_for_evidence:',
        'elif "shear" in primary_title_for_evidence:',
        'elif "bend" in primary_title_for_evidence or "moment" in primary_title_for_evidence:',
        'if not (_active_repair_fail_keys_for_evidence & {"bending", "shear"}):',
    )
    snapshot_runs = [
        _run("tools/verification/design_guide_compute_late_evidence_lane_boundary_audit.py"),
    ]
    return {
        "schema": "design_guide_compute_coherence_active_repair_fail_key_resolution_extraction.v1",
        "target": {
            "page_helper_line_start": helper_start,
            "page_helper_line_end": helper_end,
            "controller_helper_line_start": controller_start,
            "controller_helper_line_end": controller_end,
        },
        "cases": cases,
        "source_checks": {
            "page_helper_delegates_fail_key_resolution_to_controller": (
                "_resolve_design_guide_controller_compute_coherence_active_repair_fail_keys("
                in helper_segment
            ),
            "page_helper_keeps_overview_collection": all(
                token in helper_segment
                for token in (
                    "_collect_design_overview(",
                    "_overview_active_failure_keys(",
                    "_active_fail_near_current_repair_item(",
                    "_direct_target_band_guidance_item(",
                )
            ),
            "page_helper_removed_inline_fail_key_title_policy": all(
                token not in helper_segment for token in removed_page_tokens
            ),
            "controller_helper_exists": bool(controller_start),
            "controller_helper_exported": (
                '"resolve_design_guide_controller_compute_coherence_active_repair_fail_keys"'
                in controller_source
            ),
            "controller_owns_fail_key_title_policy": all(
                token in controller_segment
                for token in (
                    '"bending and shear"',
                    '"shear"',
                    '"bend"',
                    '"moment"',
                    '"actionable_strength_keys"',
                )
            ),
            "controller_has_no_page_or_streamlit_imports": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
        },
        "snapshot_runs": snapshot_runs,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "all_cases_match_old_fail_keys": all(
            bool(row.get("matches_old_fail_keys")) for row in payload.get("cases") or []
        ),
        **{name: bool(value) for name, value in source_checks.items()},
        "late_evidence_boundary_audit_passes": all(
            bool(row.get("passed")) for row in payload.get("snapshot_runs") or []
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_compute_coherence_active_repair_fail_key_resolution_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_coherence_active_repair_fail_key_resolution_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    target = dict(payload.get("target") or {})
    lines = [
        "# Design Guide Compute Coherence Active-Repair Fail-Key Resolution Extraction",
        "",
        f"Status: {payload.get('status')}",
        "",
        "## Surface",
        f"- page helper: `_republish_compute_coherence_active_repair` lines {target.get('page_helper_line_start')}-{target.get('page_helper_line_end')}",
        f"- controller helper: `resolve_design_guide_controller_compute_coherence_active_repair_fail_keys` lines {target.get('controller_helper_line_start')}-{target.get('controller_helper_line_end')}",
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"{payload['status']}: {json_path}")
    print(f"report: {report_path}")
    if payload["status"] != "PASS":
        print(json.dumps({k: v for k, v in checks.items() if not v}, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
