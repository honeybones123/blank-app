from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict = {}


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_zero_shear_stale_blocker_clear_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_zero_shear_stale_blocker_clear_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        if not condition:
            failures.append(f"{name}:{detail}")

    fake_st = FakeStreamlit()
    original_st = inputs_page.st
    debug_key = inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY
    blocker_keys = (
        "exact_blockers_by_family",
        "post_click_exact_blockers_by_family",
        "cleanup_evidence_by_family",
        "post_click_cleanup_evidence_by_family",
        "blocker_attempts_by_family",
    )

    try:
        inputs_page.st = fake_st
        guidance_debug = {
            key: {
                "shear": {"reason": f"{key}: stale shear"},
                "bending": {"reason": f"{key}: keep bending"},
            }
            for key in blocker_keys
        }
        fake_st.session_state[debug_key] = {
            key: {
                "shear": {"reason": f"session {key}: stale shear"},
                "bending": {"reason": f"session {key}: keep bending"},
            }
            for key in blocker_keys
        }
        cleared = inputs_page.render_design_guide_terminal_zero_shear_stale_blocker_clear(
            terminal_zero_shear_demand_accepted=True,
            guidance_debug=guidance_debug,
        )
        session_debug = dict(fake_st.session_state.get(debug_key) or {})

        no_op_debug = {
            "exact_blockers_by_family": {"shear": {"reason": "must remain"}},
        }
        fake_st.session_state[debug_key] = {
            "exact_blockers_by_family": {"shear": {"reason": "session must remain"}},
        }
        no_op = inputs_page.render_design_guide_terminal_zero_shear_stale_blocker_clear(
            terminal_zero_shear_demand_accepted=False,
            guidance_debug=no_op_debug,
        )
        no_op_session = dict(fake_st.session_state.get(debug_key) or {})
    finally:
        inputs_page.st = original_st

    expect(
        "guidance_shear_removed",
        all("shear" not in dict(cleared.get(key) or {}) for key in blocker_keys)
        and all(dict(cleared.get(key) or {}).get("bending", {}).get("reason") == f"{key}: keep bending" for key in blocker_keys)
        and cleared.get("zero_shear_accepted_stale_blocker_cleared") is True
        and cleared.get("terminal_zero_shear_demand_accepted") is True,
        f"cleared={cleared}",
    )
    expect(
        "session_shear_removed",
        all("shear" not in dict(session_debug.get(key) or {}) for key in blocker_keys)
        and all(
            dict(session_debug.get(key) or {}).get("bending", {}).get("reason")
            == f"session {key}: keep bending"
            for key in blocker_keys
        ),
        f"session_debug={session_debug}",
    )
    expect(
        "no_op_path",
        no_op == {"exact_blockers_by_family": {"shear": {"reason": "must remain"}}}
        and no_op_session
        == {"exact_blockers_by_family": {"shear": {"reason": "session must remain"}}},
        f"no_op={no_op} no_op_session={no_op_session}",
    )

    result = {
        "verdict": "PASS" if not failures else "FAIL",
        "json": str(json_path),
        "report": str(report_path),
        "failures": failures,
        "cleared": cleared,
        "session_debug": session_debug,
        "no_op": no_op,
        "no_op_session": no_op_session,
    }
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal Zero Shear Stale Blocker Clear Verifier",
                "",
                f"Verdict: `{result['verdict']}`",
                "",
                f"JSON: `{json_path}`",
                "",
                "## Failures",
                "",
                *(failures or ["None."]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
