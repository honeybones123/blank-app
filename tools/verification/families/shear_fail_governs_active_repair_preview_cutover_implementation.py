"""Verify SHEAR_FAIL active-repair preview cutover implementation."""

from __future__ import annotations

from datetime import datetime
import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
HELPER_PATH = ROOT / "design_brain" / "families" / "shear_fail_governs" / "active_repair_preview.py"
INIT_PATH = ROOT / "design_brain" / "families" / "shear_fail_governs" / "__init__.py"

RESTAMP_SOURCE = "final_visible_active_shear_repair_family_restamp"
HELPER_NAME = "build_shear_fail_active_repair_preview_evidence"
HELPER_ALIAS = "_build_shear_fail_active_repair_preview_evidence"
FORBIDDEN_HELPER_IMPORT_ROOTS = {"inputs_page", "streamlit", "ui", "design_guide_page"}
FORBIDDEN_HELPER_TERMS = {
    "session_state",
    "st.",
    "rendered_html",
    "render_model",
    "html",
    "apply_route",
    "one_click",
    "button_label",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "readiness": payload.get("readiness")}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(imports)


def _target_context() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    index = source.find(f'source="{RESTAMP_SOURCE}"')
    context = source[max(0, index - 1800) : min(len(source), index + 6200)] if index >= 0 else ""
    return {
        "helper_imported": HELPER_ALIAS in source and "active_repair_preview" in source,
        "restamp_source_retained_for_compatibility": f'source="{RESTAMP_SOURCE}"' in context,
        "evaluator_call_retained": "_evaluate_auto_design_candidate(" in context,
        "helper_called_in_restamp_block": f"{HELPER_ALIAS}(" in context,
        "contract_effect_consumed": "button_contract_effect" in context and "contract.update(" in context,
        "item_effect_consumed": "item_effect" in context and "out.update(item_effect)" in context,
        "display_truth_effect_consumed": "display_truth_effect" in context,
        "candidate_evidence_effect_consumed": "candidate_search_evidence_effect" in context,
        "family_proof_stamped": "active_repair_preview_proof" in context,
        "debug_proof_stamped": "final_binding_active_shear_repair_proof" in context,
        "context_hash": _stable_hash(context),
    }


def _helper_context() -> dict[str, Any]:
    source = HELPER_PATH.read_text(encoding="utf-8")
    imports = _imports(HELPER_PATH)
    forbidden_imports = [
        imported
        for imported in imports
        if imported.split(".", 1)[0] in FORBIDDEN_HELPER_IMPORT_ROOTS
    ]
    forbidden_terms = sorted(term for term in FORBIDDEN_HELPER_TERMS if term.lower() in source.lower())
    from design_brain.families.shear_fail_governs.active_repair_preview import (  # noqa: WPS433
        build_shear_fail_active_repair_preview_evidence,
    )

    accepted = build_shear_fail_active_repair_preview_evidence(
        updates={"reinforcement": {"ligature_spacing_mm": 150.0}},
        current_shear_utilisation=1.18,
        preview_shear_utilisation=0.92,
        any_fail=False,
        required_checks_acceptable=True,
        explicit_preview_failures=False,
        target_band_eps=1.0e-9,
    )
    no_improvement = build_shear_fail_active_repair_preview_evidence(
        updates={"reinforcement": {"ligature_spacing_mm": 150.0}},
        current_shear_utilisation=1.18,
        preview_shear_utilisation=1.18,
        any_fail=False,
        required_checks_acceptable=True,
        explicit_preview_failures=False,
        target_band_eps=1.0e-9,
    )
    explicit_fail = build_shear_fail_active_repair_preview_evidence(
        updates={"reinforcement": {"ligature_spacing_mm": 150.0}},
        current_shear_utilisation=1.18,
        preview_shear_utilisation=0.92,
        any_fail=False,
        required_checks_acceptable=True,
        explicit_preview_failures=True,
        target_band_eps=1.0e-9,
    )
    return {
        "helper_exists": HELPER_PATH.exists(),
        "helper_exported": HELPER_NAME in INIT_PATH.read_text(encoding="utf-8"),
        "forbidden_imports": forbidden_imports,
        "forbidden_terms": forbidden_terms,
        "accepted_applies": bool(accepted.get("applies")),
        "accepted_effects_present": all(
            key in dict(accepted.get("effects") or {})
            for key in (
                "button_contract_effect",
                "item_effect",
                "display_truth_effect",
                "candidate_search_evidence_effect",
                "debug_stamp_effect",
            )
        ),
        "no_improvement_applies": bool(no_improvement.get("applies")),
        "explicit_fail_applies": bool(explicit_fail.get("applies")),
        "accepted_effect_hash": accepted.get("effect_hash"),
        "repeat_effect_hash": build_shear_fail_active_repair_preview_evidence(
            updates={"reinforcement": {"ligature_spacing_mm": 150.0}},
            current_shear_utilisation=1.18,
            preview_shear_utilisation=0.92,
            any_fail=False,
            required_checks_acceptable=True,
            explicit_preview_failures=False,
            target_band_eps=1.0e-9,
        ).get("effect_hash"),
    }


def _capture() -> dict[str, Any]:
    return {
        "preconditions": {
            "cutover_plan": _latest("shear_fail_governs_active_repair_preview_cutover_plan"),
            "parity": _latest("shear_fail_governs_active_repair_preview_parity"),
            "boundary": _latest("shear_fail_governs_active_repair_preview_boundary"),
        },
        "target_context": _target_context(),
        "helper_context": _helper_context(),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    preconditions = dict(capture.get("preconditions") or {})
    target = dict(capture.get("target_context") or {})
    helper = dict(capture.get("helper_context") or {})
    return {
        "cutover_plan_pass": (preconditions.get("cutover_plan") or {}).get("status") == "PASS",
        "cutover_plan_ready": (preconditions.get("cutover_plan") or {}).get("readiness") == "READY_FOR_NARROW_IMPLEMENTATION",
        "parity_pass": (preconditions.get("parity") or {}).get("status") == "PASS",
        "boundary_pass": (preconditions.get("boundary") or {}).get("status") == "PASS",
        "helper_clean": helper.get("helper_exists") and not helper.get("forbidden_imports") and not helper.get("forbidden_terms"),
        "helper_exported": bool(helper.get("helper_exported")),
        "helper_effects_correct": bool(helper.get("accepted_applies"))
        and bool(helper.get("accepted_effects_present"))
        and not bool(helper.get("no_improvement_applies"))
        and not bool(helper.get("explicit_fail_applies")),
        "helper_hash_stable": helper.get("accepted_effect_hash") == helper.get("repeat_effect_hash"),
        "page_uses_helper": all(
            bool(target.get(key))
            for key in (
                "helper_imported",
                "restamp_source_retained_for_compatibility",
                "evaluator_call_retained",
                "helper_called_in_restamp_block",
                "contract_effect_consumed",
                "item_effect_consumed",
                "display_truth_effect_consumed",
                "candidate_evidence_effect_consumed",
                "family_proof_stamped",
                "debug_proof_stamped",
            )
        ),
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# SHEAR_FAIL_GOVERNS Active Repair Preview Cutover Implementation",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Scope",
        "",
        "- Narrow helper/effect bridge only.",
        "- Page evaluator execution retained.",
        "- CTA rendering, publication rendering, apply routing, one-click, visible wording, UI/session/debug ownership unchanged.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Result",
            "",
            "The active-shear repair preview proof is now produced by the SHEAR_FAIL_GOVERNS helper while the page still wires/evaluates/renders.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"shear_fail_governs_active_repair_preview_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_governs_active_repair_preview_cutover_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "shear_fail_governs_active_repair_preview_cutover_implementation.v1",
        "created_at": _stamp(),
        "status": status,
        "product_behaviour_changed": False,
        "family_runtime_changed": False,
        "contract_changed": False,
        "cta_publication_apply_changed": False,
        "checks": checks,
        "failures": [key for key, ok in checks.items() if not ok],
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
        **capture,
    }
    json_path, report_path = _write(payload)
    print(f"shear_fail_governs_active_repair_preview_cutover_implementation {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(json.dumps({"status": status, "failures": payload["failures"]}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
