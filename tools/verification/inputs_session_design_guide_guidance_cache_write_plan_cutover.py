from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_guidance_cache_write_plan


def _old_debug_bundle(guidance_debug, blocked):
    if not isinstance(guidance_debug, dict):
        return {}
    out = {}
    for key, value in guidance_debug.items():
        if key in blocked:
            continue
        try:
            out[key] = copy.deepcopy(value)
        except Exception:
            out[key] = value
    return out


def main() -> int:
    inputs = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    builders = (ROOT / "inputs_page_modules" / "session" / "builders.py").read_text(encoding="utf-8")
    init_text = (ROOT / "inputs_page_modules" / "session" / "__init__.py").read_text(encoding="utf-8")
    blocked = {"render_feedback", "presentation"}
    scenarios = []
    cases = [
        ("normal", ("fp", 1), [{"id": "a"}], {"truth": {"x": 1}, "render_feedback": 2}),
        ("empty", (), None, None),
        ("all_blocked", "fp", [], {"render_feedback": 1, "presentation": 2}),
    ]
    for name, fingerprint, items, debug in cases:
        plan = build_inputs_design_guide_guidance_cache_write_plan(
            fingerprint=fingerprint,
            guidance_items=items,
            guidance_debug=debug,
            non_cache_debug_keys=blocked,
        )
        scenarios.append(
            {
                "name": name,
                "match": (
                    plan.fingerprint == fingerprint
                    and plan.guidance_items == list(items or [])
                    and plan.cache_debug == _old_debug_bundle(debug, blocked)
                    and bool(plan.display_hash)
                ),
            }
        )
    failures = []
    if not all(row["match"] for row in scenarios):
        failures.append("cache write plan parity failed")
    bundle_start = inputs.index("def _design_guide_cacheable_debug_bundle")
    set_start = inputs.index("def _set_cached_design_guide_guidance", bundle_start)
    next_start = inputs.index("def _design_guide_debug_has_coherent_overview", set_start)
    bundle_body = inputs[bundle_start:set_start]
    set_body = inputs[set_start:next_start]
    if "build_inputs_design_guide_guidance_cache_write_plan(" not in bundle_body:
        failures.append("cacheable debug wrapper does not delegate")
    if "build_inputs_design_guide_guidance_cache_write_plan(" not in set_body:
        failures.append("cache write helper does not delegate")
    for snippet in ("for k, v in guidance_debug.items()", "copy.deepcopy(v)", "list(guidance_items or [])"):
        if snippet in bundle_body or snippet in set_body:
            failures.append(f"old page-owned cache write shaping remains: {snippet}")
    if "st.session_state" in builders or "import streamlit" in builders or "import inputs_page" in builders:
        failures.append("session builder imports or reads forbidden page/UI state")
    if "build_inputs_design_guide_guidance_cache_write_plan" not in init_text:
        failures.append("cache write-plan builder is not exported")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_SESSION_DESIGN_GUIDE_GUIDANCE_CACHE_WRITE_PLAN_LOCKED" if not failures else "FAIL"
    result = {
        "audit": "inputs_session_design_guide_guidance_cache_write_plan_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "session_write_ownership_moved": False,
        "scenarios": scenarios,
        "failures": failures,
    }
    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_session_design_guide_guidance_cache_write_plan_{timestamp}.json"
    report_path = audit_dir / f"inputs_session_design_guide_guidance_cache_write_plan_{timestamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Session Design Guide Guidance Cache Write Plan",
                "",
                f"Decision: `{decision}`",
                "",
                f"Scenarios checked: `{len(scenarios)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The session module owns cache-debug filtering and reusable cache value shaping.",
                "`inputs_page.py` still owns all Streamlit session assignments.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(decision)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
