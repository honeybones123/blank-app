from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.source_fingerprint import compute_source_fingerprint  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _latest_batch_artifact() -> Path | None:
    paths = sorted(
        ARTIFACT_DIR.glob("design_brain_universal_fuzz_family_batches_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return paths[0] if paths else None


def _index_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("scenario_id") or ""): dict(row)
        for row in rows
        if isinstance(row, dict) and row.get("scenario_id")
    }


def _family_rows(family_payload: dict[str, Any]) -> list[dict[str, Any]]:
    published = _index_rows(list(family_payload.get("published_result") or []))
    button = _index_rows(list(family_payload.get("button_action_payload") or []))
    rows: list[dict[str, Any]] = []
    for scenario_id in sorted(set(published) | set(button)):
        pub = _mapping(published.get(scenario_id))
        button_row = _mapping(button.get(scenario_id))
        probe = _mapping(pub.get("publication_probe_before"))
        cta = _mapping(probe.get("cta"))
        button_probe = _mapping(button_row.get("button_probe_before"))
        visible_enabled_actions = int(button_probe.get("enabled_action_count") or 0)
        action_type = str(cta.get("action_type") or cta.get("intent") or "").strip()
        updates = _mapping(cta.get("updates"))
        family_id = str(
            probe.get("selected_family_id")
            or cta.get("family_id")
            or cta.get("family")
            or ""
        ).strip().upper()
        rows.append(
            {
                "scenario_id": scenario_id,
                "selected_family_id": family_id,
                "publication_hash_present": bool(probe.get("publication_hash")),
                "authority_hash_present": bool(probe.get("authority_hash")),
                "visible_enabled_action_count": visible_enabled_actions,
                "publication_cta_action_type": action_type,
                "publication_cta_updates": updates,
                "publication_cta_family_id": str(
                    cta.get("family_id") or cta.get("family") or ""
                ).strip().upper(),
                "publication_blocker_reason": probe.get("blocker_reason"),
                "publication_outcome_state": probe.get("outcome_state"),
                "parity": bool(
                    visible_enabled_actions <= 0
                    or (action_type and updates and family_id and family_id != "OTHER")
                ),
            }
        )
    return rows


def _run(source_artifact: Path) -> dict[str, Any]:
    payload = json.loads(source_artifact.read_text(encoding="utf-8"))
    families = list(payload.get("families") or [])
    expanded_families: list[dict[str, Any]] = []
    for family_payload in families:
        family_d = _mapping(family_payload)
        artifact_value = family_d.get("artifact")
        if artifact_value:
            artifact_path = Path(str(artifact_value))
            if not artifact_path.is_absolute():
                artifact_path = ROOT / artifact_path
            try:
                child = json.loads(artifact_path.read_text(encoding="utf-8"))
                child_families = list(child.get("families") or [])
                if child_families:
                    expanded_families.extend(
                        _mapping(child_family) for child_family in child_families
                    )
                    continue
            except (OSError, json.JSONDecodeError):
                pass
        expanded_families.append(family_d)
    families = expanded_families
    family_results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for family_payload in families:
        family = str(_mapping(family_payload).get("family") or "").strip()
        rows = _family_rows(_mapping(family_payload))
        for row in rows:
            if not row["parity"]:
                failures.append(
                    {
                        "family": family,
                        "scenario_id": row["scenario_id"],
                        "reason": "visible_enabled_action_without_shared_publication_cta",
                        "row": row,
                    }
                )
        family_results.append(
            {
                "family": family,
                "scenario_count": len(rows),
                "passed": sum(bool(row["parity"]) for row in rows),
                "failed": sum(not bool(row["parity"]) for row in rows),
                "rows": rows,
            }
        )

    source_fingerprint = compute_source_fingerprint(repo=ROOT)
    status = "PASS" if not failures and family_results else "FAIL"
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    result = {
        "schema": "design_brain_shared_family_route_consistency_snapshot.v1",
        "status": status,
        "source_artifact": str(source_artifact),
        "source_fingerprint": source_fingerprint,
        "family_count": len(family_results),
        "family_results": family_results,
        "failures": failures,
        "checks": {
            "family_publication_cta_parity": not failures,
            "visible_enabled_action_requires_shared_cta": not failures,
            "other_family_empty_payload_rejected": not any(
                row.get("publication_cta_family_id") == "OTHER"
                and not row.get("publication_cta_updates")
                for family in family_results
                for row in family["rows"]
            ),
        },
        "generated_at": stamp,
    }
    json_path = ARTIFACT_DIR / f"design_brain_shared_family_route_consistency_snapshot_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_shared_family_route_consistency_snapshot_{stamp}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Shared Family Route Consistency Snapshot",
        "",
        f"Status: **{status}**",
        f"Source artifact: `{source_artifact}`",
        f"Families covered: **{len(family_results)}**",
        "",
        "## Checks",
        "",
        f"- Visible enabled actions require shared publication CTA intent: **{'PASS' if result['checks']['visible_enabled_action_requires_shared_cta'] else 'FAIL'}**",
        f"- Family publication and CTA identity parity: **{'PASS' if result['checks']['family_publication_cta_parity'] else 'FAIL'}**",
        f"- `OTHER` empty action payload rejected: **{'PASS' if result['checks']['other_family_empty_payload_rejected'] else 'FAIL'}**",
        "",
        "## Family Results",
        "",
    ]
    for family in family_results:
        lines.append(
            f"- `{family['family']}`: {family['passed']} passed, {family['failed']} failed of {family['scenario_count']}"
        )
    if failures:
        lines.extend(["", "## Failures", ""])
        for failure in failures:
            lines.append(
                f"- `{failure['family']}` / `{failure['scenario_id']}`: {failure['reason']}"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "An enabled visible action is shared-contract consistent only when the authoritative publication exposes a non-empty action type, updates, and family identity. This snapshot is proof-only and does not render, apply, mutate candidates, or change product routing.",
            "",
            f"Machine-readable result: `{json_path}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "json": str(json_path), "report": str(md_path), "failures": failures}, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, default=None)
    args = parser.parse_args()
    source_artifact = args.artifact or _latest_batch_artifact()
    if source_artifact is None:
        print("No universal batch artifact found", file=sys.stderr)
        return 2
    result = _run(source_artifact.resolve())
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
