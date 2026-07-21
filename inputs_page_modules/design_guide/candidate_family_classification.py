"""Design Guide candidate-family domain classification."""

from __future__ import annotations


def _candidate_family_matches_governing_domain(family_name: str, governing_domain: str) -> bool:
    """
    Domain-aware classification for one-click tightening pools.

    Notes:
    - Shear "cleanup / layout tidy" families are intentionally NOT treated as shear-primary levers,
      so shear-governing pruning can deprioritize them via the same domain matcher as other
      non-primary families (instead of relying on scattered name tuples in the solver loop).
    - Shear-governing geometry escalation is shear-relevant (depth/width/combined), not bending-first.
    """
    fam = str(family_name or "").strip()
    if not fam:
        return False
    low = fam.lower()
    if governing_domain == "bending":
        return bool(
            low.startswith("bending_strength")
            or low.startswith("bottom_reduction")
            or low.startswith("geometry_reduction")
            or low
            in {
                "bottom_reo",
                "geometry",
                "bending",
                "compound_geometry_bottom",
            }
        )
    if governing_domain == "shear":
        shear_primary_families = {
            "spacing_reduction",
            "more_legs",
            "larger_dia",
            "combined_link_changes",
            "combined_geometry_links",
            "depth_increase",
            "width_increase",
            "shear_cleanup",
        }
        if low in shear_primary_families:
            return True

        # Shear cleanup / non-primary helpers: keep these OUT of shear-primary classification.
        if low in ("shear_spacing_layout_cleanup",):
            return False
        if "cleanup" in low or low.endswith("_cleanup") or low.endswith("cleanup"):
            return False

        # Broaden shear_* variants without treating every arbitrary "shear" substring as primary.
        if low.startswith("shear_"):
            if low in ("shear_adjust",):
                return False
            shearish_tokens = (
                "spacing",
                "leg",
                "legs",
                "dia",
                "lig",
                "link",
                "links",
                "combined",
                "geometry",
                "depth",
                "width",
                "stirrup",
                "ties",
            )
            tail = low[len("shear_") :]
            if any(tok in tail for tok in shearish_tokens):
                return True

        return False
    return False


__all__ = ["_candidate_family_matches_governing_domain"]
