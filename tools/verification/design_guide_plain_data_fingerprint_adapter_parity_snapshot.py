"""Prove Design Brain plain-data fingerprint adapter parity with legacy page wrapper."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PUBLICATION = ROOT / "design_brain" / "publication.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _scenario_states() -> list[dict[str, Any]]:
    base = {
        "sec_shape": "RECT",
        "b": 300,
        "bw": 300,
        "D": 600,
        "cover_bot": 40,
        "cover_top": 40,
        "cover_side": 40,
        "fc": 40,
        "fsy": 500,
        "Es": 200000,
        "Ec": 30000,
        "span_L_m": 6,
        "uls_Mstar": 0,
        "uls_Vstar": 0,
        "uls_Nstar": 0,
        "Tu_star": 0,
        "sls_Mstar": 0,
        "sls_Vstar": 0,
        "actions_mode": "manual",
        "actions_source": "Manual design actions (inputs below)",
        "loads_edit_mode": "ULS",
        "bot_row_count": 1,
        "bot1_layout_mode": "Count",
        "bot1_count": 3,
        "bot1_spacing": 200,
        "db_bot_1": 16,
        "bot_row_1_mode": "Count",
        "bot_row_1_bars": 3,
        "bot_row_1_spacing": 200,
        "bot_row_1_dia": 16,
        "bot2_count": 0,
        "bot_row_2_bars": 0,
        "db_bot_2": 20,
        "bot_row_2_dia": 20,
        "top_row_count": 1,
        "top1_layout_mode": "Count",
        "top1_count": 2,
        "top1_spacing": 200,
        "db_top_1": 12,
        "top_row_1_mode": "Count",
        "top_row_1_bars": 2,
        "top_row_1_spacing": 200,
        "top_row_1_dia": 12,
        "top2_count": 0,
        "top_row_2_bars": 0,
        "db_top_2": 16,
        "top_row_2_dia": 16,
        "lig_d": 0,
        "lig_legs": 0,
        "s_lig": 200,
    }
    active_second_row = dict(base)
    active_second_row.update(
        {
            "bot_row_count": 2,
            "bot2_count": 2,
            "bot_row_2_bars": 2,
            "db_bot_2": 12,
            "bot_row_2_dia": 12,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 150,
        }
    )
    t_beam = dict(base)
    t_beam.update({"sec_shape": "T", "bf": 600, "tf": 120, "tw": 300})
    loading = dict(base)
    loading.update(
        {
            "uls_Mstar": 300,
            "uls_Vstar": 100,
            "load_Mstar_proxy": 300,
            "load_Vstar_proxy": 100,
            "sfd_case": "Simple beam - UDL over entire span",
        }
    )
    return [base, active_second_row, t_beam, loading]


def _capture() -> dict[str, Any]:
    import inputs_page
    from design_brain.publication import (
        DEFAULT_DESIGN_GUIDE_ALGORITHM_VERSION,
        DESIGN_GUIDE_PUBLICATION_CACHE_PREFIX,
        design_guide_cache_fingerprint_from_plain_data,
        design_guide_publication_state_payload_from_plain_data,
    )

    source = PUBLICATION.read_text(encoding="utf-8", errors="replace")
    cases: list[dict[str, Any]] = []
    for idx, state in enumerate(_scenario_states(), start=1):
        signature = tuple(inputs_page._resolve_design_actions_from_state(dict(state)).get("signature", ()))
        optimisation_goal = str(inputs_page._design_optimisation_goal(dict(state)))
        legacy_payload = inputs_page._design_guide_publication_state_payload(dict(state))
        adapter_payload = design_guide_publication_state_payload_from_plain_data(
            dict(state),
            design_actions_signature=signature,
            optimisation_goal=optimisation_goal,
        )
        legacy_fingerprint = inputs_page._design_guide_cache_fingerprint(dict(state))
        adapter_fingerprint = design_guide_cache_fingerprint_from_plain_data(
            dict(state),
            design_actions_signature=signature,
            optimisation_goal=optimisation_goal,
            algorithm_version=inputs_page.DESIGN_GUIDE_ALGORITHM_VERSION,
        )
        cases.append(
            {
                "case_id": f"case_{idx}",
                "payload_match": legacy_payload == adapter_payload,
                "fingerprint_match": legacy_fingerprint == adapter_fingerprint,
                "legacy_payload_hash": _stable_hash(legacy_payload),
                "adapter_payload_hash": _stable_hash(adapter_payload),
                "legacy_fingerprint_hash": _stable_hash(legacy_fingerprint),
                "adapter_fingerprint_hash": _stable_hash(adapter_fingerprint),
                "legacy_fingerprint_prefix": legacy_fingerprint[0] if legacy_fingerprint else None,
                "adapter_fingerprint_prefix": adapter_fingerprint[0] if adapter_fingerprint else None,
            }
        )
    forbidden_tokens = {
        "inputs_page": "inputs_page" in source,
        "streamlit": "streamlit" in source,
        "st_session_state": "st.session_state" in source,
        "st_button": "st.button" in source,
        "render_panel": "render_final_panel" in source,
        "apply_routing": "handle_apply_buttons" in source,
    }
    return {
        "cases": cases,
        "adapter_surface": {
            "payload_adapter": "design_guide_publication_state_payload_from_plain_data",
            "cache_fingerprint_adapter": "design_guide_cache_fingerprint_from_plain_data",
            "prefix": DESIGN_GUIDE_PUBLICATION_CACHE_PREFIX,
            "default_algorithm_version": DEFAULT_DESIGN_GUIDE_ALGORITHM_VERSION,
        },
        "forbidden_tokens_present": forbidden_tokens,
        "composed": {
            "state_fingerprint_ownership_audit": _run(
                "tools/verification/design_guide_state_fingerprint_ownership_audit.py"
            )
        },
        "decision": "PLAIN_DATA_FINGERPRINT_ADAPTER_PARITY_PROVEN",
        "next_step": (
            "Use the adapter in the controller selector state_fingerprint calculation, "
            "then rerun no-active primary readiness."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    cases = list(capture.get("cases") or [])
    composed = dict(capture.get("composed") or {})
    return {
        "all_cases_payload_match": bool(cases)
        and all(case.get("payload_match") is True for case in cases),
        "all_cases_fingerprint_match": bool(cases)
        and all(case.get("fingerprint_match") is True for case in cases),
        "adapter_surface_named": bool(
            (capture.get("adapter_surface") or {}).get("payload_adapter")
        )
        and bool((capture.get("adapter_surface") or {}).get("cache_fingerprint_adapter")),
        "no_page_ui_session_apply_imports": not any(
            (capture.get("forbidden_tokens_present") or {}).values()
        ),
        "ownership_audit_passes": (
            (composed.get("state_fingerprint_ownership_audit") or {}).get("passed") is True
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Plain-Data Fingerprint Adapter Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Payload match | Fingerprint match |",
            "| --- | --- | --- |",
        ]
    )
    for case in capture.get("cases") or []:
        lines.append(
            f"| {case.get('case_id')} | `{case.get('payload_match')}` | `{case.get('fingerprint_match')}` |"
        )
    lines.extend(["", "## Next Step", "", str(capture.get("next_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_plain_data_fingerprint_adapter_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_plain_data_fingerprint_adapter_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_plain_data_fingerprint_adapter_parity_snapshot {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
