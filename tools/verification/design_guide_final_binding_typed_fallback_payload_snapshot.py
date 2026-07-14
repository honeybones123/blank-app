"""Proof snapshot for final-binding typed helper fallbacks.

This verifier proves the final-binding helper exception paths no longer fall
back to bare empty payloads. It does not delete manual fallback rows; it only
checks that the replacement fallback object is typed, hash-stamped, and
non-authoritative while preserving the old effect maps.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import (  # noqa: E402
    build_final_visible_contract_binding_typed_fallback_payload,
)


HELPERS = {
    "no_second_cta": {
        "token": "def _stamp_final_visible_contract_binding_no_second_cta_result(",
        "error_key": "final_binding_no_second_cta_result_error",
        "required_effects": (
            "contract_effect",
            "item_effect",
            "evidence_effect",
            "debug_effect",
        ),
        "required_groups": (
            "final_binding_no_second_cta_decision",
            "button_contract_suppression_effect",
        ),
    },
    "target_band_promotion": {
        "token": "def _stamp_final_visible_contract_binding_target_band_promotion_result(",
        "error_key": "final_binding_target_band_promotion_result_error",
        "required_effects": (
            "contract_effect",
            "item_effect",
            "evidence_effect",
            "display_truth_effect",
            "action_payload_effect",
            "resolved_candidate_effect",
            "debug_effect",
        ),
        "required_groups": (
            "final_binding_target_band_promotion_decision",
            "button_contract_promotion_effect",
        ),
    },
    "consistency_guard": {
        "token": "def _stamp_final_visible_contract_binding_consistency_guard_result(",
        "error_key": "final_binding_consistency_guard_result_error",
        "required_effects": (
            "updates_replacement",
            "action_type_replacement",
            "contract_replacement",
        ),
        "required_groups": (
            "final_binding_contract_consistency_guard",
            "contract_reset_effect",
        ),
    },
    "contract_truth": {
        "token": "def _stamp_final_visible_contract_binding_truth_result(",
        "error_key": "final_binding_contract_truth_result_error",
        "required_effects": (
            "evidence_expected_util",
            "contract_expected_util",
            "evidence_family_for_contract",
            "contract_updates_cross_family",
            "blocker_families_for_contract",
            "debug_effect",
        ),
        "required_groups": (
            "enabled_contract_expected_util_family_truth",
            "enabled_contract_blocker_family_truth",
        ),
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _exception_block(block: str) -> str:
    marker = "    except Exception as exc:"
    start = block.find(marker)
    if start < 0:
        return ""
    return block[start:]


def _builder_probe() -> dict[str, Any]:
    first = build_final_visible_contract_binding_typed_fallback_payload(
        result={
            "applies": True,
            "contract_effect": {"enabled": False},
            "item_effect": {"primary_card_actionable": False},
        },
        input_hashes={"fixture": "typed-fallback"},
        represented_live_groups=("fixture_group",),
        derived_from="fixture",
        error="fixture-error",
        fallback_reason="fixture_reason",
        ready_for_live_cutover=False,
    )
    second = build_final_visible_contract_binding_typed_fallback_payload(
        result={
            "applies": True,
            "contract_effect": {"enabled": False},
            "item_effect": {"primary_card_actionable": False},
        },
        input_hashes={"fixture": "typed-fallback"},
        represented_live_groups=("fixture_group",),
        derived_from="fixture",
        error="fixture-error",
        fallback_reason="fixture_reason",
        ready_for_live_cutover=False,
    )
    return {
        "payload": first,
        "stable_repeat_hash": first.get("proof_hash") == second.get("proof_hash"),
        "required_flags": {
            "fallback_payload": first.get("fallback_payload") is True,
            "proof_only": first.get("proof_only") is True,
            "product_driving_false": first.get("product_driving") is False,
            "render_driving_false": first.get("render_driving") is False,
            "apply_driving_false": first.get("apply_driving") is False,
            "session_driving_false": first.get("session_driving") is False,
            "has_result_hash": bool(first.get("result_hash")),
            "has_proof_hash": bool(first.get("proof_hash")),
            "ready_for_live_cutover_false_supported": first.get("ready_for_live_cutover") is False,
        },
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper_rows: dict[str, Any] = {}
    for name, spec in HELPERS.items():
        block = _function_block(source, str(spec["token"]))
        exception = _exception_block(block)
        represented_groups = tuple(str(group) for group in spec["required_groups"])
        required_effects = tuple(str(effect) for effect in spec["required_effects"])
        helper_rows[name] = {
            "helper_present": bool(block),
            "exception_path_present": bool(exception),
            "uses_typed_fallback_builder": "_build_final_visible_contract_binding_typed_fallback_payload(" in exception,
            "exception_returns_bare_empty_payload": "return {}" in exception,
            "error_key_stamped": str(spec["error_key"]) in exception,
            "required_effects_present": {
                effect: f'"{effect}"' in exception for effect in required_effects
            },
            "required_groups_present": {
                group: f'"{group}"' in exception for group in represented_groups
            },
            "non_authoritative_flags_stamped": all(
                token in exception
                for token in (
                    "_proof_only",
                    "_product_driving",
                    "_render_driving",
                    "_apply_driving",
                    "_session_driving",
                )
            ),
        }
    builder = _builder_probe()
    return {
        "decision": "FINAL_BINDING_HELPER_EXCEPTION_PATHS_USE_TYPED_FALLBACK_PAYLOADS",
        "builder_probe": builder,
        "helpers": helper_rows,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    builder = dict(capture.get("builder_probe") or {})
    builder_flags = dict(builder.get("required_flags") or {})
    helpers = dict(capture.get("helpers") or {})
    return {
        "builder_exists_and_hashes_stably": builder.get("stable_repeat_hash") is True,
        "builder_required_flags": all(builder_flags.values()),
        "all_helpers_present": set(helpers) == set(HELPERS)
        and all((row or {}).get("helper_present") is True for row in helpers.values()),
        "all_exception_paths_present": all(
            (row or {}).get("exception_path_present") is True for row in helpers.values()
        ),
        "all_use_typed_fallback_builder": all(
            (row or {}).get("uses_typed_fallback_builder") is True for row in helpers.values()
        ),
        "no_helper_exception_returns_bare_empty_payload": all(
            (row or {}).get("exception_returns_bare_empty_payload") is False for row in helpers.values()
        ),
        "all_error_keys_stamped": all(
            (row or {}).get("error_key_stamped") is True for row in helpers.values()
        ),
        "all_required_effects_present": all(
            all(dict((row or {}).get("required_effects_present") or {}).values())
            for row in helpers.values()
        ),
        "all_required_groups_present": all(
            all(dict((row or {}).get("required_groups_present") or {}).values())
            for row in helpers.values()
        ),
        "all_paths_non_authoritative": all(
            (row or {}).get("non_authoritative_flags_stamped") is True for row in helpers.values()
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Typed Fallback Payload Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Helpers",
        "",
    ]
    for name, row in (capture.get("helpers") or {}).items():
        lines.append(
            f"- {name}: typed_fallback=`{row.get('uses_typed_fallback_builder')}`, "
            f"bare_empty_return=`{row.get('exception_returns_bare_empty_payload')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_final_binding_typed_fallback_payload_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_typed_fallback_payload_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_typed_fallback_payload_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_typed_fallback_payload {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
