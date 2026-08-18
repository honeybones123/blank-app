from pathlib import Path


def test_deflection_renderer_reuses_authoritative_publication_when_present():
    source = Path('deflection_page_runtime.py').read_text(encoding='utf-8')
    start = source.index('    from deflection_core import compute_deflection_results')
    end = source.index('    render_timing_mark("deflection_page.runtime.compute.publication.end")', start)
    block = source[start:end]

    assert 'if not _deflection_params_present or not _deflection_report_present:' in block
    assert block.count('compute_deflection_results(publish=True)') == 1
    assert 'st.session_state["_deflection_core_cache_key"] = _deflection_cache_key' in block
    assert 'st.session_state.get("_deflection_core_cache_key") != _deflection_cache_key' not in block


def test_deflection_authoritative_result_boundary_remains_documented():
    source = Path('deflection_page_runtime.py').read_text(encoding='utf-8')
    assert 'application result-page boundary refreshes Deflection authoritatively' in source
