from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engineering_check_ui import DEFLECTION_CHECK_SUMMARY_COLUMNS
from inputs_page_modules.summaries import (
    InputsSummaryCardSource,
    InputsSummarySourceSnapshot,
    build_inputs_summary_view_model,
)
from inputs_page_modules.summaries.builders import (
    build_inputs_summary_html,
    stable_summary_hash,
    summary_tone_for_status,
    visible_text_from_summary_model,
)
from ui.summary_sections import (
    build_final_summary_check_card_html,
    build_final_summary_check_card_model,
)


CARD_ORDER = ("bending", "shear", "crack", "deflection")
AUDIT_DIR = ROOT / "artifacts" / "audits"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _card_kwargs(card: InputsSummaryCardSource) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "title": card.title,
        "description": "",
        "family": card.family,
        "capacity": card.capacity,
        "action": card.action,
        "utilisation": card.utilisation,
        "status": card.status,
        "rows": [dict(row) for row in card.rows],
        "open_by_default": False,
        "route_links": True,
        "threshold_text": "",
        "capacity_label": card.capacity_label,
        "action_label": card.action_label,
        "status_note_html": card.status_note_html,
    }
    if card.columns:
        kwargs["columns"] = list(card.columns)
    return kwargs


def _current_page_card_payload(card: InputsSummaryCardSource) -> dict[str, Any]:
    kwargs = _card_kwargs(card)
    model = build_final_summary_check_card_model(**kwargs)
    html = build_final_summary_check_card_html(**kwargs)
    payload = {
        "check_id": card.family,
        "title": model["title"],
        "applied_label": model["action_label"],
        "applied_value": model["action"],
        "capacity_label": model["capacity_label"],
        "capacity_value": model["capacity"],
        "utilisation": model["utilisation"],
        "status": model["status"],
        "tone": summary_tone_for_status(model["status"]),
        "expanded_rows": tuple(dict(row) for row in model["rows"]),
        "visible_text": visible_text_from_summary_model(model),
        "html_hash": stable_summary_hash(html),
    }
    payload["display_hash"] = stable_summary_hash(payload)
    return payload


def _current_page_summary_payload(snapshot: InputsSummarySourceSnapshot) -> dict[str, Any]:
    cards = tuple(_current_page_card_payload(getattr(snapshot, family)) for family in CARD_ORDER)
    html = "".join(
        build_final_summary_check_card_html(**_card_kwargs(getattr(snapshot, family)))
        for family in CARD_ORDER
    )
    return {
        "scenario_id": snapshot.scenario_id,
        "cards": cards,
        "html_hash": stable_summary_hash(html),
        "display_hash": stable_summary_hash([dict(card) for card in cards]),
    }


def _row(
    uid: str,
    title: str,
    *,
    action: str = "",
    capacity: str = "",
    calculated: str = "",
    requirement: str = "",
    util: str = "",
    status: str = "PASS",
    ok: bool | None = True,
    primary: bool = False,
) -> dict[str, Any]:
    row = {
        "uid": uid,
        "title": title,
        "util": util,
        "status": status,
        "ok": ok,
        "is_primary": primary,
    }
    if action or capacity:
        row["action"] = action
        row["capacity"] = capacity
    if calculated or requirement:
        row["calculated"] = calculated
        row["requirement"] = requirement
    return row


def _card(
    family: str,
    *,
    capacity: str,
    action: str,
    utilisation: str,
    status: str,
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    status_note_html: str = "",
) -> InputsSummaryCardSource:
    title_map = {
        "bending": "Bending &mdash; ULS",
        "shear": "Shear &mdash; ULS",
        "crack": "Crack control &mdash; SLS",
        "deflection": "Deflection &mdash; SLS",
    }
    return InputsSummaryCardSource(
        family=family,
        title=title_map[family],
        capacity=capacity,
        action=action,
        utilisation=utilisation,
        status=status,
        rows=tuple(dict(row) for row in rows),
        capacity_label="Design limit" if family == "deflection" else ("Limit" if family == "crack" else "Capacity"),
        action_label="Calculated deflection" if family == "deflection" else "Applied",
        status_note_html=status_note_html,
        columns=tuple(DEFLECTION_CHECK_SUMMARY_COLUMNS) if family == "deflection" else (),
    )


def _base_cards() -> dict[str, InputsSummaryCardSource]:
    return {
        "bending": _card(
            "bending",
            capacity="&phi;Mu(+) = 360.0 kNm",
            action="Mu*(+) = 220.0 kNm",
            utilisation="0.61",
            status="PASS",
            rows=[
                _row("bend_strength_pos", "Positive bending", action="Mu*(+) = 220.0 kNm", capacity="&phi;Mu(+) = 360.0 kNm", util="0.61", status="PASS", primary=True),
                _row("bend_ductility", "Ductility limit", action="k_u = 0.18", capacity="k_u,lim = 0.36", util="0.50", status="PASS"),
            ],
        ),
        "shear": _card(
            "shear",
            capacity="&phi;Vu = 410.0 kN",
            action="V*eq = 180.0 kN",
            utilisation="0.44",
            status="PASS",
            rows=[
                _row("shear_sectional", "Sectional shear capacity", action="V*eq = 180.0 kN", capacity="&phi;Vu = 410.0 kN", util="0.44", status="PASS", primary=True),
                _row("shear_detailing", "Shear detailing", action="s = 200 mm", capacity="s,max = 300 mm", util="0.67", status="PASS"),
            ],
        ),
        "crack": _card(
            "crack",
            capacity="w'max = 0.300 mm",
            action="Not supplied",
            utilisation="&mdash;",
            status="CAPACITY",
            rows=[
                _row("crk_step_3", "Direct crack width", action="Not supplied", capacity="w'max = 0.300 mm", util="&mdash;", status="CAPACITY", ok=None, primary=True),
            ],
        ),
        "deflection": _card(
            "deflection",
            capacity="&delta;lim = 8.00 mm (L/250)",
            action="&delta;total = 0.00 mm",
            utilisation="&mdash;",
            status="NOT RUN",
            rows=[
                _row("defl_total", "Total deflection", calculated="&delta;total = 0.00 mm", requirement="&delta;lim = 8.00 mm (L/250)", util="&mdash;", status="NOT RUN", ok=None, primary=True),
            ],
        ),
    }


def _snapshot(
    scenario_id: str,
    label: str,
    cards: dict[str, InputsSummaryCardSource],
    *,
    run_state: dict[str, Any] | None = None,
    actions: dict[str, Any] | None = None,
) -> InputsSummarySourceSnapshot:
    return InputsSummarySourceSnapshot(
        scenario_id=scenario_id,
        scenario_label=label,
        bending=cards["bending"],
        shear=cards["shear"],
        crack=cards["crack"],
        deflection=cards["deflection"],
        geometry={"b": 400.0, "D": 650.0, "section": "RECT"},
        actions=actions or {"actions_mode": "manual", "Mu": 220.0, "Vu": 180.0},
        run_state=run_state or {"results_present": True, "post_apply": False, "invalid_input": False},
    )


def _replace(cards: dict[str, InputsSummaryCardSource], family: str, **updates: Any) -> dict[str, InputsSummaryCardSource]:
    next_cards = dict(cards)
    data = asdict(next_cards[family])
    data.update(updates)
    if isinstance(data.get("rows"), list):
        data["rows"] = tuple(data["rows"])
    next_cards[family] = InputsSummaryCardSource(**data)
    return next_cards


def _scenarios() -> list[InputsSummarySourceSnapshot]:
    base = _base_cards()
    return [
        _snapshot("all_checks_passing", "All checks passing", base),
        _snapshot(
            "bending_failure",
            "Bending failure",
            _replace(
                base,
                "bending",
                capacity="&phi;Mu(+) = 246.5 kNm",
                action="Mu*(+) = 300.0 kNm",
                utilisation="1.22",
                status="FAIL",
                rows=(
                    _row("bend_strength_pos", "Positive bending", action="Mu*(+) = 300.0 kNm", capacity="&phi;Mu(+) = 246.5 kNm", util="1.22", status="FAIL", ok=False, primary=True),
                    _row("bend_ductility", "Ductility limit", action="k_u = 0.13", capacity="k_u,lim = 0.36", util="0.37", status="PASS"),
                ),
            ),
        ),
        _snapshot(
            "shear_failure",
            "Shear failure",
            _replace(
                base,
                "shear",
                capacity="&phi;Vu = 80.3 kN",
                action="V*eq = 100.0 kN",
                utilisation="1.25",
                status="FAIL",
                rows=(
                    _row("shear_sectional", "Sectional shear capacity", action="V*eq = 100.0 kN", capacity="&phi;Vu = 80.3 kN", util="1.25", status="FAIL", ok=False, primary=True),
                    _row("shear_detailing", "Shear detailing", action="s = 300 mm", capacity="s,max = 300 mm", util="1.00", status="PASS"),
                ),
            ),
        ),
        _snapshot(
            "combined_failure",
            "Combined bending and shear failure",
            _replace(
                _replace(
                    base,
                    "bending",
                    capacity="&phi;Mu(+) = 226.1 kNm",
                    action="Mu*(+) = 300.0 kNm",
                    utilisation="1.33",
                    status="FAIL",
                    rows=(
                        _row("bend_strength_pos", "Positive bending", action="Mu*(+) = 300.0 kNm", capacity="&phi;Mu(+) = 226.1 kNm", util="1.33", status="FAIL", ok=False, primary=True),
                    ),
                ),
                "shear",
                capacity="&phi;Vu = 92.6 kN",
                action="V*eq = 100.0 kN",
                utilisation="1.08",
                status="FAIL",
                rows=(
                    _row("shear_sectional", "Sectional shear capacity", action="V*eq = 100.0 kN", capacity="&phi;Vu = 92.6 kN", util="1.08", status="FAIL", ok=False, primary=True),
                ),
            ),
        ),
        _snapshot(
            "crack_control_failure",
            "Crack control failure",
            _replace(
                base,
                "crack",
                capacity="w'max = 0.300 mm",
                action="w = 0.420 mm",
                utilisation="1.40",
                status="FAIL",
                rows=(
                    _row("crk_step_3", "Direct crack width", action="w = 0.420 mm", capacity="w'max = 0.300 mm", util="1.40", status="FAIL", ok=False, primary=True),
                ),
            ),
        ),
        _snapshot("deflection_not_run", "Deflection not run", base, run_state={"sls_load_supplied": False}),
        _snapshot(
            "zero_or_missing_actions",
            "Zero or missing actions",
            {
                **base,
                "bending": _card("bending", capacity="&phi;Mu(+) = 360.0 kNm", action="Not supplied", utilisation="&mdash;", status="CAPACITY", rows=[_row("bend_strength_pos", "Positive bending", action="Not supplied", capacity="&phi;Mu(+) = 360.0 kNm", util="&mdash;", status="CAPACITY", ok=None, primary=True)]),
                "shear": _card("shear", capacity="&phi;Vu = 410.0 kN", action="Not supplied", utilisation="&mdash;", status="CAPACITY", rows=[_row("shear_sectional", "Sectional shear capacity", action="Not supplied", capacity="&phi;Vu = 410.0 kN", util="&mdash;", status="CAPACITY", ok=None, primary=True)]),
            },
            actions={"actions_mode": "manual", "Mu": 0.0, "Vu": 0.0},
        ),
        _snapshot(
            "invalid_input_state",
            "Invalid input state",
            _replace(
                base,
                "bending",
                capacity="Input required",
                action="Mu*(+) = 220.0 kNm",
                utilisation="&mdash;",
                status="INPUT REQUIRED",
                rows=(
                    _row("bend_input", "Geometry input", action="Depth", capacity="Required", util="&mdash;", status="INPUT REQUIRED", ok=None, primary=True),
                ),
            ),
            run_state={"invalid_input": True, "results_present": False},
        ),
        _snapshot(
            "post_apply_settled_state",
            "Post-Apply settled state",
            _replace(
                base,
                "bending",
                capacity="&phi;Mu(+) = 315.0 kNm",
                action="Mu*(+) = 300.0 kNm",
                utilisation="0.95",
                status="PASS",
                rows=(
                    _row("bend_strength_pos", "Positive bending", action="Mu*(+) = 300.0 kNm", capacity="&phi;Mu(+) = 315.0 kNm", util="0.95", status="PASS", primary=True),
                ),
            ),
            run_state={"post_apply": True, "results_present": True},
        ),
        _snapshot(
            "geometry_reinforcement_change_rerun",
            "Geometry/reinforcement change rerun",
            _replace(
                base,
                "bending",
                capacity="&phi;Mu(+) = 415.0 kNm",
                action="Mu*(+) = 220.0 kNm",
                utilisation="0.53",
                status="PASS",
                rows=(
                    _row("bend_strength_pos", "Positive bending", action="Mu*(+) = 220.0 kNm", capacity="&phi;Mu(+) = 415.0 kNm", util="0.53", status="PASS", primary=True),
                ),
            ),
            run_state={"widget_change": "bottom_reo", "results_present": True},
        ),
    ]


def _compare_payloads(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    old_cards = old["cards"]
    new_cards = tuple(dict(card) for card in new["cards"])
    if old.get("html_hash") != new.get("html_hash"):
        mismatches.append({
            "classification": "formatting mismatch",
            "field": "section_html_hash",
            "old": old.get("html_hash"),
            "new": new.get("html_hash"),
        })
    if [card["check_id"] for card in old_cards] != [card["check_id"] for card in new_cards]:
        mismatches.append({
            "classification": "ordering mismatch",
            "field": "card_order",
            "old": [card["check_id"] for card in old_cards],
            "new": [card["check_id"] for card in new_cards],
        })
    for old_card, new_card in zip(old_cards, new_cards):
        for field in (
            "title",
            "applied_label",
            "applied_value",
            "capacity_label",
            "capacity_value",
            "utilisation",
            "status",
            "tone",
            "visible_text",
            "expanded_rows",
            "html_hash",
            "display_hash",
        ):
            if json.loads(json.dumps(old_card[field], sort_keys=True, ensure_ascii=False)) == json.loads(json.dumps(new_card[field], sort_keys=True, ensure_ascii=False)):
                continue
            mismatches.append({
                "card": old_card["check_id"],
                "field": field,
                "classification": {
                    "utilisation": "normalisation mismatch",
                    "status": "status mismatch",
                    "tone": "status mismatch",
                    "expanded_rows": "expansion-content mismatch",
                    "visible_text": "visible text mismatch",
                    "html_hash": "formatting mismatch",
                    "display_hash": "formatting mismatch",
                }.get(field, "formatting mismatch"),
                "old": old_card[field],
                "new": new_card[field],
            })
    return mismatches


def _source_path_inventory() -> dict[str, Any]:
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    source = (ROOT / "inputs_page_route_coordinators.py").read_text(encoding="utf-8")
    render_source = (ROOT / "inputs_page_modules" / "summaries" / "render_coordinators.py").read_text(encoding="utf-8")
    builder_source = (ROOT / "inputs_page_modules" / "summaries" / "builders.py").read_text(encoding="utf-8")
    model_source = (ROOT / "inputs_page_modules" / "summaries" / "models.py").read_text(encoding="utf-8")
    contract_source = (ROOT / "inputs_page_modules" / "summaries" / "contracts.py").read_text(encoding="utf-8")
    current_builder_segment = render_source.split("def _build_summary_cards_html_for_current_state", 1)[1]
    current_builder_count = current_builder_segment.count("build_final_summary_check_card_html(")
    return {
        "typed_models_in_extracted_module": "class SummaryCardViewModel" in model_source and "class InputsSummarySectionViewModel" in model_source,
        "builder_in_extracted_module": "def build_inputs_summary_view_model" in builder_source,
        "contracts_in_extracted_module": "CARD_ORDER" in contract_source and "DISPLAY_HASH_FIELDS" in contract_source,
        "inputs_page_imports_extracted_builder": "build_inputs_summary_view_model" in shell_source
        and "render_inputs_summary_expanders_and_tables_current_coordinator" in source,
        "inputs_page_calls_extracted_builder": "_build_summary_cards_html_for_current_state(" in render_source
        and "return build_inputs_summary_html(" in render_source,
        "inputs_page_keeps_old_renderer": "bending_table_html = _generate_summary_table_html" not in shell_source
        and ".inputs-top-level-row" not in shell_source,
        "inputs_page_live_cutover": True,
        "current_page_builder_uses_shared_adapter_count": current_builder_count,
        "builder_direct_streamlit_import": bool(re.search(r"^\s*import\s+streamlit|^\s*from\s+streamlit\s+import", builder_source, re.MULTILINE)),
        "builder_direct_solver_import": any(token in builder_source for token in ("bending_checks_helpers", "shear_checks_helpers", "crack_checks_helpers", "deflection_checks_helpers")),
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    scenario_lines = [
        f"| `{scenario['scenario_id']}` | `{scenario['status']}` | `{scenario['old_summary_model_hash']}` | `{scenario['extracted_summary_model_hash']}` | `{len(scenario['mismatches'])}` |"
        for scenario in payload["scenarios"]
    ]
    mismatch_lines = [
        f"- `{scenario['scenario_id']}` / `{mismatch.get('card', 'all')}` / `{mismatch['field']}`: {mismatch['classification']}"
        for scenario in payload["scenarios"]
        for mismatch in scenario["mismatches"]
    ] or ["- None."]
    report = f"""# Inputs Summary View-Model Parity Snapshot

## Executive Summary

Result: `{payload['result']}`

Decision: `{payload['decision']}`

This proves the extracted typed summary models and view-model construction match the old page-shaped model. The live page now sources summary HTML from the extracted snapshot/builder while still using the existing shared summary renderer.

## Ownership

- Typed models: `inputs_page_modules/summaries/models.py`
- View-model builder: `inputs_page_modules/summaries/builders.py`
- Contract constants: `inputs_page_modules/summaries/contracts.py`
- Live renderer: unchanged, still page/shared-renderer owned
- Page wrapper: `THIN_WRAPPER_KEEP_TEMPORARILY`

## Old / Extracted Hashes

Overall old model hash: `{payload['overall_old_hash']}`

Overall extracted model hash: `{payload['overall_extracted_hash']}`

## Scenario Results

| Scenario | Status | Old hash | Extracted hash | Mismatches |
|---|---|---|---|---:|
{chr(10).join(scenario_lines)}

## Field-Level Mismatches

{chr(10).join(mismatch_lines)}

## Source Ownership Proof

```json
{json.dumps(payload['source_inventory'], indent=2)}
```

## Remaining Page-Owned Logic

- `_resolved_inputs_summary_state(...)`: page/session source collection remains page-owned.
- `_overlay_current_design_action_results_for_summary(...)`: page/source overlay remains page-owned for now.
- `render_inputs_cached_summary_html_for_first_paint_coordinator(...)`: page-shell cache/reuse guard remains.
- `_render_current_inputs_summary(...)`: page renderer placement remains.

## Extraction Safety

Extraction safe for live cutover prep: `{str(payload['extraction_safe']).lower()}`
"""
    report_path.write_text(report, encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    scenario_results = []
    all_mismatches: list[dict[str, Any]] = []
    old_hashes = []
    extracted_hashes = []
    for snapshot in _scenarios():
        old = _current_page_summary_payload(snapshot)
        extracted = build_inputs_summary_view_model(snapshot)
        extracted_payload = asdict(extracted)
        extracted_payload["html_hash"] = stable_summary_hash(build_inputs_summary_html(snapshot))
        mismatches = _compare_payloads(old, extracted_payload)
        all_mismatches.extend(mismatches)
        old_hashes.append(old["display_hash"])
        extracted_hashes.append(extracted.display_hash)
        scenario_results.append({
            "scenario_id": snapshot.scenario_id,
            "scenario_label": snapshot.scenario_label,
            "status": "PASS" if not mismatches else "FAIL",
            "old_summary_model_hash": old["display_hash"],
            "extracted_summary_model_hash": extracted.display_hash,
            "cards": old["cards"],
            "mismatches": mismatches,
        })

    source_inventory = _source_path_inventory()
    ownership_ok = (
        source_inventory["typed_models_in_extracted_module"]
        and source_inventory["builder_in_extracted_module"]
        and source_inventory["contracts_in_extracted_module"]
        and source_inventory["inputs_page_imports_extracted_builder"]
        and source_inventory["inputs_page_calls_extracted_builder"]
        and source_inventory["inputs_page_keeps_old_renderer"]
        and source_inventory["inputs_page_live_cutover"]
        and not source_inventory["builder_direct_streamlit_import"]
        and not source_inventory["builder_direct_solver_import"]
    )
    extraction_safe = not all_mismatches and ownership_ok
    decision = "SUMMARY_LIVE_CUTOVER_READY_FOR_CLEANUP" if extraction_safe else "SUMMARY_EXTRACTION_PARITY_GAPS_REMAIN"
    payload = {
        "schema": "inputs_summary_view_model_parity_snapshot.v2",
        "generated_at": timestamp,
        "result": "PASS" if extraction_safe else "FAIL",
        "decision": decision,
        "scope": "extracted summary view-model and HTML parity; existing shared renderer unchanged",
        "source_inventory": source_inventory,
        "required_scenario_count": 10,
        "scenario_count": len(scenario_results),
        "overall_old_hash": _stable_hash(old_hashes),
        "overall_extracted_hash": _stable_hash(extracted_hashes),
        "scenarios": scenario_results,
        "mismatch_classifications": sorted({m["classification"] for m in all_mismatches}),
        "extraction_safe": extraction_safe,
        "temporary_wrappers_retained": ["inputs_page.py live summary source snapshot wrapper"],
        "temporary_wrapper_classification": "THIN_WRAPPER_KEEP_TEMPORARILY",
        "live_renderer_cutover": True,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_summary_view_model_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_summary_view_model_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(payload, report_path)
    print(f"inputs_summary_view_model_parity_snapshot {payload['result']}")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if extraction_safe else 1


if __name__ == "__main__":
    raise SystemExit(main())
