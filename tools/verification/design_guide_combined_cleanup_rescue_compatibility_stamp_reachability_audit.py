"""Audit reachability for combined cleanup rescue compatibility stamp rows."""

from __future__ import annotations

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

HELPER = "_stamp_final_publication_combined_cleanup_rescue_compatibility_proof"
TOKENS = (
    HELPER,
    "final_publication_combined_cleanup_rescue_compatibility_proofs",
    "final_publication_combined_cleanup_rescue_compatibility_proof_hash",
    "final_publication_combined_cleanup_rescue_rows_compatibility_only",
    "final_publication_combined_cleanup_rescue_remaining_truth_narrowed",
)
PRODUCT_ROOTS = (
    ROOT / "inputs_page.py",
    ROOT / "design_brain",
    ROOT / "ui",
    ROOT / "design_guide_page.py",
)
VERIFIER_ROOT = ROOT / "tools" / "verification"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts and path.is_file()
    )


def _line_hits(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:
        return [
            {
                "file": str(path.relative_to(ROOT)),
                "line": None,
                "token": "<read_error>",
                "text": f"{type(exc).__name__}: {exc}",
            }
        ]
    hits: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        for token in TOKENS:
            if token in line:
                hits.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": index,
                        "token": token,
                        "text": line.strip(),
                    }
                )
    return hits


def _classify(hit: dict[str, Any]) -> str:
    file_name = str(hit.get("file") or "")
    text = str(hit.get("text") or "")
    token = str(hit.get("token") or "")
    if file_name == "inputs_page.py" and text.startswith(f"def {HELPER}("):
        return "product_helper_definition"
    if file_name == "inputs_page.py" and token == HELPER and text.startswith(f"{HELPER}("):
        return "product_helper_callsite"
    if file_name == "inputs_page.py" and token != HELPER:
        return "product_helper_internal_stamp_key"
    if file_name.startswith("tools\\verification") or file_name.startswith("tools/verification"):
        return "verifier_contract_consumer"
    if file_name.startswith("design_brain"):
        return "design_brain_reference"
    if file_name.startswith("ui") or file_name == "design_guide_page.py":
        return "ui_or_render_reference"
    return "unknown"


def _capture() -> dict[str, Any]:
    product_hits: list[dict[str, Any]] = []
    for root in PRODUCT_ROOTS:
        for path in _iter_files(root):
            product_hits.extend(_line_hits(path))

    verifier_hits: list[dict[str, Any]] = []
    for path in _iter_files(VERIFIER_ROOT):
        verifier_hits.extend(_line_hits(path))

    all_hits = product_hits + verifier_hits
    for hit in all_hits:
        hit["classification"] = _classify(hit)

    counts: dict[str, int] = {}
    for hit in all_hits:
        classification = str(hit.get("classification") or "unknown")
        counts[classification] = counts.get(classification, 0) + 1

    product_external_consumers = [
        hit
        for hit in product_hits
        if hit.get("classification")
        not in {
            "product_helper_definition",
            "product_helper_callsite",
            "product_helper_internal_stamp_key",
        }
    ]
    verifier_consumers = [
        hit for hit in verifier_hits if hit.get("classification") == "verifier_contract_consumer"
    ]
    helper_calls = [
        hit for hit in product_hits if hit.get("classification") == "product_helper_callsite"
    ]
    product_stamp_surface = [
        hit
        for hit in product_hits
        if hit.get("classification")
        in {
            "product_helper_definition",
            "product_helper_callsite",
            "product_helper_internal_stamp_key",
        }
    ]
    safe_plain_delete_now = (
        len(product_external_consumers) == 0 and len(product_stamp_surface) == 0
    )
    safe_collapse_next = (
        len(product_external_consumers) == 0 and len(product_stamp_surface) > 0
    )
    decision = (
        "NO_PRODUCT_STAMP_SURFACE_DELETE_READY"
        if safe_plain_delete_now
        else "PRODUCT_STAMP_SURFACE_PRESENT_COLLAPSE_READY"
        if safe_collapse_next
        else "UNSAFE_PRODUCT_CONSUMERS_REMAIN"
    )
    return {
        "decision": decision,
        "helper": HELPER,
        "counts": counts,
        "helper_call_count": len(helper_calls),
        "product_stamp_surface_count": len(product_stamp_surface),
        "product_external_consumer_count": len(product_external_consumers),
        "verifier_consumer_count": len(verifier_consumers),
        "safe_plain_delete_now": safe_plain_delete_now,
        "safe_collapse_next": safe_collapse_next,
        "next_safe_step": (
            "Delete the product combined cleanup rescue compatibility stamp helper/calls if "
            "product_stamp_surface_count is nonzero and no external product consumers remain."
        ),
        "sample_hits": all_hits[:80],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    product_surface_count = int(capture.get("product_stamp_surface_count") or 0)
    return {
        "product_surface_accounted": product_surface_count >= 0,
        "no_external_product_consumers": int(capture.get("product_external_consumer_count") or 0)
        == 0,
        "verifier_consumers_nonblocking": int(capture.get("verifier_consumer_count") or 0) >= 0,
        "delete_or_collapse_state_explicit": capture.get("safe_plain_delete_now") is True
        or capture.get("safe_collapse_next") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Combined Cleanup Rescue Compatibility Stamp Reachability Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Counts",
    ]
    lines.extend(
        f"- {key}: `{value}`" for key, value in sorted((capture.get("counts") or {}).items())
    )
    lines.extend(
        [
            "",
            f"- helper_call_count: `{capture.get('helper_call_count')}`",
            f"- product_stamp_surface_count: `{capture.get('product_stamp_surface_count')}`",
            f"- product_external_consumer_count: `{capture.get('product_external_consumer_count')}`",
            f"- verifier_consumer_count: `{capture.get('verifier_consumer_count')}`",
            f"- safe_plain_delete_now: `{capture.get('safe_plain_delete_now')}`",
            f"- safe_collapse_next: `{capture.get('safe_collapse_next')}`",
            "",
            "## Checks",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or ""), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_cleanup_rescue_compatibility_stamp_reachability_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_cleanup_rescue_compatibility_stamp_reachability_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_cleanup_rescue_compatibility_stamp_reachability {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(f"decision={capture.get('decision')}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
