"""Metrics collection framework for RAG system evaluation.

问题C-5修复：提供基础的指标收集机制，用于评估检索质量和系统性能。

指标类别：
1. chat_metrics: 聊天请求级别的指标（工具调用次数、引用数、响应时间等）
2. retrieval_metrics: 检索质量指标（空结果率、引用类型分布等）
3. system_metrics: 系统级指标（请求总数、错误率等）

使用方式：
    from rag.metrics import metrics_collector
    metrics_collector.record_chat_request(...)
    summary = metrics_collector.get_summary()
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChatMetrics:
    """单次聊天请求的指标快照。"""
    timestamp: str
    query_length: int
    citation_count: int
    internal_citation_count: int
    external_citation_count: int
    tool_calls_count: int
    web_search_count: int
    deep_fetch_count: int
    has_results: bool
    response_time_ms: float
    model_calls_count: int = 0
    retrieval_ms: float = 0
    agent_ms: float = 0
    repair_ms: float = 0
    agent_timeout: bool = False
    error: str | None = None
    search_candidate_count: int = 0
    admitted_external_count: int = 0
    deep_fetch_success_count: int = 0
    deep_fetch_failure_count: int = 0


@dataclass
class MetricsSummary:
    """聚合指标摘要。"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    timeout_requests: int
    empty_result_requests: int
    avg_citations_per_request: float
    avg_tool_calls_per_request: float
    avg_response_time_ms: float
    response_time_p50_ms: float
    response_time_p95_ms: float
    avg_model_calls_per_request: float
    avg_retrieval_ms: float
    avg_agent_ms: float
    avg_repair_ms: float
    citation_type_distribution: dict[str, int]
    tool_call_distribution: dict[str, int]
    web_search_request_count: int
    provider_call_count: int
    search_candidate_count: int
    admitted_external_count: int
    deep_fetch_success_count: int
    deep_fetch_failure_count: int
    period_start: str
    period_end: str
    sample_count: int

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "timeout_requests": self.timeout_requests,
            "empty_result_requests": self.empty_result_requests,
            "empty_result_rate": (
                self.empty_result_requests / self.total_requests
                if self.total_requests > 0 else 0
            ),
            "avg_citations_per_request": round(self.avg_citations_per_request, 2),
            "avg_tool_calls_per_request": round(self.avg_tool_calls_per_request, 2),
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            "response_time_p50_ms": round(self.response_time_p50_ms, 2),
            "response_time_p95_ms": round(self.response_time_p95_ms, 2),
            "avg_model_calls_per_request": round(self.avg_model_calls_per_request, 2),
            "avg_retrieval_ms": round(self.avg_retrieval_ms, 2),
            "avg_agent_ms": round(self.avg_agent_ms, 2),
            "avg_repair_ms": round(self.avg_repair_ms, 2),
            "citation_type_distribution": self.citation_type_distribution,
            "tool_call_distribution": self.tool_call_distribution,
            "web_search_request_count": self.web_search_request_count,
            "provider_call_count": self.provider_call_count,
            "search_candidate_count": self.search_candidate_count,
            "admitted_external_count": self.admitted_external_count,
            "deep_fetch_success_count": self.deep_fetch_success_count,
            "deep_fetch_failure_count": self.deep_fetch_failure_count,
            "period": {
                "start": self.period_start,
                "end": self.period_end,
            },
            "sample_count": self.sample_count,
        }


class MetricsCollector:
    """线程安全的指标收集器。

    使用滑动窗口存储最近的指标数据，避免内存无限增长。
    """

    def __init__(self, max_samples: int = 1000):
        self._lock = Lock()
        self._max_samples = max_samples
        self._samples: list[ChatMetrics] = []
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._timeout_requests = 0
        self._start_time = datetime.now().isoformat()

    def record_chat_request(
        self,
        query_length: int,
        citation_count: int,
        internal_citation_count: int,
        external_citation_count: int,
        tool_calls_count: int,
        web_search_count: int,
        deep_fetch_count: int,
        has_results: bool,
        response_time_ms: float,
        model_calls_count: int = 0,
        retrieval_ms: float = 0,
        agent_ms: float = 0,
        repair_ms: float = 0,
        agent_timeout: bool = False,
        error: str | None = None,
        search_candidate_count: int = 0,
        admitted_external_count: int = 0,
        deep_fetch_success_count: int = 0,
        deep_fetch_failure_count: int = 0,
    ) -> None:
        """记录一次聊天请求的指标。"""
        metrics = ChatMetrics(
            timestamp=datetime.now().isoformat(),
            query_length=query_length,
            citation_count=citation_count,
            internal_citation_count=internal_citation_count,
            external_citation_count=external_citation_count,
            tool_calls_count=tool_calls_count,
            web_search_count=web_search_count,
            deep_fetch_count=deep_fetch_count,
            has_results=has_results,
            response_time_ms=response_time_ms,
            model_calls_count=model_calls_count,
            retrieval_ms=retrieval_ms,
            agent_ms=agent_ms,
            repair_ms=repair_ms,
            agent_timeout=agent_timeout,
            error=error,
            search_candidate_count=search_candidate_count,
            admitted_external_count=admitted_external_count,
            deep_fetch_success_count=deep_fetch_success_count,
            deep_fetch_failure_count=deep_fetch_failure_count,
        )

        with self._lock:
            self._total_requests += 1
            if error:
                self._failed_requests += 1
            elif agent_timeout:
                self._timeout_requests += 1
            else:
                self._successful_requests += 1

            self._samples.append(metrics)

            # 滑动窗口：超过最大样本数时移除最旧的
            if len(self._samples) > self._max_samples:
                self._samples = self._samples[-self._max_samples:]

    def get_summary(self) -> MetricsSummary:
        """获取聚合指标摘要。"""
        with self._lock:
            samples = list(self._samples)

        if not samples:
            return MetricsSummary(
                total_requests=self._total_requests,
                successful_requests=self._successful_requests,
                failed_requests=self._failed_requests,
                timeout_requests=self._timeout_requests,
                empty_result_requests=0,
                avg_citations_per_request=0,
                avg_tool_calls_per_request=0,
                avg_response_time_ms=0,
                response_time_p50_ms=0,
                response_time_p95_ms=0,
                avg_model_calls_per_request=0,
                avg_retrieval_ms=0,
                avg_agent_ms=0,
                avg_repair_ms=0,
                citation_type_distribution={},
                tool_call_distribution={},
                web_search_request_count=0,
                provider_call_count=0,
                search_candidate_count=0,
                admitted_external_count=0,
                deep_fetch_success_count=0,
                deep_fetch_failure_count=0,
                period_start=self._start_time,
                period_end=datetime.now().isoformat(),
                sample_count=0,
            )

        # 计算空结果率
        empty_results = sum(1 for s in samples if not s.has_results)

        # 计算平均值
        avg_citations = sum(s.citation_count for s in samples) / len(samples)
        avg_tool_calls = sum(s.tool_calls_count for s in samples) / len(samples)
        avg_response_time = sum(s.response_time_ms for s in samples) / len(samples)
        response_times = sorted(s.response_time_ms for s in samples)
        avg_model_calls = sum(s.model_calls_count for s in samples) / len(samples)
        avg_retrieval = sum(s.retrieval_ms for s in samples) / len(samples)
        avg_agent = sum(s.agent_ms for s in samples) / len(samples)
        avg_repair = sum(s.repair_ms for s in samples) / len(samples)

        # 引用类型分布
        citation_types: dict[str, int] = defaultdict(int)
        for s in samples:
            if s.internal_citation_count > 0:
                citation_types["internal"] += 1
            if s.external_citation_count > 0:
                citation_types["external"] += 1
            if s.citation_count == 0:
                citation_types["none"] += 1

        # 工具调用分布
        tool_distribution: dict[str, int] = defaultdict(int)
        for s in samples:
            if s.tool_calls_count == 0:
                tool_distribution["no_tools"] += 1
            elif s.tool_calls_count <= 2:
                tool_distribution["1-2_calls"] += 1
            elif s.tool_calls_count <= 4:
                tool_distribution["3-4_calls"] += 1
            else:
                tool_distribution["5+_calls"] += 1

        return MetricsSummary(
            total_requests=self._total_requests,
            successful_requests=self._successful_requests,
            failed_requests=self._failed_requests,
            timeout_requests=self._timeout_requests,
            empty_result_requests=empty_results,
            avg_citations_per_request=avg_citations,
            avg_tool_calls_per_request=avg_tool_calls,
            avg_response_time_ms=avg_response_time,
            response_time_p50_ms=_nearest_rank(response_times, 0.50),
            response_time_p95_ms=_nearest_rank(response_times, 0.95),
            avg_model_calls_per_request=avg_model_calls,
            avg_retrieval_ms=avg_retrieval,
            avg_agent_ms=avg_agent,
            avg_repair_ms=avg_repair,
            citation_type_distribution=dict(citation_types),
            tool_call_distribution=dict(tool_distribution),
            web_search_request_count=sum(1 for sample in samples if sample.web_search_count > 0),
            provider_call_count=sum(sample.web_search_count for sample in samples),
            search_candidate_count=sum(sample.search_candidate_count for sample in samples),
            admitted_external_count=sum(sample.admitted_external_count for sample in samples),
            deep_fetch_success_count=sum(sample.deep_fetch_success_count for sample in samples),
            deep_fetch_failure_count=sum(sample.deep_fetch_failure_count for sample in samples),
            period_start=samples[0].timestamp,
            period_end=samples[-1].timestamp,
            sample_count=len(samples),
        )

    def get_recent_samples(self, count: int = 10) -> list[dict]:
        """获取最近的原始样本（用于调试）。"""
        with self._lock:
            recent = self._samples[-count:]

        return [
            {
                "timestamp": s.timestamp,
                "query_length": s.query_length,
                "citation_count": s.citation_count,
                "tool_calls_count": s.tool_calls_count,
                "has_results": s.has_results,
                "response_time_ms": round(s.response_time_ms, 2),
                "model_calls_count": s.model_calls_count,
                "total_ms": round(s.response_time_ms, 2),
                "retrieval_ms": round(s.retrieval_ms, 2),
                "agent_ms": round(s.agent_ms, 2),
                "repair_ms": round(s.repair_ms, 2),
                "agent_timeout": s.agent_timeout,
                "error": s.error,
                "web_search_count": s.web_search_count,
                "search_candidate_count": s.search_candidate_count,
                "admitted_external_count": s.admitted_external_count,
                "deep_fetch_success_count": s.deep_fetch_success_count,
                "deep_fetch_failure_count": s.deep_fetch_failure_count,
            }
            for s in recent
        ]

    def reset(self) -> None:
        """重置所有指标（用于测试）。"""
        with self._lock:
            self._samples.clear()
            self._total_requests = 0
            self._successful_requests = 0
            self._failed_requests = 0
            self._timeout_requests = 0
            self._start_time = datetime.now().isoformat()


# 全局单例
metrics_collector = MetricsCollector()


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    index = max(0, min(len(values) - 1, math.ceil(percentile * len(values)) - 1))
    return values[index]
