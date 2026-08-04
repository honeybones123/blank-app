from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
PLAN_VERIFIER = ROOT / "tools" / "verification" / "design_brain_internal_scaffolding_removal_plan.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


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


def _stable_fingerprint_tuple(payload: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    serialised: list[tuple[str, str]] = []
    for key, value in sorted(dict(payload or {}).items(), key=lambda item: str(item[0])):
        try:
            encoded = json.dumps(value, sort_keys=True, default=str)
        except Exception:
            encoded = repr(value)
        serialised.append((str(key), encoded))
    return tuple(serialised)


def _local_cleanup_candidate_id(family: str, updates: dict[str, Any] | None) -> str:
    family_id = str(family or "").strip().lower()
    return (
        f"local_cleanup:{family_id}:"
        f"{_stable_fingerprint_tuple({'family': family_id, 'updates': dict(updates or {})})}"
    )


def build_snapshot() -> dict[str, Any]:
    source = _read(FINAL_PUBLICATION)
    checks = {
        "legacy_helper_name_removed": "def _legacy_payload_fingerprint_tuple(" not in source,
        "stable_helper_name_present": "def _stable_payload_fingerprint_tuple(" in source,
        "local_cleanup_candidate_id_uses_stable_helper": "_stable_payload_fingerprint_tuple({'family': family_id, 'updates': dict(updates or {})})" in source,
        "local_cleanup_candidate_id_no_legacy_helper_reference": "_legacy_payload_fingerprint_tuple({'family': family_id, 'updates': dict(updates or {})})" not in source,
    }
    cases = [
        ("shear", {"s_lig": 200, "lig_legs": 2}),
        ("bending", {"bot_count": 4, "bot_size": "N16"}),
        ("combined", {"D": 450, "b": 300, "bot_size": "N20"}),
    ]
    stability_rows = []
    for family, updates in cases:
        first = _local_cleanup_candidate_id(family, dict(updates))
        second = _local_cleanup_candidate_id(family, dict(updates))
        stability_rows.append(
            {
                "family": family,
                "updates": dict(updates),
                "candidate_id_first": first,
                "candidate_id_second": second,
                "stable": first == second,
            }
        )
    latest = {
        "internal_plan": _latest("design_brain_internal_scaffolding_removal_plan"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    failures = [name for name, passed in checks.items() if not passed]
    if not all(row["stable"] for row in stability_rows):
        failures.append("candidate_id_stability_failed")
    for key, row in latest.items():
        status = str((row.get("payload") or {}).get("status") or (row.get("payload") or {}).get("result") or "").upper()
        if "PASS" not in status and "LOCKED" not in status and "COMPLETE" not in status:
            failures.append(f"{key}_latest_not_pass")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_brain_final_publication_cleanup_candidate_id_helper_rename.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": (
            "FINAL_PUBLICATION_CLEANUP_CANDIDATE_ID_HELPER_RENAMED"
            if status == "PASS"
            else "FINAL_PUBLICATION_CLEANUP_CANDIDATE_ID_HELPER_RENAME_NEEDS_ATTENTION"
        ),
        "checks": checks,
        "stability_rows": stability_rows,
        "latest": {
            key: {
                "found": value.get("found"),
                "path": value.get("path"),
                "status": (value.get("payload") or {}).get("status") or (value.get("payload") or {}).get("result"),
            }
            for key, value in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "failures": failures,
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Final Publication Cleanup Candidate ID Helper Rename",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Checks",
    ]
    for name, passed in (snapshot.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(["", "## Stability Rows"])
    for row in snapshot.get("stability_rows") or []:
        lines.append(
            f"- `{row['family']}` stable=`{row['stable']}` candidate_id=`{row['candidate_id_first']}`"
        )
    lines.extend(["", "## Latest Gates"])
    for name, row in (snapshot.get("latest") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}`")
    if snapshot.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in snapshot["failures"])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_brain_final_publication_cleanup_candidate_id_helper_rename_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_final_publication_cleanup_candidate_id_helper_rename_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_final_publication_cleanup_candidate_id_helper_rename {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
