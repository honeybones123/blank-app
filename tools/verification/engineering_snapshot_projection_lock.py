from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
SNAPSHOT_MODULE = ROOT / "application" / "engineering_snapshot.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _compile(paths: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *paths],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    return {
        "command": "python -m py_compile " + " ".join(paths),
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _imports_streamlit(path: Path) -> bool:
    tree = ast.parse(_read(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "streamlit" or alias.name.startswith("streamlit.") for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            module = str(node.module or "")
            if module == "streamlit" or module.startswith("streamlit."):
                return True
    return False


def _checks() -> dict[str, Any]:
    from application.engineering_snapshot import (
        UI_ONLY_STATE_KEYS,
        build_engineering_input_snapshot_from_resolved_state,
    )

    base = {
        "sec_shape": "RECT",
        "b": 300.0,
        "D": 450.0,
        "d": 400.0,
        "fc": 32.0,
        "fsy": 500.0,
        "Ec": 30100.0,
        "Es": 200000.0,
        "phi_bend": 0.8,
        "phi_shear": 0.7,
        "cover_bot": 40.0,
        "bot_row_count": 1,
        "bot1_layout_mode": "Count",
        "bot1_count": 3,
        "db_bot_1": 16,
        "lig_d": 10,
        "lig_legs": 2,
        "s_lig": 200.0,
        "uls_Mstar": 120.0,
        "uls_Vstar": 180.0,
        "sls_Mstar": 70.0,
        "design_optimisation_goal": "balanced",
        "optimisation_lock_geometry": False,
        "active_tab": "Summary",
        "expanded_panels": ["debug"],
        "guidance_compute_ms": 123.4,
    }
    reordered = dict(reversed(list(base.items())))
    ui_changed = {
        **base,
        "active_tab": "Diagram",
        "expanded_panels": ["debug", "trace"],
        "guidance_compute_ms": 999.9,
        "loading_flags": {"design_guide": True},
    }
    geometry_changed = {**base, "D": 475.0}
    action_changed = {**base, "uls_Mstar": 140.0}
    setting_changed = {**base, "design_optimisation_goal": "minimum_reo"}
    lock_changed = {**base, "optimisation_lock_geometry": True}
    canonical_spacing = {
        **base,
        "bot1_spacing": 200.0,
        "bot2_spacing": 200.0,
        "bot_row_1_spacing": 0.0,
        "bot_row_2_spacing": 0.0,
    }
    stale_legacy_spacing = {
        **canonical_spacing,
        "bot1_spacing": 0.0,
        "bot2_spacing": 0.0,
    }

    snapshot = build_engineering_input_snapshot_from_resolved_state(
        base,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    reordered_snapshot = build_engineering_input_snapshot_from_resolved_state(
        reordered,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    ui_snapshot = build_engineering_input_snapshot_from_resolved_state(
        ui_changed,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    geometry_snapshot = build_engineering_input_snapshot_from_resolved_state(
        geometry_changed,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    action_snapshot = build_engineering_input_snapshot_from_resolved_state(
        action_changed,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    setting_snapshot = build_engineering_input_snapshot_from_resolved_state(
        setting_changed,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    lock_snapshot = build_engineering_input_snapshot_from_resolved_state(
        lock_changed,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    canonical_spacing_snapshot = build_engineering_input_snapshot_from_resolved_state(
        canonical_spacing,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    stale_legacy_spacing_snapshot = build_engineering_input_snapshot_from_resolved_state(
        stale_legacy_spacing,
        contract_versions={"design_brain": "v1"},
        calculation_versions={"beam": "v1"},
    )
    snapshot_payload = snapshot.to_dict()
    all_snapshot_keys = set()
    for value in snapshot_payload.values():
        if isinstance(value, dict):
            all_snapshot_keys.update(value)

    return {
        "snapshot_is_engineering_input_snapshot": snapshot.__class__.__name__ == "EngineeringInputSnapshot",
        "order_stable_hash": snapshot.engineering_hash == reordered_snapshot.engineering_hash,
        "ui_only_state_excluded_from_hash": snapshot.engineering_hash == ui_snapshot.engineering_hash,
        "geometry_change_changes_hash": snapshot.engineering_hash != geometry_snapshot.engineering_hash,
        "action_change_changes_hash": snapshot.engineering_hash != action_snapshot.engineering_hash,
        "setting_change_changes_hash": snapshot.engineering_hash != setting_snapshot.engineering_hash,
        "lock_change_changes_hash": snapshot.engineering_hash != lock_snapshot.engineering_hash,
        "canonical_row_spacing_owns_legacy_alias_identity": (
            canonical_spacing_snapshot.engineering_hash
            == stale_legacy_spacing_snapshot.engineering_hash
            and canonical_spacing_snapshot.reinforcement.get("bot1_spacing") == 0.0
            and canonical_spacing_snapshot.reinforcement.get("bot2_spacing") == 0.0
        ),
        "geometry_keys_captured": {"b", "D", "sec_shape"}.issubset(snapshot.geometry),
        "material_keys_captured": {"fc", "fsy", "Ec", "Es"}.issubset(snapshot.materials),
        "reinforcement_keys_captured": {"bot1_count", "db_bot_1", "lig_d", "lig_legs", "s_lig"}.issubset(
            snapshot.reinforcement
        ),
        "resolved_design_actions_captured": {
            "Mu",
            "Vu",
            "SLS_M",
        }.issubset(dict(snapshot.design_actions.get("resolved") or {})),
        "contract_versions_captured": snapshot.contract_versions.get("design_brain") == "v1",
        "calculation_versions_captured": snapshot.calculation_versions.get("beam") == "v1",
        "ui_only_keys_absent_from_snapshot": not bool(all_snapshot_keys & set(UI_ONLY_STATE_KEYS)),
        "no_streamlit_import": not _imports_streamlit(SNAPSHOT_MODULE),
    }


def _all_pass(checks: dict[str, Any]) -> bool:
    return all(value is True for value in checks.values())


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Engineering Snapshot Projection Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This proves the committed-input projection used by the future session-owned Design Brain coordinator. It does not change live rendering, CTA, Apply, or publication behavior.",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Verification",
            "",
            f"- `{snapshot['compile']['command']}` -> `{snapshot['compile']['status']}`",
            "",
            "## Remaining Cutover",
            "",
            "- Feed the current resolved Inputs state through this projection in the live Design Guide coordinator.",
            "- Compare projected `engineering_hash` with the existing Design Guide cache fingerprint before using it as the authoritative run gate.",
            "- Prove same-hash render reruns do zero Design Brain work.",
            "",
            f"JSON: `{snapshot['artifact']}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_result = _compile(
        [
            "application/engineering_snapshot.py",
            "application/__init__.py",
            "design_brain/authority.py",
            "tools/verification/engineering_snapshot_projection_lock.py",
        ]
    )
    checks = _checks()
    status = "LOCKED" if compile_result["status"] == "PASS" and _all_pass(checks) else "FAIL"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"engineering_snapshot_projection_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"engineering_snapshot_projection_lock_{stamp}.md"
    snapshot = {
        "schema": "engineering_snapshot_projection_lock.v1",
        "status": status,
        "compile": compile_result,
        "checks": checks,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
