import copy

from batch_design.importers.project_import import import_beams_from_project


def _payload():
    return {
        "beam_order": ["beam_1"],
        "beam_records": {
            "beam_1": {
                "beam_label": "Ground Beam",
                "params": {"sec_shape": "RECT", "b": 300, "D": 600, "L": 7.5, "Mu_star": 120, "Vu_star": 55},
                "summary": {"overall_status": "PASS", "phi_Mu_cap": 180, "phi_Vu_cap": 90, "Mu_utilisation": 0.67},
            }
        },
    }


def test_project_import_as_rows_does_not_mutate_source_project():
    payload = _payload()
    before = copy.deepcopy(payload)

    imported = import_beams_from_project(payload)

    assert payload == before
    assert imported.metadata["mutated_source"] is False
    assert imported.rows[0].member_id == "beam_1"
    assert imported.rows[0].mz_star == 120.0


def test_project_import_as_templates_uses_cached_passing_summary():
    templates = import_beams_from_project(_payload(), as_templates=True)

    assert templates[0].template_id == "beam_1"
    assert templates[0].passing is True
    assert templates[0].capacities["mz_star"] == 180.0
