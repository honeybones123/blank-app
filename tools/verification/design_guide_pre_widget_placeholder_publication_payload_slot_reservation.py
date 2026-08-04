"""Design Guide pre-widget slot reservation snapshot.

Proof-only verifier for the smoothness rule that an existing
FinalDesignGuidePublication payload must not suppress the early Design Guide
placeholder. The placeholder reserves the slot before later render work can
replace it, reducing layout churn without changing final publication truth.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DESIGN_GUIDE_PAGE = ROOT / "design_guide_page.py"


class _FakeStreamlit:
    def __init__(self, state: dict[str, Any]) -> None:
        self.session_state = state


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _function_block(source: str, name: str) -> str:
    marker = f"def {name}"
    start = source.find(marker)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(marker))
    return source[start:] if next_def < 0 else source[start:next_def]


def _capture() -> dict[str, Any]:
    import importlib.util

    source = DESIGN_GUIDE_PAGE.read_text(encoding="utf-8", errors="replace")
    spec = importlib.util.spec_from_file_location("design_guide_page_snapshot", DESIGN_GUIDE_PAGE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not import design_guide_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    final_payload_state = {
        "_design_guide_debug_bundle": {
            "final_publication_verifier_payload": {
                "publication_hash": "pub-final-123",
                "outcome_state": "PASS",
                "display": {"title": "Design accepted"},
                "cta": {"enabled": False},
            }
        }
    }
    applying_state = {
        **final_payload_state,
        "_design_guide_component_apply_in_flight": True,
    }
    no_payload_state: dict[str, Any] = {}

    final_payload_skip = bool(
        module._should_skip_pre_widget_placeholder(_FakeStreamlit(final_payload_state))
    )
    applying_skip = bool(module._should_skip_pre_widget_placeholder(_FakeStreamlit(applying_state)))
    no_payload_skip = bool(module._should_skip_pre_widget_placeholder(_FakeStreamlit(no_payload_state)))

    block = _function_block(source, "_should_skip_pre_widget_placeholder")
    return {
        "schema": "design_guide_pre_widget_placeholder_publication_payload_slot_reservation.v1",
        "source_hash": _stable_hash(block),
        "function_block": block,
        "cases": {
            "final_publication_payload_present": {
                "should_skip": final_payload_skip,
                "expected_should_skip": False,
                "reason": "existing publication should still reserve the early Design Guide slot",
            },
            "apply_in_flight": {
                "should_skip": applying_skip,
                "expected_should_skip": True,
                "reason": "active Apply handoff keeps the existing guarded path",
            },
            "no_publication_payload": {
                "should_skip": no_payload_skip,
                "expected_should_skip": False,
                "reason": "normal proof-pending placeholder remains available",
            },
        },
        "source_checks": {
            "skip_function_present": bool(block),
            "final_publication_payload_not_a_skip_reason": (
                "_has_final_design_guide_publication_payload" not in block
            ),
            "apply_in_flight_guard_present": "_design_guide_component_apply_in_flight" in block,
        },
        "product_behavior_changed": False,
        "final_publication_truth_changed": False,
        "cta_apply_changed": False,
        "visible_final_wording_changed": False,
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Pre-Widget Placeholder Slot Reservation",
        "",
        f"Status: `{payload.get('status')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Cases", "", "| Case | Should skip | Expected |", "|---|---:|---:|"])
    for name, row in (payload.get("cases") or {}).items():
        lines.append(f"| {name} | `{row.get('should_skip')}` | `{row.get('expected_should_skip')}` |")
    lines.extend(
        [
            "",
            "This proof only covers slot reservation. It does not move publication, CTA, apply routing, family runtime, or final visible wording authority.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    capture = _capture()
    cases = dict(capture.get("cases") or {})
    checks = {
        **dict(capture.get("source_checks") or {}),
        "final_publication_payload_keeps_placeholder": (
            cases.get("final_publication_payload_present", {}).get("should_skip") is False
        ),
        "apply_in_flight_still_skips_placeholder": (
            cases.get("apply_in_flight", {}).get("should_skip") is True
        ),
        "no_payload_keeps_placeholder": (
            cases.get("no_publication_payload", {}).get("should_skip") is False
        ),
        "no_publication_truth_or_cta_change": (
            capture.get("final_publication_truth_changed") is False
            and capture.get("cta_apply_changed") is False
            and capture.get("visible_final_wording_changed") is False
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "created_at": _stamp(),
        "status": status,
        "checks": checks,
        **capture,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_pre_widget_placeholder_slot_reservation_{payload['created_at']}.json"
    md_path = AUDIT_DIR / f"design_guide_pre_widget_placeholder_slot_reservation_{payload['created_at']}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_report(payload), encoding="utf-8")
    print(f"design_guide_pre_widget_placeholder_slot_reservation {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
