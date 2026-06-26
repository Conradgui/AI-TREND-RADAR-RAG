"""FastAPI server — serves Dashboard UI and provides /chat, /config, /health endpoints."""

from __future__ import annotations

import asyncio
import dataclasses
import fcntl
import hmac
import logging
import os
import tempfile
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag.config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    CHROMA_DIR,
    RAG_HOST,
    RAG_PORT,
    is_configured,
    LLM_PROVIDER,
    get_search_provider_api_keys,
    is_deep_fetch_enabled,
)
from rag.graphrag.driver import Neo4jDriver
from rag.graphrag.schema import init_schema
from rag.retriever.vector_store import VectorStore
from rag.retriever.hybrid import HybridRetriever
from rag.retriever.vector_only import VectorOnlyRetriever
from rag.agent.agent import create_agent
from rag.agent.llm import create_direct_llm_agent
from rag.chat_service import build_chat_response
from rag.runtime_tools import select_external_deep_fetcher
from rag.search_provider_adapters import SearchProviderRegistry

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
CHAT_REQUEST_TIMEOUT_SECONDS = 35  # /chat 端点整体请求超时（秒），大于 agent 内部 25 秒超时


class RateLimitMiddleware:
    """滑动窗口速率限制中间件 — 仅对 /chat POST 端点生效。

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
        # 仅对 HTTP POST /chat 生效，其他请求直接放行
        if scope["type"] == "http" and scope.get("method") == "POST" and scope.get("path") == "/chat":
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
    external_search_registry: SearchProviderRegistry | None
    external_deep_fetcher: object | None


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    history: list[dict] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)  # 报告上下文：report, date, topic


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict] = Field(default_factory=list)
    query_understanding: dict = Field(default_factory=dict)
    tool_trace: dict = Field(default_factory=dict)  # 工具跟踪信息


class ConfigRequest(BaseModel):
    provider: str
    api_key: str
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_password: str = "password"


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Topic Radar RAG server v%s", APP_VERSION)

    vector_store = VectorStore(CHROMA_DIR)
    external_search_registry = SearchProviderRegistry(get_search_provider_api_keys())
    external_deep_fetcher = select_external_deep_fetcher(is_deep_fetch_enabled())

    neo4j_driver = None
    chat_retriever = None
    agent = None

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
            if neo4j_driver:
                chat_retriever = HybridRetriever(vector_store, neo4j_driver)
                agent = create_agent(neo4j_driver, chat_retriever)
                logger.info("Agent initialized with 6 tools")
            else:
                chat_retriever = VectorOnlyRetriever(vector_store)
                agent = create_direct_llm_agent()
                logger.info("Neo4j unavailable, vector-only chat fallback initialized")
        except Exception as e:
            logger.error("Agent creation failed: %s", e)

    # 原子设置 RagState，后续通过 dataclasses.replace() 更新
    app.state.rag = RagState(
        vector_store=vector_store,
        neo4j_driver=neo4j_driver,
        chat_retriever=chat_retriever,
        agent=agent,
        external_search_registry=external_search_registry,
        external_deep_fetcher=external_deep_fetcher,
    )

    yield

    rag: RagState | None = getattr(app.state, "rag", None)
    if rag and rag.neo4j_driver:
        await rag.neo4j_driver.close()
        logger.info("Neo4j connection closed")


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
    """基础健康检查端点。

    G-4 修复：当 Neo4j 和 ChromaDB 都可用时，自动附加数据一致性摘要。
    """
    result = {
        "status": "ok",
        "configured": is_configured(),
        "neo4j_connected": rag.neo4j_driver is not None,
        "chromadb_chunks": rag.vector_store.count() if rag.vector_store else 0,
        "provider": LLM_PROVIDER,
        "retriever_mode": "hybrid" if rag.neo4j_driver is not None else "vector-only",
        "deep_fetch_enabled": is_deep_fetch_enabled(),
    }

    # G-4 修复：快速一致性摘要（只在两端都可用时检查）
    if rag.neo4j_driver and rag.vector_store:
        try:
            from rag.consistency import check_consistency
            report = await check_consistency(rag.neo4j_driver, rag.vector_store)
            result["data_consistency"] = {
                "is_consistent": report.is_consistent,
                "neo4j_date_count": report.neo4j_date_count,
                "chroma_date_count": report.chroma_date_count,
            }
            if not report.is_consistent:
                result["status"] = "degraded"
        except Exception as e:
            result["data_consistency"] = {"error": str(e), "is_consistent": False}

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
    search_providers = list(get_search_provider_api_keys().keys())

    # 获取最新语料日期
    latest_corpus_date = None
    digests_dir = PROJECT_ROOT / "digests"
    if digests_dir.exists():
        dates = sorted([d.name for d in digests_dir.iterdir() if d.is_dir()], reverse=True)
        if dates:
            latest_corpus_date = dates[0]

    # C-2: 对响应中的 API Key 做掩码处理
    raw_keys = get_search_provider_api_keys()
    masked_keys = {k: _mask_secret(v) for k, v in raw_keys.items()}

    return {
        "service": "ai-trend-radar-rag",
        "configured": is_configured(),
        "provider": LLM_PROVIDER,
        "neo4j_connected": rag.neo4j_driver is not None,
        "chromadb_chunks": rag.vector_store.count() if rag.vector_store else 0,
        "retriever_mode": "hybrid" if rag.neo4j_driver is not None else "vector-only",
        "deep_fetch_enabled": is_deep_fetch_enabled(),
        "search_providers": search_providers,
        "search_api_keys_masked": masked_keys,
        "latest_corpus_date": latest_corpus_date,
        "service_version": APP_VERSION,
        "web_search_enabled": rag.external_search_registry is not None and len(search_providers) > 0,
    }


@app.post("/config/web-search")
async def toggle_web_search(enabled: bool, api_key: str = Depends(verify_api_key),
                             rag: RagState = Depends(_get_rag_state)):
    """切换联网搜索状态 — 通过 dataclasses.replace() 原子替换状态"""
    if enabled:
        if not rag.external_search_registry:
            from rag.search_provider_adapters import SearchProviderRegistry
            from rag.config import get_search_provider_api_keys as _get_keys
            new_registry = SearchProviderRegistry(_get_keys())
            app.state.rag = dataclasses.replace(rag, external_search_registry=new_registry)
        logger.info("Web search enabled")
        return {"status": "ok", "web_search_enabled": True}
    else:
        app.state.rag = dataclasses.replace(rag, external_search_registry=None)
        logger.info("Web search disabled")
        return {"status": "ok", "web_search_enabled": False}


@app.post("/config/deep-fetch")
async def toggle_deep_fetch(enabled: bool, api_key: str = Depends(verify_api_key),
                             rag: RagState = Depends(_get_rag_state)):
    """切换深度抓取状态"""
    os.environ["RAG_ENABLE_DEEP_FETCH"] = "true" if enabled else "false"
    new_fetcher = select_external_deep_fetcher(enabled)
    app.state.rag = dataclasses.replace(rag, external_deep_fetcher=new_fetcher)
    logger.info("Deep fetch %s", "enabled" if enabled else "disabled")
    return {"status": "ok", "deep_fetch_enabled": enabled}


@app.post("/config/retriever-mode")
async def set_retriever_mode(mode: str, api_key: str = Depends(verify_api_key),
                              rag: RagState = Depends(_get_rag_state)):
    """设置检索模式 — 原子替换 retriever"""
    allowed_modes = {"hybrid", "vector-only", "graph-only"}
    if mode not in allowed_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Allowed: {allowed_modes}")

    new_retriever = None
    if mode == "hybrid" and rag.neo4j_driver:
        from rag.retriever.hybrid import HybridRetriever
        new_retriever = HybridRetriever(rag.vector_store, rag.neo4j_driver)
    elif mode == "vector-only":
        from rag.retriever.vector_only import VectorOnlyRetriever
        new_retriever = VectorOnlyRetriever(rag.vector_store)
    elif mode == "graph-only" and rag.neo4j_driver:
        # 需要实现GraphOnlyRetriever
        raise HTTPException(status_code=400, detail="Graph-only mode not yet implemented")

    app.state.rag = dataclasses.replace(rag, chat_retriever=new_retriever)
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
async def chat(req: ChatRequest, rag: RagState = Depends(_get_rag_state)):
    """Agent聊天端点 — C-6 修复：添加整体请求超时"""
    if not rag.agent:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Check Neo4j connection and API key configuration.",
        )

    try:
        # C-6 修复：用 asyncio.wait_for 包裹整个请求链路，设置整体超时
        # 超时时间（35s）大于 agent 内部超时（25s），确保 agent 超时先触发并返回友好错误
        response = await asyncio.wait_for(
            build_chat_response(
                rag.agent,
                rag.chat_retriever,
                req.message,
                req.history,
                context=req.context,
                external_search_registry=rag.external_search_registry,
                external_deep_fetcher=rag.external_deep_fetcher,
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


@app.post("/ingest")
async def trigger_ingest(api_key: str = Depends(verify_api_key)):
    """数据摄取端点（需要API Key认证）。

    G-4 修复：ingestion 完成后自动执行一致性校验，结果包含在响应中。
    """
    from rag.ingest import run_ingestion

    try:
        count, consistency = await run_ingestion()
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
