"""Verify duplicate secondary Status rows are suppressed only when redundant."""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _load_inputs_page() -> Any:
    spec = importlib.util.spec_from_file_location("inputs_page_under_test", INPUTS_PAGE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load inputs_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build() -> dict[str, Any]:
    module = _load_inputs_page()
    duplicate_item = {
        "title": "Bending cleanup blocked",
        "reasoning": "Trial bottom-reinforcement reductions were exhausted and none preserved bending checks.",
        "primary_action": "Why: Trial bottom-reinforcement reductions were exhausted and none preserved bending checks.",
    }
    title_prefixed_duplicate_item = {
        "title": "Bending cleanup blocked",
        "reasoning": "Bending cleanup blocked: Trial bottom-reinforcement reductions were exhausted.",
        "primary_action": "Bending cleanup blocked: Trial bottom-reinforcement reductions were exhausted.",
    }
    unique_item = {
        "title": "Bending cleanup blocked",
        "reasoning": "Trial bottom-reinforcement reductions were exhausted.",
        "primary_action": "Review the recorded blocker evidence.",
    }
    checks = {
        "duplicate_why_primary_action_suppressed": module._design_guide_primary_action_repeats_visible_reason(
            duplicate_item
        )
        is True,
        "title_prefixed_duplicate_why_primary_action_suppressed": module._design_guide_primary_action_repeats_visible_reason(
            title_prefixed_duplicate_item
        )
        is True,
        "unique_primary_action_not_suppressed": module._design_guide_primary_action_repeats_visible_reason(
            unique_item
        )
        is False,
        "render_branch_uses_duplicate_guard": "_design_guide_primary_action_repeats_visible_reason(item)"
        in INPUTS_PAGE.read_text(encoding="utf-8", errors="replace"),
        "render_branch_suppresses_primary_why_status_rows": (
            'str(item.get("primary_action") or "").strip().lower().startswith("why:")'
            in INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
        ),
        "render_branch_suppresses_title_prefixed_status_rows": (
            "_design_guide_readability_token_overlap(action_without_title, visible_reason) >= 0.82"
            in INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "design_guide_secondary_status_duplicate_readability_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "product_behaviour_changed": False,
        "visible_engineering_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtimes_changed": False,
        "design_brain_authority_changed": False,
        "checks": checks,
        "failures": failures,
        "source_file": str(INPUTS_PAGE),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_secondary_status_duplicate_readability_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_secondary_status_duplicate_readability_{stamp}.md"
    lines = [
        "# Design Guide Secondary Status Duplicate Readability",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Visible engineering wording changed: `{payload.get('visible_engineering_wording_changed')}`",
        f"- CTA/apply semantics changed: `{payload.get('cta_apply_semantics_changed')}`",
        f"- Family runtimes changed: `{payload.get('family_runtimes_changed')}`",
        f"- Design Brain authority changed: `{payload.get('design_brain_authority_changed')}`",
        "",
        "```json",
        json.dumps(payload.get("checks"), indent=2, sort_keys=True),
        "```",
        "",
    ]
    if payload.get("failures"):
        lines.extend(["## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_secondary_status_duplicate_readability {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["failures"]:
        print("failures=" + json.dumps(payload["failures"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
