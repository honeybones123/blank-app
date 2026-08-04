"""Pure projection of engineering calculation steps into report tab boxes."""

from __future__ import annotations


def steps_to_tabs_boxes(
    module_title: str,
    steps: list,
    default_tab: str,
) -> dict:
    boxes = []
    for index, raw_step in enumerate(steps, start=1):
        step = dict(raw_step or {})
        derivation = []
        formula = step.get("formula") or step.get("formula_lines") or []
        substitution = step.get("substitution") or step.get("sub_lines") or []
        if isinstance(formula, str):
            formula = [formula]
        if isinstance(substitution, str):
            substitution = [substitution]

        if formula:
            derivation.append({"label": "Formula", "eq": "", "sub": ""})
            for line in formula:
                derivation.append({"label": "", "eq": line, "sub": ""})

        if substitution:
            derivation.append(
                {"label": "Substitution", "eq": "", "sub": ""}
            )
            for line in substitution:
                derivation.append({"label": "", "eq": line, "sub": ""})

        for line in step.get("equations", []) or []:
            derivation.append({"label": "", "eq": line, "sub": ""})

        boxes.append(
            {
                "id": f"1.{index}",
                "title": step.get("title", f"Check {index}"),
                "clause": step.get("clause", ""),
                "status": step.get("status"),
                "status_text": step.get("status_text", ""),
                "result": step.get("result", ""),
                "derivation": derivation,
                "diagram": step.get("diagram"),
            }
        )

    return {
        "module_title": module_title,
        "title": module_title,
        "tabs": [{"tab_title": default_tab, "boxes": boxes}],
    }


__all__ = ["steps_to_tabs_boxes"]
