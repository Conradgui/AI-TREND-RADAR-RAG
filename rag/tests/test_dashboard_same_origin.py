"""Regression tests for dashboard API routing in local deployments."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = PROJECT_ROOT / "index.html"


def test_dashboard_uses_current_origin_for_local_rag_api_calls():
    """A page opened at 127.0.0.1 must not fetch APIs from localhost."""
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "const LOCAL_API_BASE = window.location.origin;" in source
    assert "http://localhost:8001/" not in source


def test_citation_navigation_uses_evidence_type_instead_of_date_heuristics():
    """A dated web result must never be mistaken for a local daily report."""
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "const isInternal = c.evidence_type !== 'external';" in source
    assert "const hasLocalReport = isInternal && Boolean(c.date);" in source
    assert "const hasLocalReport = Boolean(c.date);" not in source


def test_agent_is_primary_navigation_and_briefs_is_not_a_top_level_entry():
    """The primary user action is Agent; internal Briefs support remains hidden."""
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="chatBtn" class="hdr-btn primary-action"' in source
    assert 'id="briefsBtn"' not in source
    assert 'id="briefsPanel"' in source
    assert "document.getElementById('briefsBtn')?.classList.toggle" in source


def test_dashboard_explains_corpus_freshness_without_hiding_sync_failure():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="systemCorpusSync"' in source
    assert 'id="systemCorpusSyncTime"' in source
    assert "更新失败（使用旧数据）" in source
    assert "正在建立本地索引" in source
    assert "上游同步失败（本地语料可用）" in source


def test_dashboard_revalidates_dynamic_corpus_files_instead_of_using_stale_cache():
    """A long-running local dashboard must see newly synchronized dates and revisions."""
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "fetch('./manifest.json', { cache: 'no-store' })" in source
    assert "fetch(`./digests/${date}/${report}.md`, { cache: 'no-cache' })" in source


def test_dashboard_uses_real_chat_progress_stream_with_safe_fallback():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "getLocalApiUrl('/chat/stream')" in source
    assert "res.body.getReader()" in source
    assert "case 'evidence_ready':" in source
    assert "case 'web_searching':" in source
    assert "case 'web_results_ready':" in source
    assert "case 'deep_fetching':" in source
    assert "case 'web_degraded':" in source
    assert "case 'answer_chunk':" in source
    assert "canFallbackToChat" in source
    assert "fetch(CHAT_API_URL" in source


def test_dashboard_distinguishes_static_mode_from_a_recoverable_agent_connection_failure():
    """The browser can retry a service, but never starts Docker itself."""
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "function appendAgentConnectionRecovery" in source
    assert "agent-retry-service" in source
    assert "function retryAgentServiceConnection" in source
    assert "function openLocalRagService" in source
    assert "http://127.0.0.1:8001/" in source


def test_system_panel_can_attach_a_static_report_view_to_an_already_running_rag_service():
    """Connecting means navigation to the same-origin service, not restarting Docker."""
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="systemConnectionAction"' in source
    assert "function connectToLocalRag" in source
    assert "target.hash = window.location.hash;" in source
    assert "function configureSystemConnectionAction" in source
    assert "连接运行中的 RAG" in source
    assert "重新检测服务" in source


def test_dashboard_does_not_fake_agent_progress_with_fixed_timers():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "setTimeout(() => updateTypingProgress" not in source
    assert "本次如何完成" in source
    assert "推理过程" not in source


def test_dashboard_can_cancel_an_in_flight_stream_without_resending():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "new AbortController()" in source
    assert "requestStreamingChat(requestPayload, typingElement, activeChatController.signal)" in source
    assert "activeChatController.abort()" in source
    assert "已停止本次回答" in source


def test_agent_composer_exposes_request_scoped_web_search_control():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="chatWebSearchToggle"' in source
    assert 'aria-pressed="false"' in source
    assert 'id="chatWebSearchStatus"' in source
    assert "web_search_mode: chatWebSearchMode" in source
    assert "refreshChatWebSearchCapability()" in source


def test_system_panel_explains_web_capability_is_not_forced_search():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="systemWebSearchHint"' in source
    assert "允许 Agent 按需搜索，不代表每次回答都会联网" in source
    assert "web_search_capability" in source


def test_stream_and_legacy_share_one_immutable_chat_payload():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "const requestPayload = Object.freeze" in source
    assert "requestStreamingChat(requestPayload" in source
    assert "requestLegacyChat(requestPayload" in source
    assert "JSON.stringify(payload)" in source


def test_dashboard_consumes_display_answer_and_source_groups():
    source = DASHBOARD.read_text(encoding="utf-8")

    assert "case 'source_groups':" in source
    assert "data.display_answer || data.answer" in source
    assert "bindEvidenceMarkers" in source
