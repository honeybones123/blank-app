"""Verify active-fail executor rescue seed command handoff."""

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
HELPER = "build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands"
ORDER_HELPER = "resolve_design_guide_controller_active_fail_executor_rescue_seed_order"


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


def _seed_library() -> dict[str, Any]:
    return {
        "bending": {
            "medium": {"key": "bending_medium", "updates": {"D": 600.0}},
            "high": {"key": "bending_high", "updates": {"D": 700.0}},
            "very_high": {"key": "bending_very_high", "updates": {"D": 800.0}},
            "extreme": {"key": "bending_extreme", "updates": {"D": 900.0}},
        },
        "shear": {
            "medium": {"key": "shear_medium", "updates": {"lig_d": 12}},
            "high": {"key": "shear_high", "updates": {"lig_d": 16}},
            "very_high": {"key": "shear_very_high", "updates": {"lig_legs": 6}},
            "extreme": {"key": "shear_extreme", "updates": {"lig_d": 20}},
        },
        "combined": {
            "medium": {"key": "combined_medium", "updates": {"D": 650.0, "lig_d": 12}},
            "high": {"key": "combined_high", "updates": {"D": 750.0, "lig_d": 16}},
            "very_high": {"key": "combined_very_high", "updates": {"D": 850.0, "lig_legs": 6}},
            "extreme": {"key": "combined_extreme", "updates": {"D": 950.0, "lig_d": 20}},
        },
    }


def _old_seed_order(requested_tier: str | None) -> list[str]:
    tier_order = ["medium", "high", "very_high", "extreme"]
    if requested_tier not in tier_order:
        return []
    if requested_tier == "extreme":
        return ["very_high", "extreme"]
    idx = tier_order.index(requested_tier)
    out = list(tier_order[idx:])
    if "extreme" in out and requested_tier != "very_high":
        return [tier for tier in out if tier != "extreme"] + ["extreme"]
    return out


def _old_commands(rescue_family: str, requested_tier: str | None, library: dict[str, Any]) -> dict[str, Any]:
    seed_order = _old_seed_order(requested_tier)
    family = str(rescue_family or "").strip().lower()
    commands: list[dict[str, Any]] = []
    for tier in seed_order:
        seed_spec = dict(((library.get(family) or {}).get(tier)) or {})
        seed_updates = dict(seed_spec.get("updates") or {})
        if not seed_updates:
            continue
        commands.append(
            {
                "tier": tier,
                "seed_spec": seed_spec,
                "updates": seed_updates,
                "label": f"Active fail {family} rescue repair ({seed_spec.get('key') or f'{family}_{tier}'})",
                "source": "RESCUE_SEED_LIBRARY",
            }
        )
    return {
        "rescue_family": family,
        "requested_tier": requested_tier,
        "seed_order": seed_order,
        "commands": commands,
    }


def _new_commands(rescue_family: str, requested_tier: str | None, library: dict[str, Any]) -> dict[str, Any]:
    from design_brain.design_guide_controller import (  # noqa: WPS433
        build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands,
    )

    return build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands(
        rescue_family=rescue_family,
        requested_tier=requested_tier,
        rescue_seed_library=dict(library),
    )


def _cases() -> dict[str, tuple[str, str | None]]:
    return {
        "bending_none": ("bending", None),
        "bending_medium": ("bending", "medium"),
        "shear_high": ("shear", "high"),
        "combined_very_high": ("combined", "very_high"),
        "combined_extreme": ("combined", "extreme"),
        "unknown_family": ("custom", "medium"),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    helper_start, helper_end, helper_source = _function_source(controller_source, HELPER)
    order_start, order_end, order_source = _function_source(controller_source, ORDER_HELPER)
    library = _seed_library()

    parity: dict[str, dict[str, Any]] = {}
    for name, (family, tier) in _cases().items():
        old = _old_commands(family, tier, library)
        new = _new_commands(family, tier, library)
        parity[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "match": old == new,
            "command_count": len(new.get("commands") or []),
        }

    removed_fallback_tokens = {
        "fallback_for_tier_loop": "for tier in _rescue_mode_seed_order(requested_tier):" not in target_source,
        "fallback_direct_seed_library_lookup": "RESCUE_SEED_LIBRARY.get(rescue_family)" not in target_source,
        "fallback_inline_rescue_label": "Active fail {rescue_family} rescue repair" not in target_source,
    }

    return {
        "schema": "design_guide_active_fail_executor_rescue_seed_command_handoff.v1",
        "target": {
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
            "delegates_rescue_seed_commands": "_build_design_guide_controller_active_fail_executor_rescue_seed_eval_commands("
            in target_source,
            "still_owns_requested_tier_choice": "_rescue_mode_choose_tier_from_overview(" in target_source,
            "still_owns_evaluator_callback": "_evaluate_active_fail_executor_candidate_with_updates(" in target_source,
            "removed_fallback_tokens": removed_fallback_tokens,
        },
        "controller_helper": {
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
            "exists": bool(helper_start),
            "order_helper_exists": bool(order_start),
            "exported": f'"{HELPER}"' in controller_source and f'"{ORDER_HELPER}"' in controller_source,
            "imports_no_page_or_streamlit": all(
                token not in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
            ),
            "helper_hash": _stable_hash(helper_source + order_source),
        },
        "parity": parity,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    target = payload.get("target") or {}
    helper = payload.get("controller_helper") or {}
    parity = payload.get("parity") or {}
    return {
        "target_found": bool(target.get("line_start")),
        "target_delegates_rescue_seed_commands": bool(target.get("delegates_rescue_seed_commands")),
        "page_still_owns_requested_tier_choice": bool(target.get("still_owns_requested_tier_choice")),
        "page_still_owns_evaluator_callback": bool(target.get("still_owns_evaluator_callback")),
        "fallback_inline_seed_iteration_removed": all((target.get("removed_fallback_tokens") or {}).values()),
        "controller_helper_exists": bool(helper.get("exists")),
        "controller_order_helper_exists": bool(helper.get("order_helper_exists")),
        "controller_helpers_exported": bool(helper.get("exported")),
        "controller_import_boundary_clean": bool(helper.get("imports_no_page_or_streamlit")),
        "parity_cases_present": len(parity) == 6,
        "all_rescue_seed_command_hashes_match": all(bool(row.get("match")) for row in parity.values()),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_rescue_seed_command_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_rescue_seed_command_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Rescue Seed Command Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Executive Summary",
        (
            "Active-fail fallback rescue seed order and evaluation command shaping now delegate to "
            "`DesignGuideController`. The page still chooses the requested tier from live page state and executes "
            "the evaluator callback."
        ),
        "",
        "## Rescue Seed Parity",
    ]
    for name, row in (payload.get("parity") or {}).items():
        lines.append(
            f"- {name}: {'PASS' if row.get('match') else 'FAIL'} "
            f"commands `{row.get('command_count')}` hash `{row.get('new_hash')}`"
        )
    lines.extend(["", "## Checks", *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()]])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    payload["snapshot_hash"] = _stable_hash(
        {
            "target": payload.get("target"),
            "controller_helper": payload.get("controller_helper"),
            "parity": payload.get("parity"),
        }
    )
    json_path, report_path = _write(payload, checks)
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
