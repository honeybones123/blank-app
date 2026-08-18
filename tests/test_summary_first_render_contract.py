from pathlib import Path


def test_bending_summary_renders_before_explainer_and_heavy_content():
    text = Path('bending_page_runtime.py').read_text(encoding='utf-8')
    summary = text.index('clicked_uid = render_clickable_summary_table(')
    summary_mark = text.index('bending_page.runtime.summary_table.rendered')
    explainer = text.index('render_page_explainer_expander(_render_bending_explainer)')
    inputs = text.index('with inputs_placeholder.container():')
    diagram = text.index('bending_page.runtime.diagram.figure.start')
    checks = text.index('bending_page.runtime.checks.start')

    assert summary < summary_mark < explainer
    assert summary < inputs
    assert summary < diagram
    assert summary < checks
