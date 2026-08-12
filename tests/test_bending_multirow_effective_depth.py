from __future__ import annotations

import pytest

from calculations.bending import compute_bending_capacity_legacy


def test_detailed_bending_uses_the_published_multirow_centroid_depth() -> None:
    result = compute_bending_capacity_legacy(
        b=275.0,
        D=500.0,
        fc=40.0,
        fsy=500.0,
        Ast=904.778684,
        Mu_star=135.0,
        phi=0.85,
        d_input=408.0,
        cover_bot=40.0,
        db_bot=12.0,
        nb_bot=8.0,
        rowgap_bot=60.0,
        lig_diameter_mm=10.0,
    )

    assert result["d"] == pytest.approx(408.0)
    assert result["phi_Mu_cap"] == pytest.approx(146.88, abs=0.05)
