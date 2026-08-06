"""Public dashboard contracts for readable reports and forgiving navigation."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = PROJECT_ROOT / "index.html"


def test_dashboard_exposes_desktop_sidebar_resize_and_collapse_controls():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="sidebarCollapse"' in source
    assert 'id="sidebarResizeHandle"' in source
    assert "ar-sidebar-width" in source
    assert "initSidebarResize" in source


def test_dashboard_keeps_long_report_tables_scannable():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="readingDensity"' in source
    assert "table-scroll" in source
    assert "data-summary-cell" in source
    assert "decorateReportTables" in source
    assert "摘要" in source


def test_dashboard_search_normalizes_spacing_and_filters_to_matching_reports():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "function normalizeSearchText" in source
    assert "normalizeSearchText(query)" in source
    assert "grp.hidden = !matched" in source
    assert "month.hidden" in source
