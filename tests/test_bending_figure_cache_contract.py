from types import SimpleNamespace

import engineering_page_sections.bending_diagram_bundle as bundle_renderer
from engineering_page_sections.bending_diagram_bundle_cache import (
    BENDING_DIAGRAM_CACHE_KEY,
    bending_diagram_bundle_fingerprint,
    bending_moment_fingerprint,
    bundle_manifest,
    get_bundle_manifest,
    get_figure_json,
    put_bundle_manifest,
    put_figure_json,
    section_stress_strain_fingerprint,
    side_view_fingerprint,
)


def _bundle_ids(seed: int = 1):
    sections = {
        state: section_stress_strain_fingerprint({"seed": seed, "state": state})
        for state in ("ULS", "SLS (cracked)", "Uncracked")
    }
    sides = {
        state: side_view_fingerprint({"seed": seed, "state": state})
        for state in sections
    }
    moment = bending_moment_fingerprint({"seed": seed})
    bundle = bending_diagram_bundle_fingerprint(
        section_fingerprints=sections,
        side_fingerprints=sides,
        moment_fingerprint=moment,
    )
    return sections, sides, moment, bundle


def test_fingerprints_are_deterministic_and_dependency_sensitive() -> None:
    a = section_stress_strain_fingerprint({"b": 250.0, "D": 300.0})
    b = section_stress_strain_fingerprint({"D": 300.0, "b": 250.0})
    changed = section_stress_strain_fingerprint({"b": 260.0, "D": 300.0})

    assert a == b
    assert changed != a


def test_relevant_engineering_changes_invalidate_presentation_fingerprints() -> None:
    section = {
        "geometry": {"b": 250.0, "D": 300.0},
        "reinforcement": {"bottom": [(3, 10.0)], "top": [(2, 10.0)]},
        "material": {"fc": 40.0, "fsy": 500.0},
        "moment_sign": "positive",
    }
    baseline_section = section_stress_strain_fingerprint(section)
    for changed in (
        {**section, "geometry": {"b": 300.0, "D": 300.0}},
        {**section, "geometry": {"b": 250.0, "D": 350.0}},
        {
            **section,
            "reinforcement": {"bottom": [(4, 10.0)], "top": [(2, 10.0)]},
        },
        {**section, "material": {"fc": 50.0, "fsy": 500.0}},
        {**section, "material": {"fc": 40.0, "fsy": 600.0}},
        {**section, "moment_sign": "negative"},
    ):
        assert section_stress_strain_fingerprint(changed) != baseline_section

    moment = {
        "L": 3.0,
        "support_type": "simply_supported",
        "x_plot": [0.0, 1.5, 3.0],
        "M_plot": [0.0, 200.0, 0.0],
    }
    baseline_moment = bending_moment_fingerprint(moment)
    assert bending_moment_fingerprint({**moment, "L": 4.0}) != baseline_moment
    assert (
        bending_moment_fingerprint({**moment, "support_type": "cantilever"})
        != baseline_moment
    )
    assert (
        bending_moment_fingerprint({**moment, "M_plot": [0.0, 250.0, 0.0]})
        != baseline_moment
    )


def test_bundle_cache_round_trip_is_presentation_only() -> None:
    state = {}
    sections, sides, moment, bundle = _bundle_ids()
    for fingerprint in sections.values():
        put_figure_json(
            state,
            kind="section",
            fingerprint=fingerprint,
            figure_json='{"data":[],"layout":{}}',
        )
    for fingerprint in sides.values():
        put_figure_json(
            state,
            kind="side",
            fingerprint=fingerprint,
            figure_json='{"data":[],"layout":{}}',
        )
    put_figure_json(
        state,
        kind="moment",
        fingerprint=moment,
        figure_json='{"data":[],"layout":{}}',
    )
    manifest = bundle_manifest(
        section_fingerprints=sections,
        side_fingerprints=sides,
        moment_fingerprint=moment,
    )
    put_bundle_manifest(state, fingerprint=bundle, manifest=manifest)

    assert get_bundle_manifest(state, fingerprint=bundle) == manifest
    assert get_figure_json(
        state, kind="moment", fingerprint=moment
    ) == '{"data":[],"layout":{}}'
    assert "engineering" not in state[BENDING_DIAGRAM_CACHE_KEY]


def test_bundle_manifest_invalidates_when_a_component_is_missing() -> None:
    state = {}
    sections, sides, moment, bundle = _bundle_ids()
    manifest = bundle_manifest(
        section_fingerprints=sections,
        side_fingerprints=sides,
        moment_fingerprint=moment,
    )
    put_bundle_manifest(state, fingerprint=bundle, manifest=manifest)

    assert get_bundle_manifest(state, fingerprint=bundle) is None


def test_component_and_bundle_caches_are_bounded() -> None:
    state = {}
    for index in range(14):
        fingerprint = section_stress_strain_fingerprint({"index": index})
        put_figure_json(
            state,
            kind="section",
            fingerprint=fingerprint,
            figure_json=f'{{"index":{index}}}',
        )

    section_bucket = state[BENDING_DIAGRAM_CACHE_KEY]["components"]["section"]
    assert len(section_bucket["entries"]) == 9
    assert len(section_bucket["order"]) == 9


def test_bundle_fingerprint_changes_for_each_relevant_component() -> None:
    sections, sides, moment, bundle = _bundle_ids(1)
    changed_sections, _, _, changed_section_bundle = _bundle_ids(2)
    changed_side = dict(sides)
    changed_side["ULS"] = side_view_fingerprint({"seed": "changed"})
    changed_side_bundle = bending_diagram_bundle_fingerprint(
        section_fingerprints=sections,
        side_fingerprints=changed_side,
        moment_fingerprint=moment,
    )
    changed_moment_bundle = bending_diagram_bundle_fingerprint(
        section_fingerprints=sections,
        side_fingerprints=sides,
        moment_fingerprint=bending_moment_fingerprint({"seed": "changed"}),
    )

    assert changed_sections != sections
    assert changed_section_bundle != bundle
    assert changed_side_bundle != bundle
    assert changed_moment_bundle != bundle


def test_side_view_identity_ignores_unrelated_results_publication(
    monkeypatch,
) -> None:
    session = {
        "results": {"shear_page_only": 1},
        "actions_mode": "manual",
        "bending_detail_view": "positive",
    }
    parameters = {
        "moment_x": [0.0, 3.0],
        "shear_M_uls_kNm": [0.0, 200.0],
        "delta_total": 2.5,
    }
    monkeypatch.setattr(
        bundle_renderer,
        "st",
        SimpleNamespace(session_state=session),
        raising=False,
    )
    monkeypatch.setattr(
        bundle_renderer,
        "get_param",
        lambda name, default=None: parameters.get(name, default),
        raising=False,
    )

    import shear_visuals
    from ui.diagrams import crack_side_view_diagram

    monkeypatch.setattr(
        shear_visuals,
        "_beam_model",
        lambda: {"span_m": 3.0, "support_condition": "simply_supported"},
    )
    monkeypatch.setattr(
        crack_side_view_diagram,
        "_resolve_crack_diagram_window",
        lambda state: {"multi": False, "x0_m": 0.0, "L_m": 3.0},
    )
    monkeypatch.setattr(
        crack_side_view_diagram,
        "_support_resolution",
        lambda state: {"support_type": "Simply supported"},
    )
    monkeypatch.setattr(
        crack_side_view_diagram,
        "_total_structural_length_m",
        lambda: 3.0,
    )

    before = bundle_renderer._side_view_identity_payload(
        section_fingerprint="section-a",
        state_option="ULS",
        projected_state={"dn": 26.6},
    )
    session["results"] = {
        "shear_page_only": 999,
        "unrelated_deflection_page_value": "changed",
    }
    after = bundle_renderer._side_view_identity_payload(
        section_fingerprint="section-a",
        state_option="ULS",
        projected_state={"dn": 26.6},
    )

    assert before == after
    assert "publication" not in before


def test_side_view_identity_tracks_relevant_authoritative_inputs(
    monkeypatch,
) -> None:
    session = {
        "actions_mode": "manual",
        "bending_detail_view": "positive",
    }
    parameters = {
        "moment_x": [0.0, 3.0],
        "shear_M_uls_kNm": [0.0, 200.0],
        "delta_total": 2.5,
    }
    model = {"span_m": 3.0, "support_condition": "simply_supported"}
    monkeypatch.setattr(
        bundle_renderer,
        "st",
        SimpleNamespace(session_state=session),
        raising=False,
    )
    monkeypatch.setattr(
        bundle_renderer,
        "get_param",
        lambda name, default=None: parameters.get(name, default),
        raising=False,
    )

    import shear_visuals
    from ui.diagrams import crack_side_view_diagram

    monkeypatch.setattr(shear_visuals, "_beam_model", lambda: dict(model))
    monkeypatch.setattr(
        crack_side_view_diagram,
        "_resolve_crack_diagram_window",
        lambda state: {"multi": False, "x0_m": 0.0, "L_m": model["span_m"]},
    )
    monkeypatch.setattr(
        crack_side_view_diagram,
        "_support_resolution",
        lambda state: {"support_type": model["support_condition"]},
    )
    monkeypatch.setattr(
        crack_side_view_diagram,
        "_total_structural_length_m",
        lambda: model["span_m"],
    )

    def fingerprint() -> str:
        return side_view_fingerprint(
            bundle_renderer._side_view_identity_payload(
                section_fingerprint="section-a",
                state_option="ULS",
                projected_state={"dn": 26.6},
            )
        )

    baseline = fingerprint()
    parameters["shear_M_uls_kNm"] = [0.0, -200.0]
    changed_action = fingerprint()
    model["support_condition"] = "cantilever"
    changed_support = fingerprint()
    model["span_m"] = 4.0
    changed_length = fingerprint()

    assert changed_action != baseline
    assert changed_support != changed_action
    assert changed_length != changed_support
