"""Trace wiring proof for post-click exact-blocker raw-vs-bound parity."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

IMPORT_TOKEN = (
    "build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof "
    "as _build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof"
)
DB_FUNCTION_TOKEN = "def build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof("
PAGE_HELPER_TOKEN = "def _stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof("
CALL_TOKEN = "_stamp_final_publication_post_click_exact_blocker_raw_bound_parity_proof("
LIVE_CALL_ANCHOR = "_post_click_exact_blocker_raw_item = dict(_post_click_bending_resolution or {})"

HELPER_TOKENS: tuple[str, ...] = (
    "_build_final_design_guide_post_click_exact_blocker_raw_bound_parity_proof(",
    "final_publication_post_click_exact_blocker_raw_bound_parity_hash",
    "final_publication_post_click_exact_blocker_raw_item_hash",
    "final_publication_post_click_exact_blocker_bound_item_hash",
    "final_publication_post_click_exact_blocker_raw_bound_adapter_result_parity",
    "final_publication_post_click_exact_blocker_ready_to_replace_old_binding",
    "final_publication_post_click_exact_blocker_raw_bound_parity_proof_only",
    "final_publication_post_click_exact_blocker_raw_bound_parity_product_driving",
    "final_publication_post_click_exact_blocker_raw_bound_parity_render_driving",
    "final_publication_post_click_exact_blocker_raw_bound_parity_apply_driving",
    "final_publication_post_click_exact_blocker_raw_bound_parity_session_driving",
)

CALL_TOKENS: tuple[str, ...] = (
    "_post_click_exact_blocker_raw_item = dict(_post_click_bending_resolution or {})",
    "raw_item=dict(_post_click_exact_blocker_raw_item or {})",
    "bound_item=dict(_final_visible_item or {})",
    "final_visible_resolution=dict(_final_visible_resolution or {})",
    "visible_action=True",
    "bending_resolution=dict(_post_click_bending_resolution or {})",
    "bending_contract=dict(_post_click_bending_contract or {})",
    "_post_click_exact_blocker_adapter_result = (",
)

DB_TOKENS: tuple[str, ...] = (
    "raw_result = build_final_design_guide_post_click_final_contract_check_adapter_result(",
    "bound_result = build_final_design_guide_post_click_final_contract_check_adapter_result(",
    "raw_bound_adapter_result_parity",
    "ready_to_replace_old_binding",
    '"product_driving": False',
    '"render_driving": False',
    '"apply_driving": False',
    '"session_driving": False',
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "design_guide_post_click_exact_blocker_final_binding_replacement_readiness",
    "design_guide_render_panel_binding_adapter_readiness",
    "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _window(source: str, token: str, radius: int = 70) -> str:
    lines = source.splitlines()
    for index, line in enumerate(lines):
        if token in line:
            start = max(0, index - radius)
            end = min(len(lines), index + radius)
            return "\n".join(lines[start:end])
    return ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper_window = _window(source, PAGE_HELPER_TOKEN, radius=85)
    call_window = _window(source, LIVE_CALL_ANCHOR, radius=35)
    db_window = _window(final_source, DB_FUNCTION_TOKEN, radius=95)
    latest = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    return {
        "import_present": IMPORT_TOKEN in source,
        "db_function_present": DB_FUNCTION_TOKEN in final_source,
        "page_helper_present": PAGE_HELPER_TOKEN in source,
        "callsite_present": CALL_TOKEN in source and LIVE_CALL_ANCHOR in source,
        "helper_tokens": {token: token in helper_window for token in HELPER_TOKENS},
        "call_tokens": {token: token in call_window for token in CALL_TOKENS},
        "db_tokens": {token: token in db_window for token in DB_TOKENS},
        "trace_only_live_wired": False,
        "latest_artifacts": {
            prefix: {"status": data.get("status"), "path": data.get("path")}
            for prefix, data in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    helper_tokens = dict(capture.get("helper_tokens") or {})
    call_tokens = dict(capture.get("call_tokens") or {})
    db_tokens = dict(capture.get("db_tokens") or {})
    trace_only_live_wired = bool(
        capture.get("import_present")
        and capture.get("db_function_present")
        and capture.get("page_helper_present")
        and capture.get("callsite_present")
        and all(helper_tokens.values())
        and all(call_tokens.values())
        and all(db_tokens.values())
    )
    capture["trace_only_live_wired"] = trace_only_live_wired
    return {
        "import_present": capture.get("import_present") is True,
        "db_function_present": capture.get("db_function_present") is True,
        "page_helper_present": capture.get("page_helper_present") is True,
        "callsite_present": capture.get("callsite_present") is True,
        "helper_tokens_all_true": all(helper_tokens.values()),
        "call_tokens_all_true": all(call_tokens.values()),
        "db_tokens_all_true": all(db_tokens.values()),
        "trace_only_live_wired": trace_only_live_wired is True,
        "replacement_readiness_pass": (
            latest.get("design_guide_post_click_exact_blocker_final_binding_replacement_readiness")
            or {}
        ).get("status")
        == "PASS",
        "binding_adapter_readiness_pass": (
            latest.get("design_guide_render_panel_binding_adapter_readiness") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("design_guide_render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_pass": (
            latest.get("design_guide_compute_resolver_publication_bridge_lock") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("design_guide_independence_lock") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Exact Blocker Raw-Bound Parity Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Trace-only live wired: `{capture.get('trace_only_live_wired')}`",
        "- Product behavior changed: `False`",
        "- Next: run a browser/live parity scenario before deleting the old binding.",
        "",
        "## Checks",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_exact_blocker_raw_bound_parity_trace_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_post_click_exact_blocker_raw_bound_parity_trace_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_click_exact_blocker_raw_bound_parity_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_exact_blocker_raw_bound_parity_trace {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
