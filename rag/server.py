"""FastAPI server — serves Dashboard UI and provides /chat, /config, /health endpoints."""

from __future__ import annotations

import asyncio
import dataclasses
import fcntl
import hmac
import json
import logging
import os
import tempfile
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag.config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    CHROMA_DIR,
    INDEX_GENERATIONS_DIR,
    RAG_HOST,
    RAG_PORT,
    is_configured,
    LLM_PROVIDER,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    get_configured_search_providers,
    get_search_provider_api_keys,
    is_deep_fetch_enabled,
    is_startup_corpus_update_enabled,
)
from rag.graphrag.driver import Neo4jDriver
from rag.graphrag.schema import init_schema
from rag.retriever.vector_store import VectorStore
from rag.retriever.lexical_store import LexicalStore
from rag.retriever.hybrid import HybridRetriever
from rag.retriever.vector_only import VectorOnlyRetriever
from rag.retrieval_gateway import EvidenceRetrievalGateway
from rag.ordered_frame_client_v3 import (
    DeepSeekOrderedFrameModelV3,
    OrderedFrameClientV3,
    understand_ordered_query_v3,
)
from rag.agent.agent import create_agent
from rag.agent.llm import create_direct_llm_agent
from rag.chat_service import build_chat_response
from rag.chat_stream import encode_stream_event, iter_chat_events
from rag.corpus_update import load_update_state, summarize_update_state
from rag.runtime_tools import select_external_deep_fetcher
from rag.runtime_settings import load_runtime_settings, save_runtime_setting
from rag.search_provider_adapters import SearchProviderRegistry
from rag.index_coordinator import IndexBuildCoordinator, VectorBuildResult
from rag.index_generation import IndexGenerationStore
from rag.runtime_leases import RuntimeLeaseRegistry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 版本号统一为常量
APP_VERSION = "0.2.0"

# ── C-6 修复：速率限制配置 ───────────────────────────────────────────────────
# 滑动窗口速率限制器 — 按客户端 IP 限制 /chat 端点请求频率
RATE_LIMIT_MAX_REQUESTS = 10      # 窗口内最大请求数
RATE_LIMIT_WINDOW_SECONDS = 60    # 滑动窗口时长（秒）
# Must remain above the longest Agent path so the UI receives the more useful
# Agent-level timeout diagnosis instead of a generic HTTP 504.
CHAT_REQUEST_TIMEOUT_SECONDS = 195
RAG_CONFIG_LOCK = asyncio.Lock()
CORPUS_UPDATE_LOCK = asyncio.Lock()
INDEX_MAINTENANCE_LOCK = asyncio.Lock()


class RateLimitMiddleware:
    """滑动窗口速率限制中间件 — 对聊天 POST 端点生效。

    使用 defaultdict(list) 按客户端 IP 记录请求时间戳，
    每次请求清理窗口外的旧记录，超限返回 429 Too Many Requests。
    """

    def __init__(self, app, max_requests: int = RATE_LIMIT_MAX_REQUESTS,
                 window_seconds: int = RATE_LIMIT_WINDOW_SECONDS):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # {client_ip: [timestamp, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, scope, receive, send):
        # 流式与非流式聊天共享同一成本边界，避免通过换端点绕过限流。
        is_chat_request = (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") in {"/chat", "/chat/stream"}
        )
        if is_chat_request:
            client_ip = self._get_client_ip(scope)
            now = time.time()

            # 清理窗口外的旧记录
            window_start = now - self.window_seconds
            self._requests[client_ip] = [
                ts for ts in self._requests[client_ip] if ts > window_start
            ]

            if len(self._requests[client_ip]) >= self.max_requests:
                # 超限 — 返回 429
                from starlette.responses import JSONResponse
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please wait before retrying."},
                )
                await response(scope, receive, send)
                return

            self._requests[client_ip].append(now)

        await self.app(scope, receive, send)

    @staticmethod
    def _get_client_ip(scope) -> str:
        """从 ASGI scope 提取客户端 IP，支持反向代理 X-Forwarded-For。"""
        # 优先从 headers 中取 X-Forwarded-For
        headers = dict(scope.get("headers", []))
        forwarded_for = headers.get(b"x-forwarded-for")
        if forwarded_for:
            return forwarded_for.decode().split(",")[0].strip()
        # 回退到直接连接地址
        client = scope.get("client")
        return client[0] if client else "unknown"

# ── C-2 修复：使用 hmac.compare_digest 做恒定时间比较，防止时序攻击 ─────────
# 移除硬编码默认值：未配置 RAG_API_KEY 时启动失败，避免生产环境用弱密钥
API_KEY = os.getenv("RAG_API_KEY")
if not API_KEY:
    logger.warning(
        "RAG_API_KEY is not set — API key authentication is disabled. "
        "Set RAG_API_KEY environment variable to enable auth."
    )


def verify_api_key(x_api_key: str = Header(None)) -> str:
    """验证API Key — 使用恒定时间比较防止时序攻击"""
    if not API_KEY:
        # 未配置 API Key 时放行（开发模式）
        return x_api_key or "no-auth"
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    # hmac.compare_digest 对两个字符串做逐字节比较，不会提前退出，
    # 因此攻击者无法通过测量响应时间猜出正确字符
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


def _mask_secret(value: str) -> str:
    """将敏感字符串掩码为前4位 + ****（用于日志和响应，不暴露完整密钥）"""
    if not value or len(value) <= 4:
        return "****"
    return value[:4] + "****"


# ── C-1 修复：用不可变 dataclass 封装运行时状态，替换全局可变变量 ─────────────
@dataclass(frozen=True)
class RagState:
    """不可变运行时状态快照 — 并发读写安全。

    所有字段在 lifespan 中初始化一次，配置端点通过
    dataclasses.replace() 创建新实例并原子替换 app.state.rag。
    读请求拿到的是不可变快照，不会因并发写端点而看到半更新状态。
    """
    vector_store: VectorStore
    neo4j_driver: Neo4jDriver | None
    chat_retriever: object | None
    agent: object | None
    answer_composer: object | None
    external_search_registry: SearchProviderRegistry | None
    external_deep_fetcher: object | None
    lexical_store: LexicalStore | None = None
    retrieval_gateway: EvidenceRetrievalGateway | None = None
    query_contract_resolver: object | None = None
    generation_id: str = "legacy"
    latest_corpus_date: str | None = None
    retriever_mode: str = "vector-only"
    index_status: str = "ready"


def _build_retrieval_runtime(
    vector_store: VectorStore,
    neo4j_driver: Neo4jDriver | None,
    answer_composer: object | None,
    mode: str,
    lexical_store: LexicalStore | None = None,
) -> tuple[object, object | None]:
    """Build a retriever and the Agent that closes over that exact retriever."""
    if mode == "hybrid":
        if neo4j_driver is None:
            raise ValueError("Hybrid retrieval requires an available Neo4j driver")
        retriever = HybridRetriever(vector_store, neo4j_driver, lexical_store=lexical_store)
        return retriever, create_agent(neo4j_driver, retriever)
    if mode == "vector-only":
        return VectorOnlyRetriever(vector_store, lexical_store=lexical_store), answer_composer
    raise ValueError(f"Unsupported retriever mode: {mode}")


def _build_retrieval_gateway(retriever: object | None, lexical_store: LexicalStore | None) -> EvidenceRetrievalGateway | None:
    """Bind the Gateway to the same immutable retriever snapshot as the Agent."""
    if retriever is None:
        return None
    graph_driver = getattr(retriever, "neo4j", None)
    return EvidenceRetrievalGateway(
        retriever,
        structured_store=lexical_store,
        graph_driver=graph_driver,
    )


def _build_query_contract_resolver():
    """Build one request-safe v3.5 resolver for the configured DeepSeek runtime."""
    if LLM_PROVIDER != "deepseek" or not DEEPSEEK_API_KEY:
        return None
    extractor = OrderedFrameClientV3(
        DeepSeekOrderedFrameModelV3(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            model=DEEPSEEK_MODEL,
        )
    )

    async def resolve(message: str, context: dict) -> tuple[dict, dict]:
        public_context = json.dumps(context or {}, ensure_ascii=False, sort_keys=True)
        return await asyncio.to_thread(
            understand_ordered_query_v3,
            message,
            extractor,
            public_context,
        )

    return resolve


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    history: list[dict] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)  # 报告上下文：report, date, topic
    web_search_mode: Literal["auto", "always", "never"] = "auto"


class ChatResponse(BaseModel):
    status: str = "ready"
    error_code: str = ""
    answer: str
    display_answer: str = ""
    citations: list[dict] = Field(default_factory=list)
    evidence_display_map: dict[str, str] = Field(default_factory=dict)
    search_references: list[dict] = Field(default_factory=list)
    source_summary: dict = Field(default_factory=dict)
    claim_evidence: list[dict] = Field(default_factory=list)
    claim_verification: dict | None = None
    evidence_integrity: dict = Field(default_factory=dict)
    query_understanding: dict = Field(default_factory=dict)
    tool_trace: dict = Field(default_factory=dict)  # 工具跟踪信息


class ConfigRequest(BaseModel):
    provider: str
    api_key: str
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_password: str = "password"


class CorpusUpdateRequest(BaseModel):
    base_url: str | None = None
    days: int = Field(default=30, ge=1, le=3660)
    dry_run: bool = False


async def _get_rag_state() -> RagState:
    """FastAPI 依赖注入：从 app.state 读取当前 RagState 快照。

    并发安全：frozen dataclass 的读取是线程安全的；
    lifespan 和写端点通过原子替换 app.state.rag 更新快照。
    """
    rag: RagState | None = getattr(app.state, "rag", None)
    if rag is None:
        raise HTTPException(
            status_code=503,
            detail="Server is starting or shutting down. Please retry.",
        )
    return rag


def _runtime_leases() -> RuntimeLeaseRegistry:
    leases = getattr(app.state, "runtime_leases", None)
    if leases is None:
        leases = RuntimeLeaseRegistry()
        app.state.runtime_leases = leases
    return leases


def _corpus_revision() -> str:
    try:
        contract = json.loads((PROJECT_ROOT / "corpus-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unversioned"
    return str(contract.get("corpus_revision") or "unversioned")


def _latest_generation_date(generation_path: Path | None) -> str | None:
    """Return the date owned by the active index generation, not a stale UI manifest."""
    if generation_path is None:
        return None
    try:
        payload = json.loads(
            (generation_path / IndexGenerationStore.MANIFEST_NAME).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    dates = payload.get("dates")
    if not isinstance(dates, list):
        return None
    valid_dates = sorted(
        (value for value in dates if isinstance(value, str) and value),
        reverse=True,
    )
    return valid_dates[0] if valid_dates else None


async def _rebuild_runtime_index_unlocked(dates: list[str] | None = None) -> tuple[int, dict]:
    """Build a full vector staging generation, drain old readers, then update graph."""
    from rag.consistency import post_ingestion_verify
    from rag.ingest import (
        ingest_all_vector_chunks,
        ingest_graph_dates,
        load_search_documents,
        migrate_atomic_vector_chunks,
        select_ingestion_dates,
    )

    coordinator: IndexBuildCoordinator = app.state.index_coordinator
    selected_dates = select_ingestion_dates(dates)
    generation_id = datetime.now(timezone.utc).strftime("gen-%Y%m%dT%H%M%S") + f"-{uuid.uuid4().hex[:8]}"
    old_state = await _get_rag_state()

    async def build(staging_path: Path) -> VectorBuildResult:
        def build_sync() -> VectorBuildResult:
            staging_store = VectorStore(str(staging_path))
            lexical_store = LexicalStore(staging_path / "lexical.sqlite3")
            try:
                documents = load_search_documents()
                ingested_at = datetime.now(timezone.utc).isoformat()
                documents = [{**document, "ingested_at": ingested_at} for document in documents]
                from rag.temporal_semantics import audit_temporal_documents

                temporal_gate = audit_temporal_documents(documents)
                if not temporal_gate["passed"]:
                    raise RuntimeError("runtime temporal provenance gate failed")
                migration_report: dict = {}
                count = migrate_atomic_vector_chunks(
                    old_state.vector_store,
                    staging_store,
                    documents,
                    report_sink=migration_report,
                )
                migration_report["temporal_gate"] = temporal_gate
                if old_state.vector_store.count() > 0 and count == 0:
                    raise RuntimeError(
                        "existing vectors could not be mapped to atomic search documents; "
                        "full re-embedding was stopped"
                    )
                if old_state.vector_store.count() == 0:
                    count = ingest_all_vector_chunks(staging_store)
                lexical_count = lexical_store.rebuild(documents)
                return VectorBuildResult(
                    chunk_count=count,
                    dates=select_ingestion_dates(None),
                    corpus_revision=_corpus_revision(),
                    lexical_count=lexical_count,
                    migration_report=migration_report,
                )
            finally:
                lexical_store.close()
                staging_store.close()

        return await asyncio.to_thread(build_sync)

    async def prepare_runtime(generation_path: Path, manifest: dict) -> RagState:
        current = await _get_rag_state()
        vector_store = VectorStore(str(generation_path))
        lexical_store = LexicalStore(generation_path / "lexical.sqlite3")
        retriever, agent = _build_retrieval_runtime(
            vector_store,
            current.neo4j_driver,
            current.answer_composer,
            "vector-only",
            lexical_store,
        )
        return dataclasses.replace(
            current,
            vector_store=vector_store,
            lexical_store=lexical_store,
            chat_retriever=retriever,
            retrieval_gateway=_build_retrieval_gateway(retriever, lexical_store),
            agent=agent,
            generation_id=str(manifest["generation_id"]),
            latest_corpus_date=(manifest.get("dates") or [None])[0],
            retriever_mode="vector-only",
            index_status="graph_maintenance" if current.neo4j_driver else "vector_ready_graph_unavailable",
        )

    def publish_runtime(runtime: RagState) -> None:
        app.state.rag = runtime

    published = await coordinator.build_and_publish(
        generation_id,
        build=build,
        prepare_runtime=prepare_runtime,
        publish_runtime=publish_runtime,
    )

    try:
        await _runtime_leases().wait_for_generation(old_state.generation_id, timeout=CHAT_REQUEST_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        current = await _get_rag_state()
        app.state.rag = dataclasses.replace(current, index_status="graph_drain_timeout")
        raise RuntimeError("old Hybrid runtime did not drain before graph maintenance") from exc

    if old_state.vector_store is not (await _get_rag_state()).vector_store:
        old_state.vector_store.close()
    if old_state.lexical_store and old_state.lexical_store is not (await _get_rag_state()).lexical_store:
        old_state.lexical_store.close()

    current = await _get_rag_state()
    if current.neo4j_driver is None:
        return len(selected_dates), {
            "is_consistent": False,
            "status": "unavailable",
            "error_code": "graph_unavailable",
            "generation_id": published.manifest["generation_id"],
        }

    try:
        graph_dates = await ingest_graph_dates(current.neo4j_driver, selected_dates)
        report = await post_ingestion_verify(current.neo4j_driver, current.vector_store, graph_dates)
        if not report.is_consistent:
            app.state.rag = dataclasses.replace(current, index_status="graph_inconsistent")
            return len(graph_dates), report.to_dict()
        retriever, agent = _build_retrieval_runtime(
            current.vector_store,
            current.neo4j_driver,
            current.answer_composer,
            "hybrid",
            current.lexical_store,
        )
        app.state.rag = dataclasses.replace(
            current,
            chat_retriever=retriever,
            retrieval_gateway=_build_retrieval_gateway(retriever, current.lexical_store),
            agent=agent,
            retriever_mode="hybrid",
            index_status="ready",
        )
        return len(graph_dates), report.to_dict()
    except Exception:
        current = await _get_rag_state()
        app.state.rag = dataclasses.replace(current, index_status="graph_update_failed")
        raise


async def _rebuild_runtime_index(dates: list[str] | None = None) -> tuple[int, dict]:
    """Serialize the complete vector + graph maintenance transaction."""
    async with INDEX_MAINTENANCE_LOCK:
        return await _rebuild_runtime_index_unlocked(dates)


async def _build_shadow_index() -> dict:
    """Build and audit an isolated generation without changing runtime state."""
    from rag.ingest import load_search_documents, migrate_atomic_vector_chunks, select_ingestion_dates

    async with INDEX_MAINTENANCE_LOCK:
        current = await _get_rag_state()
        store: IndexGenerationStore = app.state.generation_store
        generation_id = datetime.now(timezone.utc).strftime("shadow-%Y%m%dT%H%M%S") + f"-{uuid.uuid4().hex[:8]}"
        staging_path = store.create_staging(generation_id)
        try:
            def build_sync() -> dict:
                vector = VectorStore(str(staging_path))
                lexical = LexicalStore(staging_path / "lexical.sqlite3")
                report: dict = {}
                try:
                    documents = load_search_documents()
                    ingested_at = datetime.now(timezone.utc).isoformat()
                    documents = [{**document, "ingested_at": ingested_at} for document in documents]
                    from rag.temporal_semantics import audit_temporal_documents

                    temporal_gate = audit_temporal_documents(documents)
                    report["temporal_gate"] = temporal_gate
                    if not temporal_gate["passed"]:
                        raise RuntimeError("shadow temporal provenance gate failed")
                    count = migrate_atomic_vector_chunks(
                        current.vector_store,
                        vector,
                        documents,
                        report_sink=report,
                    )
                    lexical_count = lexical.rebuild(documents)
                    expected = int(report.get("target_document_count") or 0)
                    report["lexical_count"] = lexical_count
                    report["complete"] = bool(expected) and count == expected and lexical_count == expected
                    if not report["complete"]:
                        raise RuntimeError("shadow migration completeness gate failed")
                    manifest = store.write_verified_manifest(
                        staging_path,
                        chunk_count=count,
                        dates=select_ingestion_dates(None),
                        corpus_revision=_corpus_revision(),
                        lexical_count=lexical_count,
                    )
                    return store.mark_shadow_ready(staging_path, manifest, report)
                finally:
                    lexical.close()
                    vector.close()

            return await asyncio.to_thread(build_sync)
        except Exception as exc:
            if staging_path.exists():
                store.mark_failed(staging_path, type(exc).__name__)
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Topic Radar RAG server v%s", APP_VERSION)

    # Upstream Pages may still publish the legacy topics/excerpts index. Rebuild
    # this project's atomic item projection before the UI starts serving it.
    from rag.ingest import load_search_documents
    await asyncio.to_thread(load_search_documents)

    generation_store = IndexGenerationStore(INDEX_GENERATIONS_DIR)
    active_generation = generation_store.resolve_active()
    vector_path = str(active_generation or Path(CHROMA_DIR))
    generation_id = active_generation.name if active_generation else "legacy"
    latest_corpus_date = _latest_generation_date(active_generation)
    vector_store = VectorStore(vector_path)
    lexical_path = Path(vector_path) / "lexical.sqlite3"
    lexical_store = LexicalStore(lexical_path) if lexical_path.exists() else None
    app.state.generation_store = generation_store
    app.state.index_coordinator = IndexBuildCoordinator(generation_store)
    app.state.runtime_leases = RuntimeLeaseRegistry()
    runtime_settings = load_runtime_settings(deep_fetch_default=is_deep_fetch_enabled())
    external_search_registry = (
        SearchProviderRegistry(get_search_provider_api_keys())
        if runtime_settings["web_search_enabled"]
        else None
    )
    external_deep_fetcher = select_external_deep_fetcher(runtime_settings["deep_fetch_enabled"])

    neo4j_driver = None
    chat_retriever = None
    agent = None
    answer_composer = None

    if is_configured():
        neo4j_driver = Neo4jDriver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        try:
            await neo4j_driver.connect()
            await init_schema(neo4j_driver)
            logger.info("Neo4j connected successfully")
        except Exception as e:
            logger.error("Neo4j connection failed: %s", e)
            neo4j_driver = None

        try:
            answer_composer = create_direct_llm_agent()
            if neo4j_driver:
                chat_retriever, agent = _build_retrieval_runtime(
                    vector_store,
                    neo4j_driver,
                    answer_composer,
                    "hybrid",
                    lexical_store,
                )
                logger.info("Agent initialized with 6 tools")
            else:
                chat_retriever, agent = _build_retrieval_runtime(
                    vector_store,
                    None,
                    answer_composer,
                    "vector-only",
                    lexical_store,
                )
                logger.info("Neo4j unavailable, vector-only chat fallback initialized")
        except Exception as e:
            logger.error("Agent creation failed: %s", e)

    retrieval_gateway = _build_retrieval_gateway(chat_retriever, lexical_store)
    query_contract_resolver = _build_query_contract_resolver()

    # 原子设置 RagState，后续通过 dataclasses.replace() 更新
    app.state.rag = RagState(
        vector_store=vector_store,
        neo4j_driver=neo4j_driver,
        chat_retriever=chat_retriever,
        agent=agent,
        answer_composer=answer_composer,
        external_search_registry=external_search_registry,
        external_deep_fetcher=external_deep_fetcher,
        lexical_store=lexical_store,
        retrieval_gateway=retrieval_gateway,
        query_contract_resolver=query_contract_resolver,
        generation_id=generation_id,
        latest_corpus_date=latest_corpus_date,
        retriever_mode="hybrid" if neo4j_driver else "vector-only",
    )

    async def refresh_corpus_in_process() -> None:
        from rag.corpus_update import update_corpus

        try:
            async with CORPUS_UPDATE_LOCK:
                result = await update_corpus(
                    days=int(os.getenv("RAG_CORPUS_RECHECK_DAYS", "30")),
                    ingester=_rebuild_runtime_index,
                )
            logger.info("Startup corpus update finished with status=%s", result.status)
        except Exception as exc:
            logger.error("Startup corpus update failed; keeping last-known-good runtime: %s", exc)

    if is_startup_corpus_update_enabled():
        app.state.corpus_update_task = asyncio.create_task(refresh_corpus_in_process())
    else:
        app.state.corpus_update_task = None
        logger.info("Startup corpus update is disabled; serving the frozen active index")

    yield

    update_task = getattr(app.state, "corpus_update_task", None)
    if update_task and not update_task.done():
        update_task.cancel()
        with suppress(asyncio.CancelledError):
            await update_task

    rag: RagState | None = getattr(app.state, "rag", None)
    if rag and rag.neo4j_driver:
        await rag.neo4j_driver.close()
        logger.info("Neo4j connection closed")
    if rag and rag.vector_store:
        rag.vector_store.close()
    if rag and rag.lexical_store:
        rag.lexical_store.close()


app = FastAPI(title="AI Topic Radar RAG", version=APP_VERSION, lifespan=lifespan)

# C-6 修复：注册速率限制中间件（仅影响 /chat POST 端点）
app.add_middleware(RateLimitMiddleware)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DASHBOARD_HTML = PROJECT_ROOT / "index.html"
CHAT_HTML = Path(__file__).parent / "web" / "chat.html"


@app.get("/", response_class=HTMLResponse)
async def index():
    """服务仪表盘首页"""
    if not DASHBOARD_HTML.exists():
        # 降级到chat.html
        if CHAT_HTML.exists():
            return FileResponse(str(CHAT_HTML), media_type="text/html")
        raise HTTPException(status_code=500, detail="Dashboard UI not found")
    return FileResponse(str(DASHBOARD_HTML), media_type="text/html")


@app.get("/chat", response_class=HTMLResponse)
async def chat_ui():
    """服务聊天UI（兼容旧路由）"""
    if not CHAT_HTML.exists():
        raise HTTPException(status_code=500, detail="Chat UI not found")
    return FileResponse(str(CHAT_HTML), media_type="text/html")


@app.get("/health")
async def health(rag: RagState = Depends(_get_rag_state)):
    """Cheap readiness probe; deep consistency lives at /health/consistency."""
    result = {
        "status": "ok",
        "configured": is_configured(),
        "neo4j_connected": rag.neo4j_driver is not None,
        "chromadb_chunks": rag.vector_store.count() if rag.vector_store else 0,
        "provider": LLM_PROVIDER,
        "retriever_mode": rag.retriever_mode,
        "index_generation": rag.generation_id,
        "index_status": rag.index_status,
        "deep_fetch_enabled": rag.external_deep_fetcher is not None,
    }

    return result


@app.get("/health/consistency")
async def health_consistency(rag: RagState = Depends(_get_rag_state)):
    """详细的数据一致性校验端点（G-4 修复）。

    返回 Neo4j 与 ChromaDB 之间完整的日期覆盖对比。
    """
    if not rag.neo4j_driver:
        raise HTTPException(
            status_code=503,
            detail="Neo4j not connected — consistency check requires both stores.",
        )
    if not rag.vector_store:
        raise HTTPException(
            status_code=503,
            detail="ChromaDB not available — consistency check requires both stores.",
        )

    try:
        from rag.consistency import check_consistency
        report = await check_consistency(rag.neo4j_driver, rag.vector_store)
        return {
            "status": "consistent" if report.is_consistent else "inconsistent",
            **report.to_dict(),
        }
    except Exception as e:
        logger.error("Consistency check failed: %s", e)
        raise HTTPException(status_code=500, detail="Consistency check failed. Check server logs.")


@app.get("/dashboard/status")
async def dashboard_status(rag: RagState = Depends(_get_rag_state)):
    """返回仪表盘完整的系统状态"""
    # 获取搜索provider信息
    search_providers = sorted(get_configured_search_providers())

    # 获取最新语料日期
    latest_corpus_date = getattr(rag, "latest_corpus_date", None)
    if latest_corpus_date is None:
        digests_dir = PROJECT_ROOT / "digests"
        if digests_dir.exists():
            dates = sorted([d.name for d in digests_dir.iterdir() if d.is_dir()], reverse=True)
            if dates:
                latest_corpus_date = dates[0]

    # C-2: 对响应中的 API Key 做掩码处理
    raw_keys = get_search_provider_api_keys()
    masked_keys = {k: _mask_secret(v) for k, v in raw_keys.items()}
    corpus_update = summarize_update_state(load_update_state())
    corpus_mode = "managed" if is_startup_corpus_update_enabled() else "frozen"
    if corpus_mode == "frozen":
        # The durable ledger may contain an interrupted historic "syncing"
        # state.  In frozen mode no updater is running, so expose the active
        # runtime truth instead of presenting that stale state to the user.
        corpus_update = {**corpus_update, "status": "frozen"}

    return {
        "service": "ai-trend-radar-rag",
        "configured": is_configured(),
        "provider": LLM_PROVIDER,
        "neo4j_connected": rag.neo4j_driver is not None,
        "chromadb_chunks": rag.vector_store.count() if rag.vector_store else 0,
        "retriever_mode": rag.retriever_mode,
        "index_generation": rag.generation_id,
        "index_status": rag.index_status,
        "deep_fetch_enabled": rag.external_deep_fetcher is not None,
        "search_providers": search_providers,
        "search_api_keys_masked": masked_keys,
        "latest_corpus_date": latest_corpus_date,
        "corpus_mode": corpus_mode,
        "corpus_update": corpus_update,
        "service_version": APP_VERSION,
        "web_search_enabled": rag.external_search_registry is not None and len(search_providers) > 0,
        "web_search_capability": "available" if search_providers else "unconfigured",
    }


@app.post("/runtime/reconnect-databases")
async def reconnect_databases(api_key: str = Depends(verify_api_key)):
    """Reconnect the existing Neo4j service without rebuilding data or images.

    This endpoint deliberately has no shell or Docker control.  The launcher is
    responsible for starting the existing Compose stack; this action only
    repairs an application-to-database connection that was unavailable during
    server startup or dropped later.
    """
    async with RAG_CONFIG_LOCK:
        current = await _get_rag_state()
        candidate = Neo4jDriver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        try:
            await candidate.connect()
            retriever, agent = _build_retrieval_runtime(
                current.vector_store,
                candidate,
                current.answer_composer,
                "hybrid",
                current.lexical_store,
            )
            updated = dataclasses.replace(
                current,
                neo4j_driver=candidate,
                chat_retriever=retriever,
                agent=agent,
                retrieval_gateway=_build_retrieval_gateway(retriever, current.lexical_store),
                retriever_mode="hybrid",
                index_status="ready",
            )
            app.state.rag = updated
        except Exception as exc:
            await candidate.close()
            logger.warning("Neo4j runtime reconnect failed: %s", type(exc).__name__)
            raise HTTPException(
                status_code=503,
                detail="Neo4j is not ready. Start the existing stack with start.command, then retry.",
            ) from exc

        if current.neo4j_driver is not None and current.neo4j_driver is not candidate:
            await current.neo4j_driver.close()

        return {
            "status": "connected",
            "neo4j_connected": True,
            "retriever_mode": "hybrid",
            "index_generation": updated.generation_id,
        }


@app.post("/config/web-search")
async def toggle_web_search(enabled: bool, api_key: str = Depends(verify_api_key),
                             rag: RagState = Depends(_get_rag_state)):
    """切换联网搜索状态 — 通过 dataclasses.replace() 原子替换状态"""
    async with RAG_CONFIG_LOCK:
        current = await _get_rag_state()
        configured_providers = get_configured_search_providers()
        if enabled and not configured_providers:
            raise HTTPException(
                status_code=409,
                detail="No web search provider is configured. Add at least one provider API key first.",
            )
        new_registry = None
        if enabled:
            from rag.search_provider_adapters import SearchProviderRegistry
            from rag.config import get_search_provider_api_keys as _get_keys
            new_registry = current.external_search_registry or SearchProviderRegistry(_get_keys())
        # Persist first: if disk write fails, the in-memory state remains truthful.
        save_runtime_setting(
            "web_search_enabled",
            enabled,
            deep_fetch_default=current.external_deep_fetcher is not None,
        )
        app.state.rag = dataclasses.replace(current, external_search_registry=new_registry)
    logger.info("Web search %s", "enabled" if enabled else "disabled")
    return {"status": "ok", "web_search_enabled": enabled}


@app.post("/config/deep-fetch")
async def toggle_deep_fetch(enabled: bool, api_key: str = Depends(verify_api_key),
                             rag: RagState = Depends(_get_rag_state)):
    """切换深度抓取状态"""
    async with RAG_CONFIG_LOCK:
        current = await _get_rag_state()
        new_fetcher = select_external_deep_fetcher(enabled)
        save_runtime_setting(
            "deep_fetch_enabled",
            enabled,
            deep_fetch_default=current.external_deep_fetcher is not None,
        )
        os.environ["RAG_ENABLE_DEEP_FETCH"] = "true" if enabled else "false"
        app.state.rag = dataclasses.replace(current, external_deep_fetcher=new_fetcher)
    logger.info("Deep fetch %s", "enabled" if enabled else "disabled")
    return {"status": "ok", "deep_fetch_enabled": enabled}


@app.post("/config/retriever-mode")
async def set_retriever_mode(mode: str, api_key: str = Depends(verify_api_key),
                              rag: RagState = Depends(_get_rag_state)):
    """设置检索模式 — 原子替换 retriever"""
    allowed_modes = {"hybrid", "vector-only", "graph-only"}
    if mode not in allowed_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Allowed: {allowed_modes}")

    async with RAG_CONFIG_LOCK:
        coordinator = getattr(app.state, "index_coordinator", None)
        if coordinator is not None and coordinator.updating:
            raise HTTPException(
                status_code=409,
                detail="Index maintenance is in progress. Retriever mode cannot change yet.",
            )
        current = await _get_rag_state()
        if current.index_status != "ready":
            raise HTTPException(
                status_code=409,
                detail="Index maintenance is not complete. Retriever mode cannot change yet.",
            )
        if mode == "graph-only" and current.neo4j_driver:
            # 需要实现GraphOnlyRetriever
            raise HTTPException(status_code=400, detail="Graph-only mode not yet implemented")
        try:
            new_retriever, new_agent = _build_retrieval_runtime(
                current.vector_store,
                current.neo4j_driver,
                current.answer_composer,
                mode,
                current.lexical_store,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        app.state.rag = dataclasses.replace(
            current,
            chat_retriever=new_retriever,
            retrieval_gateway=_build_retrieval_gateway(new_retriever, current.lexical_store),
            agent=new_agent,
            retriever_mode=mode,
        )
    logger.info("Retriever mode set to: %s", mode)
    return {"status": "ok", "retriever_mode": mode}


@app.get("/briefs")
async def list_briefs():
    """列出所有Trend Brief制品"""
    briefs_dir = PROJECT_ROOT / "docs" / "rag-transformation" / "briefs"

    if not briefs_dir.exists():
        return {"briefs": []}

    briefs = []
    for brief_file in sorted(briefs_dir.glob("*.md"), reverse=True):
        try:
            content = brief_file.read_text(encoding="utf-8")

            # 解析元数据
            title = brief_file.stem
            topic = ""
            generated_date = ""
            mode = ""
            source_quality = ""

            # 解析键值对格式（Generated at:, Mode:等）
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("# Trend Brief:"):
                    title = line[14:].strip()
                elif line.startswith("- Generated at:"):
                    generated_date = line[15:].strip()
                    # 提取日期部分（2026-06-24T12:56:41... -> 2026-06-24）
                    if "T" in generated_date:
                        generated_date = generated_date.split("T")[0]
                elif line.startswith("- Mode:"):
                    mode = line[7:].strip()
                elif line.startswith("- Policy mode:"):
                    # Policy mode可以作为source_quality的参考
                    pass

            # 从文件名提取日期作为备选
            if not generated_date:
                # 文件名格式：trend-brief-rag-2026-06-24.md
                parts = brief_file.stem.split("-")
                if len(parts) >= 4:
                    generated_date = "-".join(parts[-3:])

            briefs.append({
                "title": title,
                "topic": topic,
                "generated_date": generated_date,
                "mode": mode,
                "source_quality": source_quality,
                "path": str(brief_file.relative_to(PROJECT_ROOT)),
            })
        except Exception as e:
            logger.error("Error reading brief %s: %s", brief_file, e)
            continue

    return {"briefs": briefs}


@app.post("/config")
async def save_config(req: ConfigRequest, api_key: str = Depends(verify_api_key)):
    """保存配置（需要API Key认证）

    注意：此端点将 API Key 明文写入 .env 文件，仅限受信任环境使用。
    生产环境应通过环境变量或密钥管理服务配置。
    """
    # 验证provider白名单
    allowed_providers = {"anthropic", "openai", "deepseek"}
    if req.provider not in allowed_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider. Allowed: {allowed_providers}"
        )

    # 验证Neo4j URI格式
    if not req.neo4j_uri.startswith(("bolt://", "neo4j://")):
        raise HTTPException(
            status_code=400,
            detail="Invalid Neo4j URI. Must start with bolt:// or neo4j://"
        )

    env_path = Path(__file__).parent.parent / ".env"
    try:
        # C-3 修复：使用文件锁 + 原子写入（先写临时文件再 rename）防止并发竞态。
        # 1. 用 fcntl.flock 对 .env 加排他锁，其他并发请求阻塞等待
        # 2. 在同目录写临时文件，完成后 os.replace 原子替换，避免半写状态
        lock_path = env_path.with_suffix(".env.lock")

        # 创建锁文件（如果不存在）并获取排他锁
        lock_fd = open(lock_path, "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)  # 阻塞直到获取锁

            lines = []
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()

            updates = {
                "LLM_PROVIDER": req.provider,
                "ANTHROPIC_API_KEY": req.api_key if req.provider == "anthropic" else "",
                "OPENAI_API_KEY": req.api_key if req.provider == "openai" else "",
                "DEEPSEEK_API_KEY": req.api_key if req.provider == "deepseek" else "",
                "NEO4J_URI": req.neo4j_uri,
                "NEO4J_PASSWORD": req.neo4j_password,
            }

            updated_keys = set()
            new_lines = []
            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=", 1)[0].strip()
                    if key in updates:
                        new_lines.append(f"{key}={updates[key]}")
                        updated_keys.add(key)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            for key, val in updates.items():
                if key not in updated_keys:
                    new_lines.append(f"{key}={val}")

            # 原子写入：先写临时文件，再 os.replace 替换目标文件。
            # os.replace 在 POSIX 上是原子操作，不会出现半写状态。
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(env_path.parent), suffix=".env.tmp"
            )
            fd_closed = False
            try:
                os.write(tmp_fd, ("\n".join(new_lines) + "\n").encode("utf-8"))
                os.close(tmp_fd)
                fd_closed = True
                os.replace(tmp_path, str(env_path))  # 原子替换
            except BaseException:
                if not fd_closed:
                    os.close(tmp_fd)
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

        logger.info("Configuration saved successfully")
        # C-2: 日志和响应中对敏感配置做掩码
        logger.info("Saved provider=%s, api_key=%s, neo4j_uri=%s",
                     req.provider, _mask_secret(req.api_key), req.neo4j_uri)
        return {"status": "ok", "message": "Configuration saved. Please restart the server."}
    except Exception as e:
        # C-4 修复：对外返回通用错误消息，详细错误仅写日志
        logger.error("Config save failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save configuration. Check server logs for details.")


@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    _api_key: str = Depends(verify_api_key),
    rag: RagState = Depends(_get_rag_state),
):
    """Agent聊天端点 — C-6 修复：添加整体请求超时"""
    if not rag.agent:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Check Neo4j connection and API key configuration.",
        )

    try:
        async with _runtime_leases().lease(rag.generation_id, rag.retriever_mode):
            # 总超时（195s）高于最长 180 秒 Agent 预算，确保内部阶段先给出可诊断反馈。
            response = await asyncio.wait_for(
                build_chat_response(
                    rag.agent,
                    rag.chat_retriever,
                    req.message,
                    req.history,
                    context=req.context,
                    web_search_mode=req.web_search_mode,
                    external_search_registry=rag.external_search_registry,
                    external_deep_fetcher=rag.external_deep_fetcher,
                    answer_composer=rag.answer_composer,
                    retrieval_gateway=rag.retrieval_gateway,
                    query_contract_resolver=rag.query_contract_resolver,
                    latest_corpus_date=rag.latest_corpus_date,
                ),
                timeout=CHAT_REQUEST_TIMEOUT_SECONDS,
            )
        return ChatResponse(**response)
    except asyncio.TimeoutError:
        logger.error("Chat request timed out after %ds", CHAT_REQUEST_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=504,
            detail="Request timed out. Please simplify your question or try again later.",
        )
    except Exception as e:
        # C-4 修复：对外返回通用错误消息，详细错误仅写日志
        logger.error("Chat error: %s", e)
        raise HTTPException(status_code=500, detail="Chat processing failed. Please try again later.")


@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    _api_key: str = Depends(verify_api_key),
    rag: RagState = Depends(_get_rag_state),
):
    """Stream truthful execution progress and a validated answer as NDJSON."""
    if not rag.agent:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Check Neo4j connection and API key configuration.",
        )

    async def build(progress_callback):
        return await build_chat_response(
            rag.agent,
            rag.chat_retriever,
            req.message,
            req.history,
            context=req.context,
            web_search_mode=req.web_search_mode,
            external_search_registry=rag.external_search_registry,
            external_deep_fetcher=rag.external_deep_fetcher,
            answer_composer=rag.answer_composer,
            retrieval_gateway=rag.retrieval_gateway,
            query_contract_resolver=rag.query_contract_resolver,
            latest_corpus_date=rag.latest_corpus_date,
            progress_callback=progress_callback,
        )

    async def body():
        async with _runtime_leases().lease(rag.generation_id, rag.retriever_mode):
            async for event in iter_chat_events(
                build,
                timeout_seconds=CHAT_REQUEST_TIMEOUT_SECONDS,
            ):
                yield encode_stream_event(event)

    return StreamingResponse(
        body(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/ingest")
async def trigger_ingest(date: str | None = None, api_key: str = Depends(verify_api_key)):
    """Build and publish a complete last-known-good index generation."""

    try:
        count, consistency = await _rebuild_runtime_index([date] if date else None)
        logger.info("Ingestion completed: %d dates ingested", count)
        result = {"status": "ok", "dates_ingested": count}
        if consistency:
            result["consistency_check"] = consistency
            if not consistency.get("is_consistent", True):
                result["status"] = "partial"
                logger.warning("Ingestion completed with consistency issues: %s", consistency)
        return result
    except Exception as e:
        # C-4 修复：对外返回通用错误消息，详细错误仅写日志
        logger.error("Ingestion failed: %s", e)
        raise HTTPException(status_code=500, detail="Ingestion failed. Check server logs for details.")


@app.post("/ingest/shadow")
async def trigger_shadow_ingest(api_key: str = Depends(verify_api_key)):
    """Build an audited shadow generation without activating it."""
    try:
        manifest = await _build_shadow_index()
        return {
            "status": "shadow_ready",
            "generation_id": manifest["generation_id"],
            "migration_report": manifest["migration_report"],
        }
    except Exception as exc:
        logger.error("Shadow ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail="Shadow ingestion failed. Active index was not changed.")


@app.post("/corpus/update")
async def trigger_corpus_update(
    request: CorpusUpdateRequest,
    api_key: str = Depends(verify_api_key),
):
    """Synchronize corpus and publish it through the single-writer path."""
    from rag.corpus_update import DEFAULT_BASE_URL, update_corpus

    try:
        async with CORPUS_UPDATE_LOCK:
            result = await update_corpus(
                base_url=request.base_url or DEFAULT_BASE_URL,
                days=request.days,
                dry_run=request.dry_run,
                ingester=_rebuild_runtime_index,
            )
        return result.to_dict()
    except Exception as exc:
        logger.error("Corpus update failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Corpus update failed. Check server logs for details.",
        ) from exc


@app.get("/metrics")
async def get_metrics():
    """获取系统指标摘要（C-5 修复）。

    返回检索质量、响应时间、工具调用分布等聚合指标。
    用于监控和评估 RAG 系统性能。
    """
    from rag.metrics import metrics_collector

    summary = metrics_collector.get_summary()
    return {
        "status": "ok",
        "metrics": summary.to_dict(),
    }


@app.get("/metrics/recent")
async def get_recent_metrics(count: int = 10):
    """获取最近的请求指标样本（C-5 修复）。

    Args:
        count: 返回的样本数量，默认10，最大100。

    用于调试和实时监控。
    """
    from rag.metrics import metrics_collector

    count = min(max(count, 1), 100)
    samples = metrics_collector.get_recent_samples(count)
    return {
        "status": "ok",
        "samples": samples,
        "count": len(samples),
    }


# 静态文件配置 - 服务项目根目录的静态文件
# manifest.json、digests、feed.xml、assets等
# 添加容错处理，目录不存在时不挂载
if (PROJECT_ROOT / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(PROJECT_ROOT / "assets")), name="assets")
else:
    logger.warning("Assets directory not found, skipping mount")

if (PROJECT_ROOT / "digests").exists():
    app.mount("/digests", StaticFiles(directory=str(PROJECT_ROOT / "digests")), name="digests")
else:
    logger.warning("Digests directory not found, skipping mount")

# 服务docs目录（用于Briefs功能）
if (PROJECT_ROOT / "docs").exists():
    app.mount("/docs", StaticFiles(directory=str(PROJECT_ROOT / "docs")), name="docs")
else:
    logger.warning("Docs directory not found, skipping mount")


@app.get("/manifest.json")
async def manifest():
    """服务manifest.json"""
    manifest_path = PROJECT_ROOT / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found")
    return FileResponse(str(manifest_path), media_type="application/json")


@app.get("/feed.xml")
async def feed():
    """服务RSS feed"""
    feed_path = PROJECT_ROOT / "feed.xml"
    if not feed_path.exists():
        raise HTTPException(status_code=404, detail="Feed not found")
    return FileResponse(str(feed_path), media_type="application/xml")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=RAG_HOST, port=RAG_PORT)
