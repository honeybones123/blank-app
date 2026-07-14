"""Audit BENDING_FAIL_GOVERNS family proof recognition in live Design Guide paths.

Proof-only. This verifier does not change product behaviour. It documents
whether the locked BENDING_FAIL_GOVERNS no-repair proof fields exist, whether
the page recognizer knows them, and whether the latest browser/live Design
Guide payload actually carries that proof through to final publication.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_RUNTIME_TERMS = (
    "blocked_ownership_proof",
    "repair_blocked",
    "hard_blocker_proven",
    "contract_strategy_exhaustion_proven",
    "internal_cap_only",
)

REQUIRED_PAGE_RECOGNIZER_TERMS = (
    "bending_fail_blocked_ownership_proof",
    "repair_reason_proof",
    "blocked_ownership_proof",
    "bending_fail_repair_blocked",
    "bending_fail_contract_strategy_exhaustion_proven",
    "bending_fail_hard_blocker_proven",
)

LIVE_PROOF_TERMS = (
    "bending_fail_blocked_ownership_proof",
    "repair_reason_proof",
    "blocked_ownership_proof",
    "bending_fail_repair_blocked",
    "bending_fail_contract_strategy_exhaustion_proven",
    "bending_fail_hard_blocker_proven",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _latest(prefix: str) -> Path | None:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    return paths[-1] if paths else None


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _latest_browser_payload() -> dict[str, Any]:
    path = _latest("design_guide_controller_browser_live_trace_parity")
    if not path:
        return {"path": None, "payload": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        payload = {"read_error": f"{type(exc).__name__}: {exc}"}
    return {"path": str(path), "payload": payload}


def _live_payload_terms(payload: dict[str, Any]) -> dict[str, Any]:
    live = _as_dict(payload.get("live_trace"))
    diagnostics = list(live.get("state_diagnostics") or [])
    latest_diag = _as_dict(diagnostics[-1] if diagnostics else {})
    text = json.dumps(payload, sort_keys=True, default=str)
    return {
        "live_trace_present": bool(live),
        "latest_primary_card_title": latest_diag.get("primary_card_title"),
        "selected_family": live.get("selected_family"),
        "outcome_state": live.get("outcome_state"),
        "terms_present": {term: term in text for term in LIVE_PROOF_TERMS},
        "diagnostic_incomplete_card": str(latest_diag.get("primary_card_title") or "").strip()
        == "Bending repair proof incomplete",
    }


def main() -> int:
    created_at = datetime.now().replace(microsecond=0).isoformat()
    runtime_path = ROOT / "design_brain" / "families" / "bending_fail_governs" / "runtime.py"
    family_path = ROOT / "design_brain" / "families" / "bending_fail.py"
    page_path = ROOT / "inputs_page.py"

    runtime_text = _read(runtime_path)
    family_text = _read(family_path)
    page_text = _read(page_path)
    browser = _latest_browser_payload()
    browser_payload = _as_dict(browser.get("payload"))
    live_terms = _live_payload_terms(browser_payload)

    runtime_terms = {term: term in runtime_text for term in REQUIRED_RUNTIME_TERMS}
    family_mapping_terms = {term: term in family_text for term in REQUIRED_PAGE_RECOGNIZER_TERMS}
    page_recognizer_terms = {term: term in page_text for term in REQUIRED_PAGE_RECOGNIZER_TERMS}

    runtime_contract_proof_exists = all(runtime_terms.values())
    family_exports_proof_surface = all(family_mapping_terms.values())
    page_recognizer_knows_surface = all(page_recognizer_terms.values())
    live_payload_has_any_family_proof = any(_as_dict(live_terms.get("terms_present")).values())
    live_payload_is_diagnostic = bool(live_terms.get("diagnostic_incomplete_card"))

    decision = (
        "LIVE_PROOF_NOT_RECOGNISED"
        if runtime_contract_proof_exists
        and family_exports_proof_surface
        and page_recognizer_knows_surface
        and live_payload_is_diagnostic
        and not live_payload_has_any_family_proof
        else "PROOF_CHAIN_PRESENT_OR_DIFFERENT_GAP"
    )
    status = "PASS"
    payload = {
        "schema": "design_guide_bending_fail_family_proof_recognition_audit.v1",
        "created_at": created_at,
        "status": status,
        "decision": decision,
        "product_behaviour_changed": False,
        "family_runtimes_changed": False,
        "contracts_changed": False,
        "cta_publication_apply_changed": False,
        "runtime_contract_proof_exists": runtime_contract_proof_exists,
        "family_exports_proof_surface": family_exports_proof_surface,
        "page_recognizer_knows_surface": page_recognizer_knows_surface,
        "live_payload_has_any_family_proof": live_payload_has_any_family_proof,
        "live_payload_is_diagnostic": live_payload_is_diagnostic,
        "runtime_terms": runtime_terms,
        "family_mapping_terms": family_mapping_terms,
        "page_recognizer_terms": page_recognizer_terms,
        "live_terms": live_terms,
        "latest_browser_artifact": browser.get("path"),
        "next_safe_step": (
            "Trace the family result/evidence handoff for BENDING_FAIL_GOVERNS and "
            "carry the existing locked runtime blocked_ownership_proof into the "
            "candidate_search_evidence consumed by the page recognizer."
        ),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bending_fail_family_proof_recognition_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_bending_fail_family_proof_recognition_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide BENDING_FAIL Family Proof Recognition Audit",
                "",
                f"Status: `{status}`",
                f"Decision: `{decision}`",
                "",
                "## Findings",
                "",
                f"- Runtime contract proof fields exist: `{runtime_contract_proof_exists}`",
                f"- Family adapter exports proof surface: `{family_exports_proof_surface}`",
                f"- Page recognizer knows proof surface: `{page_recognizer_knows_surface}`",
                f"- Latest live payload is diagnostic card: `{live_payload_is_diagnostic}`",
                f"- Latest live payload carries family proof terms: `{live_payload_has_any_family_proof}`",
                f"- Latest browser artifact: `{browser.get('path')}`",
                "",
                "## Next Safe Step",
                "",
                payload["next_safe_step"],
                "",
                "No product behaviour, CTA/publication/apply routing, contracts, or family runtimes were changed.",
            ]
        ),
        encoding="utf-8",
    )
    print(f"status: {status}")
    print(f"decision: {decision}")
    print(f"json: {json_path}")
    print(f"report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
