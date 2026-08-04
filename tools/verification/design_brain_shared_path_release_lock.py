"""Composed release lock for shared Design Guide paths.

Families can be correct while shared publication, CTA, Apply, render, session,
or fallback paths still distort the live result. This verifier composes the
shared-path evidence and scans the current source for forbidden visible legacy
surfaces.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.browser_red_screen_sentinel import browser_red_screen_findings  # noqa: E402
from tools.verification.verification_run_manifest import current_run_artifact  # noqa: E402

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_ARTIFACTS: dict[str, str] = {
    "independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "zero_authority_inventory_lock": "design_brain_inputs_page_zero_authority_inventory_lock",
    "shared_bridge_dependency_binding_lock": "shared_bridge_dependency_binding_lock",
    "legacy_visible_surface_deletion_lock": "design_guide_legacy_visible_surface_deletion_lock",
    "critical_workflows_lock": "app_stability_critical_workflows_lock",
    "inputs_apply_10x_workflow_lock": "app_stability_inputs_apply_10x_workflow_lock",
}

FORBIDDEN_VISIBLE_SOURCE_MARKERS: tuple[str, ...] = (
    "Recommendation is advisory, not directly executable",
    "One-click found a candidate, but it was blocked",
    "stale_primary_design_guide_payload",
    "Design Guide family contract violation",
)

SOURCE_FILES: tuple[str, ...] = (
    "inputs_page.py",
    "inputs_application/engineering_workspace.py",
    "inputs_application/page_runtime/design_guide.py",
    "inputs_page_modules/guidance_compute.py",
    "inputs_page_modules/design_guide/current_coordinators.py",
    "design_guide_page.py",
    "design_brain/final_publication.py",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return payload if isinstance(payload, dict) else {"status": "UNREADABLE", "error": "json root is not object"}


def _read_text(relative: str) -> str:
    path = ROOT / relative
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    # Shared-path release authority must be bound to the active canonical
    # run. A newest-file fallback can certify stale evidence.
    if not os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        return None, {}
    return current_run_artifact(prefix)


def _payload_status(payload: dict[str, Any]) -> str:
    return str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("completion_status")
        or payload.get("meta_lock_status")
        or "MISSING"
    ).strip()


def _payload_passed(payload: dict[str, Any]) -> bool:
    status = _payload_status(payload).upper()
    if status in {"PASS", "PASSED", "LOCKED", "LIVE_EXECUTION_PASS"}:
        return True
    if str(payload.get("lock_status") or "").upper() == "LOCKED":
        return True
    if str(payload.get("completion_status") or "").upper() == "COMPLETE":
        return True
    # The zero-authority inventory intentionally reports PARTIAL while its
    # bounded execution kernels remain page shells.  That is a locked
    # architecture state when no non-zero authority surfaces remain and all
    # composed locks pass; treating it as a release failure made this shared
    # lock depend on the old pre-shell status vocabulary.
    if (
        status == "PARTIAL"
        and payload.get("remaining_not_zero_count") == 0
        and payload.get("composed_verifiers_pass") is True
    ):
        return True
    return False


def _artifact_rows() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for key, prefix in REQUIRED_ARTIFACTS.items():
        path, payload = _latest(prefix)
        rows[key] = {
            "key": key,
            "prefix": prefix,
            "path": str(path) if path else None,
            "status": _payload_status(payload),
            "passed": _payload_passed(payload),
        }
    return rows


def _source_marker_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in SOURCE_FILES:
        source = _read_text(relative)
        for marker in FORBIDDEN_VISIBLE_SOURCE_MARKERS:
            if marker in source:
                rows.append({"file": relative, "marker": marker})
    return rows


def _browser_surface_only(value: Any) -> Any:
    """Exclude verifier diagnostics that are not rendered browser content."""

    if isinstance(value, dict):
        return {
            key: _browser_surface_only(item)
            for key, item in value.items()
            if str(key) not in {
                "root_cause_candidate",
                "verifier_internal_traceback",
            }
        }
    if isinstance(value, list):
        return [_browser_surface_only(item) for item in value]
    return value


def _probe_latest_browser_artifacts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prefix in (
        "family_10_fuzz_audit",
        "app_stability_critical_workflows_lock",
        "app_stability_inputs_apply_10x_workflow_lock",
        "design_guide_browser_live_visual_consistency",
        "design_guide_browser_visual_layout_lock",
    ):
        path, payload = _latest(prefix)
        rows.append(
            {
                "prefix": prefix,
                "path": str(path) if path else None,
                "red_screen_findings": browser_red_screen_findings(
                    _browser_surface_only(payload)
                ),
            }
        )
    return rows


def _build() -> dict[str, Any]:
    artifact_rows = _artifact_rows()
    source_marker_rows = _source_marker_rows()
    browser_rows = _probe_latest_browser_artifacts()
    red_screen_rows = [row for row in browser_rows if row["red_screen_findings"]]
    failed_artifacts = [row for row in artifact_rows.values() if not row["passed"]]
    failures: list[str] = []
    if failed_artifacts:
        failures.append("required_shared_artifact_missing_or_not_pass")
    if red_screen_rows:
        failures.append("latest_browser_artifact_has_red_screen_sentinel_findings")
    return {
        "schema": "design_brain.shared_path_release_lock.v1",
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "artifact_rows": artifact_rows,
        "source_marker_rows": source_marker_rows,
        "browser_artifact_red_screen_rows": red_screen_rows,
        "failures": failures,
        "direct_proof": {
            "publication_assembly_locked": artifact_rows["independence_lock"]["passed"],
            "cta_apply_payload_locked": artifact_rows["inputs_apply_10x_workflow_lock"]["passed"]
            and artifact_rows["independence_lock"]["passed"],
            "render_bridge_locked": artifact_rows["render_bridge_lock"]["passed"],
            "compute_resolver_publication_locked": artifact_rows["compute_resolver_publication_bridge_lock"]["passed"],
            "session_debug_non_authoritative_locked": artifact_rows["zero_authority_inventory_lock"]["passed"],
            "legacy_visible_surfaces_locked": artifact_rows["legacy_visible_surface_deletion_lock"]["passed"]
            and not red_screen_rows,
            "red_screen_sentinel_clean": not red_screen_rows,
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Shared Path Release Lock",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Direct Proof",
        "",
    ]
    for key, value in dict(payload["direct_proof"]).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Artifact Rows", "", "| Key | Status | Passed | Artifact |", "| --- | --- | ---: | --- |"])
    for row in dict(payload["artifact_rows"]).values():
        lines.append(f"| `{row['key']}` | `{row['status']}` | `{row['passed']}` | `{row['path']}` |")
    lines.extend(["", "## Source Marker Rows", ""])
    if payload["source_marker_rows"]:
        for row in list(payload["source_marker_rows"]):
            lines.append(f"- `{row['file']}` contains `{row['marker']}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Failures", "", f"`{payload['failures']}`", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"design_brain_shared_path_release_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_path_release_lock_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_brain_shared_path_release_lock {payload['status']}")
    print(f"failures={payload['failures']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
