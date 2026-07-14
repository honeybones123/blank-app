from __future__ import annotations

import ast
import json
import sys
import time
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER_PATH = ROOT / "design_brain" / "design_guide_controller.py"
INPUTS_PAGE_PATH = ROOT / "inputs_page.py"

FORBIDDEN_IMPORTS = {
    "inputs_page",
    "streamlit",
    "st",
}

REQUIRED_REQUEST_FIELDS = {
    "item",
    "debug",
    "design_brain_result",
    "verifier_payload",
    "final_visible_resolution",
    "guidance_debug",
    "publication_reason",
    "source",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _module_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return sorted(set(imports))


def _forbidden_import_hits(imports: list[str]) -> list[str]:
    hits: list[str] = []
    for name in imports:
        root = str(name or "").split(".", 1)[0]
        if root in FORBIDDEN_IMPORTS or name in FORBIDDEN_IMPORTS:
            hits.append(name)
    return sorted(set(hits))


def _request_shape_checks() -> dict[str, Any]:
    from design_brain.design_guide_controller import DesignGuideControllerRequest

    request_fields = {field.name: field for field in fields(DesignGuideControllerRequest)}
    missing = sorted(REQUIRED_REQUEST_FIELDS - set(request_fields))
    extra = sorted(set(request_fields) - REQUIRED_REQUEST_FIELDS)
    dict_default_fields = {
        name
        for name, field in request_fields.items()
        if name in {
            "item",
            "debug",
            "design_brain_result",
            "verifier_payload",
            "final_visible_resolution",
            "guidance_debug",
        }
        and getattr(field.default_factory, "__name__", "") == "dict"
    }
    return {
        "is_dataclass": is_dataclass(DesignGuideControllerRequest),
        "frozen": bool(getattr(DesignGuideControllerRequest, "__dataclass_params__").frozen),
        "required_fields_present": not missing,
        "missing_fields": missing,
        "extra_fields": extra,
        "dict_default_fields": sorted(dict_default_fields),
        "dict_defaults_ok": dict_default_fields
        == {
            "item",
            "debug",
            "design_brain_result",
            "verifier_payload",
            "final_visible_resolution",
            "guidance_debug",
        },
    }


def _hash_contract_checks() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        DesignGuideControllerRequest,
        design_guide_controller_request_memo_payload,
        stable_design_guide_controller_request_hash,
    )

    base = DesignGuideControllerRequest(
        item={
            "selected_family_id": "BENDING_FAIL_GOVERNS",
            "status": "FAIL",
            "button_contract": {"enabled": True, "action_type": "apply_resolved_candidate"},
        },
        debug={
            "button_contract": {"enabled": True, "action_type": "apply_resolved_candidate"},
            "noise": "ignored",
            "generated_at": "2026-07-10T00:00:00",
        },
        verifier_payload={
            "controller_hash": "aaa",
            "generated_at": "2026-07-10T00:00:00",
            "proof_hash": "aaa",
        },
        guidance_debug={
            "button_contract": {"enabled": True, "action_type": "apply_resolved_candidate"},
            "memo_cache_hit": False,
        },
        source="unit_controller_input_snapshot_lock",
    )
    proof_churn = DesignGuideControllerRequest(
        item=dict(base.item),
        debug={
            "button_contract": {"enabled": True, "action_type": "apply_resolved_candidate"},
            "noise": "different ignored value",
            "generated_at": "2026-07-10T01:00:00",
        },
        verifier_payload={
            "controller_hash": "bbb",
            "generated_at": "2026-07-10T01:00:00",
            "proof_hash": "bbb",
        },
        guidance_debug={
            "button_contract": {"enabled": True, "action_type": "apply_resolved_candidate"},
            "memo_cache_hit": True,
        },
        source="unit_controller_input_snapshot_lock",
    )
    product_change = DesignGuideControllerRequest(
        item={**base.item, "status": "PASS"},
        debug=dict(base.debug),
        verifier_payload=dict(base.verifier_payload),
        guidance_debug=dict(base.guidance_debug),
        source="unit_controller_input_snapshot_lock",
    )
    debug_product_change = DesignGuideControllerRequest(
        item=dict(base.item),
        debug={"button_contract": {"enabled": False, "action_type": "apply_resolved_candidate"}},
        verifier_payload=dict(base.verifier_payload),
        guidance_debug=dict(base.guidance_debug),
        source="unit_controller_input_snapshot_lock",
    )
    base_hash = stable_design_guide_controller_request_hash(base)
    proof_churn_hash = stable_design_guide_controller_request_hash(proof_churn)
    product_change_hash = stable_design_guide_controller_request_hash(product_change)
    debug_product_change_hash = stable_design_guide_controller_request_hash(debug_product_change)
    memo_payload = design_guide_controller_request_memo_payload(base)
    return {
        "base_hash": base_hash,
        "proof_churn_hash": proof_churn_hash,
        "product_change_hash": product_change_hash,
        "debug_product_change_hash": debug_product_change_hash,
        "proof_churn_excluded": base_hash == proof_churn_hash,
        "product_change_detected": base_hash != product_change_hash,
        "debug_product_change_detected": base_hash != debug_product_change_hash,
        "memo_owner": memo_payload.get("memo_owner"),
        "memo_key_contract": memo_payload.get("memo_key_contract"),
    }


def _inputs_page_controller_request_calls() -> dict[str, Any]:
    source = _read(INPUTS_PAGE_PATH)
    call_count = source.count("_DesignGuideControllerRequest(")
    return {
        "request_constructor_alias": "_DesignGuideControllerRequest",
        "call_count": call_count,
        "has_calls": call_count > 0,
        "imports_request_alias": "DesignGuideControllerRequest as _DesignGuideControllerRequest" in source,
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Controller Input Snapshot Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Ownership",
        "",
        "- Owner: `design_brain.design_guide_controller.DesignGuideControllerRequest`",
        "- Inputs page role: construct plain request dictionaries and call controller APIs.",
        "- Forbidden: Streamlit/session/UI/apply routing imports into the controller input snapshot.",
        "",
        "## Checks",
        "",
        f"- request shape: `{snapshot['checks']['request_shape']}`",
        f"- controller import boundary: `{snapshot['checks']['controller_import_boundary']}`",
        f"- memo hash proof-churn exclusion: `{snapshot['checks']['proof_churn_excluded']}`",
        f"- memo hash product-change detection: `{snapshot['checks']['product_change_detected']}`",
        f"- inputs_page request callsites present: `{snapshot['checks']['inputs_page_request_calls_present']}`",
        "",
        "## Artifacts",
        "",
        f"- JSON: `{snapshot['artifact']}`",
        "",
        "## Next",
        "",
        "With this row locked, move to candidate evaluation or publication assembly in the shared lock matrix.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    imports = _module_imports(_read(CONTROLLER_PATH))
    forbidden_imports = _forbidden_import_hits(imports)
    request_shape = _request_shape_checks()
    hash_checks = _hash_contract_checks()
    inputs_calls = _inputs_page_controller_request_calls()
    failures: list[str] = []
    if forbidden_imports:
        failures.append("controller_imports_forbidden_modules:" + ",".join(forbidden_imports))
    if not request_shape["is_dataclass"]:
        failures.append("request_is_not_dataclass")
    if not request_shape["frozen"]:
        failures.append("request_is_not_frozen")
    if not request_shape["required_fields_present"]:
        failures.append("request_missing_fields:" + ",".join(request_shape["missing_fields"]))
    if not request_shape["dict_defaults_ok"]:
        failures.append("request_dict_defaults_not_all_default_factory_dict")
    if not hash_checks["proof_churn_excluded"]:
        failures.append("proof_churn_changes_controller_request_hash")
    if not hash_checks["product_change_detected"]:
        failures.append("product_item_change_does_not_change_controller_request_hash")
    if not hash_checks["debug_product_change_detected"]:
        failures.append("debug_product_change_does_not_change_controller_request_hash")
    if not inputs_calls["has_calls"]:
        failures.append("inputs_page_has_no_controller_request_calls")
    if not inputs_calls["imports_request_alias"]:
        failures.append("inputs_page_does_not_import_controller_request_alias")

    status = "PASS" if not failures else "FAIL"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_shared_controller_input_snapshot_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_controller_input_snapshot_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_controller_input_snapshot_lock.v1",
        "status": status,
        "failures": failures,
        "controller_path": str(CONTROLLER_PATH),
        "inputs_page_path": str(INPUTS_PAGE_PATH),
        "request_shape": request_shape,
        "hash_contract": hash_checks,
        "inputs_page_controller_request_calls": inputs_calls,
        "checks": {
            "request_shape": not any(
                failure.startswith("request_")
                for failure in failures
            ),
            "controller_import_boundary": not forbidden_imports,
            "proof_churn_excluded": hash_checks["proof_churn_excluded"],
            "product_change_detected": hash_checks["product_change_detected"] and hash_checks["debug_product_change_detected"],
            "inputs_page_request_calls_present": inputs_calls["has_calls"],
        },
        "artifact": str(json_path),
        "report": str(report_path),
    }
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{status}: {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
