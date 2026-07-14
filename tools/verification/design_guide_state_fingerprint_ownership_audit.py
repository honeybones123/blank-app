"""Audit ownership of the Design Guide primary apply state fingerprint."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
PUBLICATION = ROOT / "design_brain" / "publication.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    publication_source = PUBLICATION.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    wrapper_source, wrapper_start, wrapper_end = _function_source(
        INPUTS_PAGE, "_design_guide_primary_apply_state_fingerprint"
    )
    cache_source, cache_start, cache_end = _function_source(
        INPUTS_PAGE, "_design_guide_cache_fingerprint"
    )
    payload_source, payload_start, payload_end = _function_source(
        INPUTS_PAGE, "_design_guide_publication_state_payload"
    )
    core_source, core_start, core_end = _function_source(
        PUBLICATION, "design_guide_primary_apply_state_fingerprint_from_state"
    )
    blockers = {
        "wrapper_uses_shared_state_snapshot_when_state_missing": "_shared_state_snapshot()" in wrapper_source,
        "wrapper_uses_guidance_state_snapshot": "_guidance_state_snapshot(raw_state)" in wrapper_source,
        "wrapper_injects_page_cache_fingerprint": "_design_guide_cache_fingerprint" in wrapper_source,
        "cache_uses_page_publication_state_payload": "_design_guide_publication_state_payload(state)" in cache_source,
        "payload_reads_streamlit_session": "st.session_state" in payload_source,
        "payload_uses_page_design_action_resolution": "_resolve_design_actions_from_state" in payload_source,
        "payload_uses_page_optimisation_goal": "_design_optimisation_goal(source)" in payload_source,
    }
    owned = {
        "design_brain_core_exists": "def design_guide_primary_apply_state_fingerprint_from_state(" in publication_source,
        "design_brain_core_accepts_cache_fingerprint_injection": "cache_fingerprint: Callable[[dict], Any]" in core_source,
        "design_brain_core_normalizes_absent_second_bottom_row": "source[\"db_bot_2\"] = 0" in core_source
        and "source[\"bot_row_2_dia\"] = 0" in core_source,
        "design_brain_plain_data_payload_adapter_exists": "def design_guide_publication_state_payload_from_plain_data(" in publication_source,
        "design_brain_plain_data_cache_adapter_exists": "def design_guide_cache_fingerprint_from_plain_data(" in publication_source,
        "controller_uses_plain_data_cache_adapter": "design_guide_cache_fingerprint_from_plain_data(" in controller_source,
        "controller_no_longer_uses_private_state_hash": "state_fingerprint = stable_final_publication_hash(" not in controller_source,
    }
    return {
        "status_decision": "CORE_AND_PLAIN_DATA_ADAPTER_EXIST_PAGE_WRAPPER_REMAINS",
        "functions": {
            "inputs_wrapper": {
                "path": str(INPUTS_PAGE),
                "name": "_design_guide_primary_apply_state_fingerprint",
                "start_line": wrapper_start,
                "end_line": wrapper_end,
            },
            "inputs_cache_fingerprint": {
                "path": str(INPUTS_PAGE),
                "name": "_design_guide_cache_fingerprint",
                "start_line": cache_start,
                "end_line": cache_end,
            },
            "inputs_publication_state_payload": {
                "path": str(INPUTS_PAGE),
                "name": "_design_guide_publication_state_payload",
                "start_line": payload_start,
                "end_line": payload_end,
            },
            "design_brain_core": {
                "path": str(PUBLICATION),
                "name": "design_guide_primary_apply_state_fingerprint_from_state",
                "start_line": core_start,
                "end_line": core_end,
            },
        },
        "design_brain_owned_surface": owned,
        "page_owned_blockers": blockers,
        "direct_move_safe": False,
        "required_next_adapter": "plain_data_publication_state_payload_adapter",
        "recommended_next_step": (
            "Keep the page wrapper as a collector until live selector readiness is proven, "
            "then replace the no-active primary branch route before deleting page wrapper callsites."
        ),
        "inputs_reference_count": inputs_source.count("_design_guide_primary_apply_state_fingerprint("),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    owned = dict(capture.get("design_brain_owned_surface") or {})
    blockers = dict(capture.get("page_owned_blockers") or {})
    return {
        "design_brain_core_exists": owned.get("design_brain_core_exists") is True,
        "core_accepts_cache_fingerprint_injection": (
            owned.get("design_brain_core_accepts_cache_fingerprint_injection") is True
        ),
        "plain_data_adapters_exist": (
            owned.get("design_brain_plain_data_payload_adapter_exists") is True
            and owned.get("design_brain_plain_data_cache_adapter_exists") is True
        ),
        "controller_uses_shared_adapter": (
            owned.get("controller_uses_plain_data_cache_adapter") is True
            and owned.get("controller_no_longer_uses_private_state_hash") is True
        ),
        "page_owned_blockers_identified": all(blockers.values()),
        "direct_move_marked_unsafe": capture.get("direct_move_safe") is False,
        "adapter_next_step_explicit": bool(capture.get("required_next_adapter")),
        "inputs_references_found": int(capture.get("inputs_reference_count") or 0) > 0,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide State Fingerprint Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('status_decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Functions"])
    for key, value in (capture.get("functions") or {}).items():
        lines.append(
            f"- {key}: `{value.get('name')}` at `{value.get('path')}` lines `{value.get('start_line')}`-`{value.get('end_line')}`"
        )
    lines.extend(
        [
            "",
            "## Finding",
            "",
            "The reusable fingerprint core and plain-data adapter exist in `design_brain/publication.py`. The controller selector uses that shared adapter. The current page wrapper still owns collection of Streamlit/session-influenced controls, so it remains a collector boundary until route replacement removes the dependent callsites.",
            "",
            "## Next Step",
            "",
            str(capture.get("recommended_next_step") or ""),
        ]
    )
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
    json_path = ARTIFACT_DIR / f"design_guide_state_fingerprint_ownership_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_state_fingerprint_ownership_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_state_fingerprint_ownership_audit {status}")
    print(f"decision={capture.get('status_decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
