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
    assert "decorateReportTables" in source


def test_dashboard_keeps_report_summaries_as_original_markdown_content():
    """The dashboard must not replace report summaries with synthetic controls."""
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "展开摘要" not in source
    assert "收起摘要" not in source
    assert "summary-cell-content" not in source
    assert "summary-toggle" not in source
    assert "headerIsSummary" not in source
    assert "summaryHasHiddenContent" not in source


def test_dashboard_search_normalizes_spacing_and_returns_specific_items():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "function normalizeSearchText" in source
    assert "normalizeSearchText(query)" in source
    assert 'digests/search-index.json' in source
    assert 'id="searchResults"' in source
    assert "item.occurrence_id" in source
    assert "openItemDetail(item)" in source
    assert "grp.hidden = !matched" not in source


def test_dashboard_accepts_the_product_owned_atr_v1_search_index():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "artifact.schema_version !== 2" in source
    assert "artifact.id_scheme !== 'atr-v1'" in source
    assert "artifact.id_scheme !== 'sd-v1'" not in source


def test_dashboard_initializes_filter_options_before_the_user_types():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "void initSearch();" in source


def test_dashboard_does_not_reuse_a_stale_versioned_search_index():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "fetch('./digests/search-index.json', { cache: 'no-store' })" in source


def test_dashboard_filters_can_browse_without_a_keyword():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "applyItemSearch(searchQuery, true)" in source
    assert "filterBrowse" in source


def test_dashboard_time_filter_uses_the_actual_latest_document_date():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "document.date > latest ? document.date : latest" in source


def test_dashboard_item_routes_restore_specific_details_without_guessing_report_anchors():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "marker === 'item'" in source
    assert "async function applyRoute" in source
    assert "searchDocumentsById.get(route.occurrenceId)" in source
    assert "item.report_target" in source
    assert "生产端尚未提供对应锚点" in source
