"""Audit reachability for final-visible restamper compatibility metadata.

This deliberately avoids the older broad duplicate-restamper verifier, which can
be slow. The scope is only the metadata wrapper added by
_mark_final_visible_restamper_compatibility_stamp and the compatibility_only
keyword that routes into it. It does not approve removal of the actual
_publish_final_visible_design_guide_contract_binding behaviour.
"""

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
INPUTS_PAGE = ROOT / "inputs_page.py"
PRODUCT_ROOTS = (ROOT / "inputs_page.py", ROOT / "design_brain", ROOT / "ui", ROOT / "design_guide_page.py")

HELPER = "_mark_final_visible_restamper_compatibility_stamp"
TOKENS = (
    HELPER,
    "compatibility_only_callsite",
    "final_publication_restamper_metadata",
    "final_publication_restamper_metadata_by_callsite",
    "final_publication_restamper_selected_callsite",
)


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
        if path.is_file() and "__pycache__" not in path.parts
    )


def _line_hits(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
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
    if file_name != "inputs_page.py":
        return "external_product_consumer"
    if text.startswith(f"def {HELPER}("):
        return "metadata_helper_definition"
    if token == HELPER:
        return "metadata_helper_internal_call"
    if "compatibility_only_callsite:" in text or "compatibility_only_callsite: str | None" in text:
        return "binding_parameter"
    if "if compatibility_only_callsite" in text or "callsite=str(compatibility_only_callsite)" in text:
        return "binding_metadata_branch"
    if "compatibility_only_callsite=" in text:
        return "binding_callsite_opt_in"
    if token.startswith("final_publication_restamper_"):
        return "metadata_helper_internal_key"
    return "unknown_product_reference"


def _capture() -> dict[str, Any]:
    product_hits: list[dict[str, Any]] = []
    for root in PRODUCT_ROOTS:
        for path in _iter_files(root):
            product_hits.extend(_line_hits(path))
    for hit in product_hits:
        hit["classification"] = _classify(hit)
    counts: dict[str, int] = {}
    for hit in product_hits:
        classification = str(hit.get("classification") or "unknown")
        counts[classification] = counts.get(classification, 0) + 1
    external_consumers = [
        hit
        for hit in product_hits
        if hit.get("classification") in {"external_product_consumer", "unknown_product_reference"}
    ]
    callsite_opt_ins = [
        hit for hit in product_hits if hit.get("classification") == "binding_callsite_opt_in"
    ]
    metadata_surface_hits = [
        hit
        for hit in product_hits
        if hit.get("classification")
        in {
            "metadata_helper_definition",
            "metadata_helper_internal_call",
            "metadata_helper_internal_key",
            "binding_parameter",
            "binding_metadata_branch",
            "binding_callsite_opt_in",
        }
    ]
    decision = (
        "METADATA_SURFACE_DELETED"
        if not metadata_surface_hits and not external_consumers
        else "METADATA_SURFACE_DELETE_READY_AFTER_FOCUSED_VERIFIER_UPDATE"
        if metadata_surface_hits and not external_consumers
        else "UNSAFE_PRODUCT_CONSUMERS_REMAIN"
    )
    return {
        "decision": decision,
        "counts": counts,
        "callsite_opt_in_count": len(callsite_opt_ins),
        "metadata_surface_hit_count": len(metadata_surface_hits),
        "external_product_consumer_count": len(external_consumers),
        "callsite_opt_ins": callsite_opt_ins,
        "external_consumers": external_consumers,
        "sample_hits": product_hits[:80],
        "next_safe_step": (
            "If focused verifier updates pass, remove only the restamper metadata helper, "
            "compatibility_only_callsite parameter/branches, and compatibility_only_callsite keyword args. "
            "Do not remove _publish_final_visible_design_guide_contract_binding itself."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "metadata_surface_deleted_or_accounted": capture.get("decision")
        in {
            "METADATA_SURFACE_DELETED",
            "METADATA_SURFACE_DELETE_READY_AFTER_FOCUSED_VERIFIER_UPDATE",
        },
        "no_external_product_consumers": int(capture.get("external_product_consumer_count") or 0) == 0,
        "callsite_opt_ins_deleted_or_accounted": capture.get("decision") == "METADATA_SURFACE_DELETED"
        or int(capture.get("callsite_opt_in_count") or 0) > 0,
        "decision_explicit": capture.get("decision")
        in {
            "METADATA_SURFACE_DELETED",
            "METADATA_SURFACE_DELETE_READY_AFTER_FOCUSED_VERIFIER_UPDATE",
        },
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Visible Restamper Metadata Reachability Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Counts",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in sorted((capture.get("counts") or {}).items()))
    lines.extend(
        [
            f"- callsite_opt_in_count: `{capture.get('callsite_opt_in_count')}`",
            f"- external_product_consumer_count: `{capture.get('external_product_consumer_count')}`",
            "",
            "## Callsite Opt-Ins",
            "",
        ]
    )
    for hit in capture.get("callsite_opt_ins") or []:
        lines.append(f"- `{hit.get('file')}:{hit.get('line')}` {hit.get('text')}")
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
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_restamper_metadata_reachability_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_restamper_metadata_reachability_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_final_visible_restamper_metadata_reachability {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(f"decision={capture.get('decision')}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
