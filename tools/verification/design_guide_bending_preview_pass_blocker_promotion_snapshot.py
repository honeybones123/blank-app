from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACTS = ROOT / "artifacts"
VERIFICATION_DIR = ARTIFACTS / "verification"
AUDITS_DIR = ARTIFACTS / "audits"


def _extract_function(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    return source[start:next_start]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    helper = _extract_function(source, "_promote_bending_fail_family_repair_before_blocker_policy")
    preview_helper = _extract_function(source, "_bending_fail_preview_passes_for_visible_item")
    view_model = _extract_function(source, "build_design_guide_card_view_model")
    policy = _extract_function(source, "_design_guide_active_failure_blocker_publication_policy")

    checks = {
        "helper_exists": bool(helper),
        "preview_helper_exists": bool(preview_helper),
        "active_failures_must_be_bending_only": 'active_failures != {"bending"}' in helper,
        "requires_visible_preview_pass": "_bending_fail_preview_passes_for_visible_item(item)" in helper,
        "uses_locked_bending_family_route": "_active_fail_near_current_repair_item(" in helper
        and '{"bending"}' in helper,
        "binds_normal_apply_contract": "_design_guide_apply_button_contracts_to_items" in helper,
        "freshly_evaluates_updates": "_evaluate_auto_design_candidate(" in helper
        and "design_guide_bending_fail_preview_pass_family_promotion" in helper,
        "requires_required_checks_acceptable": "_overview_required_checks_acceptable(preview_overview)" in helper,
        "requires_enabled_apply_contract": "_design_guide_button_contract_enabled(contract)" in helper
        and '"apply_resolved_candidate"' in helper,
        "stamps_bending_fail_family_owner": "BENDING_FAIL_GOVERNS" in helper
        and "design_brain.families.bending_fail.BendingFailFamily" in helper,
        "clears_stale_blocker_keys": "exact_blockers_by_family" in helper
        and "post_click_exact_blockers_by_family" in helper
        and "design_guide_publication_policy" in helper,
        "sets_executor_backed_apply_payload": "resolved_candidate_updates" in helper
        and "selected_action_updates" in helper,
        "view_model_calls_promotion_before_policy": (
            view_model.find("_promote_bending_fail_family_repair_before_blocker_policy(")
            < view_model.find("_design_guide_active_failure_blocker_publication_policy(")
            if "_promote_bending_fail_family_repair_before_blocker_policy(" in view_model
            and "_design_guide_active_failure_blocker_publication_policy(" in view_model
            else False
        ),
        "policy_still_blocks_missing_apply_cta": "unlocked_active_failure_missing_apply_cta" in policy,
        "old_bending_env_gate_absent": "DESIGN_BRAIN_BENDING_FAIL_FAMILY_ROUTING" not in source,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "snapshot": "design_guide_bending_preview_pass_blocker_promotion",
        "status": status,
        "checks": checks,
        "hashes": {
            "helper": _sha256(helper),
            "preview_helper": _sha256(preview_helper),
            "view_model": _sha256(view_model),
            "policy": _sha256(policy),
        },
        "purpose": (
            "A bending-only active failure with a PASS preview must be promoted through "
            "the locked BENDING_FAIL_GOVERNS route before the final blocker-proof policy can publish."
        ),
    }

    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"design_guide_bending_preview_pass_blocker_promotion_{timestamp}.json"
    md_path = AUDITS_DIR / f"design_guide_bending_preview_pass_blocker_promotion_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    missing = [name for name, ok in checks.items() if not ok]
    md_lines = [
        "# Design Guide Bending Preview-Pass Blocker Promotion",
        "",
        f"Status: `{status}`",
        "",
        "## Purpose",
        "",
        payload["purpose"],
        "",
        "## Checks",
        "",
    ]
    md_lines.extend(f"- `{name}`: `{ok}`" for name, ok in checks.items())
    if missing:
        md_lines.extend(["", "## Missing", ""])
        md_lines.extend(f"- `{name}`" for name in missing)
    md_lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- JSON: `{json_path}`",
        ]
    )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": status, "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
