"""Application-owned Design Guide card copy model."""

from __future__ import annotations

from typing import Callable

from inputs_application.engineering_predicates import parse_util_value


def _format_guidance_title(title: str, util: float | None) -> str:
    if util is None:
        return title
    return f"{title} (utilisation = {util:.2f})"


def _design_guide_efficiency_copy() -> dict:
    return {
        "title_main": "Design is efficient - further reductions would weaken capacity",
        "primary_action": "The current section is within the target utilisation range.",
        "secondary_action": "The current design is the best practical balance found, not just safe enough.",
        "guidance_why": "\n".join(
            [
                "The current section is within the target utilisation range.",
                "The solver did not find a smaller practical option that stayed inside the target range.",
                "Further reductions would reduce:",
                "- bending capacity by lowering the lever arm and/or Ast",
                "- shear capacity by reducing effective shear depth and link contribution",
                "- stiffness, which can increase deflection and cracking risk",
                "So the current design is the best practical balance found, not just safe enough.",
            ]
        ),
    }


def _design_guide_bending_low_capacity_copy() -> dict:
    return {
        "title_main": "Bending capacity is low",
        "primary_action": "Recommended action: increase bottom reinforcement or section depth.",
        "secondary_action": (
            "The solver will prefer the smallest practical change that restores capacity "
            "without making shear or serviceability worse."
        ),
        "guidance_why": "\n".join(
            [
                "The applied moment is too close to or above the available moment capacity.",
                "Why this helps:",
                "- More Ast increases tensile force capacity.",
                "- More depth increases the lever arm between compression and tension.",
                "- Together, these increase phiMu more efficiently than only oversizing one input.",
                "Trade-off: extra steel can add congestion, while extra depth increases section size and stiffness.",
            ]
        ),
    }


def _design_guide_shear_low_capacity_copy() -> dict:
    return {
        "title_main": "Shear capacity is low",
        "primary_action": "Recommended action: tighten link spacing, increase link legs, or increase effective depth.",
        "secondary_action": "The solver will first try practical reinforcement changes before increasing the whole section.",
        "guidance_why": "\n".join(
            [
                "The applied shear demand is above the available shear capacity.",
                "Why this helps:",
                "- Closer spacing increases stirrup contribution per metre.",
                "- More legs increases shear steel area.",
                "- Greater effective depth improves the concrete and truss action contribution.",
                "Trade-off: heavier or closer links can increase congestion; geometry is used when reinforcement alone is not enough.",
            ]
        ),
    }


def _design_guide_optional_shear_cleanup_copy(
    *,
    actionable: bool = False,
) -> dict:
    secondary = (
        "This is an optional cleanup rather than a required capacity fix; apply it only if the "
        "buildability/congestion benefit is worth the reduced shear reserve."
        if actionable
        else (
            "Because this is a non-governing cleanup rather than a required design improvement, "
            "it is shown as advisory rather than a one-click action."
        )
    )
    return {
        "title_main": "Optional refinement - shear reinforcement is conservative",
        "primary_action": "Shear capacity is well above demand, so the current links are not governing the design.",
        "secondary_action": secondary,
        "guidance_why": "\n".join(
            [
                "Shear capacity is well above demand, so the current links are not governing the design.",
                "Reducing links may improve buildability and reduce congestion, but it also lowers shear reserve capacity.",
                secondary,
            ]
        ),
    }


def _design_guide_copy_for_intent(
    intent: str,
    item: dict,
    *,
    fail_keys: set[str],
    actionable: bool,
) -> dict | None:
    check_key = str((item or {}).get("check_key") or "").strip().lower()
    title = str(
        (item or {}).get("title_main")
        or (item or {}).get("title")
        or ""
    ).strip().lower()
    if intent == "required_fix":
        bending_low = check_key == "bending" or fail_keys == {"bending"}
        shear_low = check_key == "shear" or fail_keys == {"shear"}
        if bending_low and "ductility" not in title:
            return _design_guide_bending_low_capacity_copy()
        if shear_low:
            return _design_guide_shear_low_capacity_copy()
        return None
    if intent == "optional_cleanup":
        return _design_guide_optional_shear_cleanup_copy(actionable=actionable)
    if intent == "already_efficient":
        return _design_guide_efficiency_copy()
    return None


def apply_guidance_copy_model_to_item(
    item: dict,
    *,
    state: dict,
    overview: dict | None,
    efficiency_state: dict | None,
    derive_guidance_intent: Callable[..., str],
) -> dict:
    if not isinstance(item, dict):
        return item
    out = dict(item)
    resolved_overview = overview if isinstance(overview, dict) else {}
    resolved_efficiency = (
        efficiency_state if isinstance(efficiency_state, dict) else {}
    )
    util = parse_util_value(out.get("util"))
    has_action = bool(str(out.get("action_type") or "").strip())
    statuses = dict(resolved_overview.get("statuses") or {})
    fail_keys = {
        str(key).strip().lower()
        for key, value in statuses.items()
        if str(value or "").strip().upper() == "FAIL"
    }
    intent = derive_guidance_intent(
        out,
        state=state,
        overview=resolved_overview,
        efficiency_state=resolved_efficiency,
    )
    out["guidance_intent"] = intent
    copy_model = _design_guide_copy_for_intent(
        intent,
        out,
        fail_keys=fail_keys,
        actionable=has_action,
    )
    if not copy_model:
        return out

    new_title = str(
        copy_model.get("title_main") or out.get("title_main") or ""
    ).strip()
    if new_title:
        out["title_main"] = new_title
        out["title"] = _format_guidance_title(new_title, util)
    if "primary_action" in copy_model:
        out["primary_action"] = str(copy_model.get("primary_action") or "")
    if "secondary_action" in copy_model:
        out["secondary_action"] = str(copy_model.get("secondary_action") or "")
    why_text = str(copy_model.get("guidance_why") or "").strip()
    if why_text:
        out["guidance_why"] = why_text
        out["guidance_why_text_compact"] = why_text
    return out


__all__ = ["apply_guidance_copy_model_to_item"]
