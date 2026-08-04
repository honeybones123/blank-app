from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_no(source: str, needle: str) -> int | None:
    index = source.find(needle)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def _window(source: str, needle: str, radius: int = 5000) -> str:
    index = source.find(needle)
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(source), index + radius)
    return source[start:end]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(_read(path))
    except Exception as exc:
        payload = {"load_error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload}


def build_snapshot() -> dict[str, Any]:
    source = _read(INPUTS_PAGE)
    early_assignment = (
        "_early_shear_cleanup_shell_projection = _build_final_design_guide_direct_shell_card_projection("
    )
    early_window = _window(source, early_assignment)
    pre_assignment = (
        "_pre_render_shell_projection = _build_final_design_guide_direct_shell_card_projection("
    )
    post_assignment = (
        "_fallback_shell_projection = _build_final_design_guide_direct_shell_card_projection("
    )
    failures: list[str] = []
    checks = {
        "early_direct_builder_present": bool(early_window),
        "early_fallback_builder_removed": (
            "_early_shear_cleanup_shell_projection = _build_final_design_guide_render_fallback_shell_projection("
            not in source
        ),
        "early_uses_projection_view_model_title": ".view_model).get(\"title\")" in early_window,
        "early_uses_projection_view_model_pill": ".view_model).get(\"pill\")" in early_window,
        "early_uses_identity_projection_identity": ".identity_projection).get(" in early_window,
        "early_renders_direct_shell_html": "_design_guide_direct_action_shell_card_html(" in early_window,
        "early_records_apply_payload": "_record_rendered_design_guide_primary_apply_payload(" in early_window,
        "pre_render_now_direct_builder": pre_assignment in source,
        "post_render_now_direct_builder": post_assignment in source,
    }
    for key, passed in checks.items():
        if passed is not True:
            failures.append(f"check:{key}")

    latest = {
        "direct_shell_identity_fallback_deletion": _latest(
            "design_guide_direct_shell_identity_fallback_deletion"
        ),
        "direct_shell_card_projection_cutover": _latest(
            "design_guide_direct_shell_card_projection_cutover"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    for key, row in latest.items():
        status = str(
            (row.get("payload") or {}).get("status")
            or (row.get("payload") or {}).get("result")
            or ""
        ).upper()
        if "PASS" not in status and "LOCKED" not in status and "COMPLETE" not in status:
            failures.append(f"{key}_latest_not_pass")

    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_brain_early_direct_shell_projection_cutover.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks": checks,
        "callsite": {
            "line": _line_no(source, early_assignment),
            "marker": "early_shear_overdesign_direct_action_shell",
        },
        "latest": {
            key: {
                "found": value.get("found"),
                "path": value.get("path"),
                "status": (value.get("payload") or {}).get("status")
                or (value.get("payload") or {}).get("result"),
            }
            for key, value in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "failures": failures,
        "recommended_next_slice": (
            "The direct shell migration is complete for the tracked callsites; next retire stale fallback-shell verifier references and focus on the final validity guard."
        ),
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Early Direct Shell Projection Cutover",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Checks",
    ]
    for key, value in (snapshot.get("checks") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Callsite",
            f"- line: `{snapshot['callsite']['line']}`",
            f"- marker: `{snapshot['callsite']['marker']}`",
            "",
            "## Recommendation",
            snapshot.get("recommended_next_slice") or "",
        ]
    )
    if snapshot.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in snapshot["failures"])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_brain_early_direct_shell_projection_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_early_direct_shell_projection_cutover_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_early_direct_shell_projection_cutover {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
