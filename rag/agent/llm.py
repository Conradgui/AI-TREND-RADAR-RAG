"""LLM factory and lightweight adapters for RAG chat modes."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from rag.config import (
    ANTHROPIC_BASE_URL,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_PROVIDER,
    get_llm_api_key,
)


def create_chat_model():
    """Create the configured chat model."""
    api_key = get_llm_api_key()
    provider = LLM_PROVIDER.lower()

    if provider == "anthropic":
        kwargs = {"model": "claude-sonnet-4-20250514", "api_key": api_key}
        if ANTHROPIC_BASE_URL:
            kwargs["base_url"] = ANTHROPIC_BASE_URL
        return ChatAnthropic(**kwargs)

    if provider == "deepseek":
        return ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=api_key,
            base_url=DEEPSEEK_BASE_URL,
        )

    return ChatOpenAI(model="gpt-4o", api_key=api_key)


class DirectLLMAgent:
    """Small adapter exposing the same ainvoke shape used by chat_service."""

    def __init__(self, llm):
        self.llm = llm

    async def ainvoke(self, payload: dict, config=None) -> dict:
        response = await self.llm.ainvoke(payload.get("messages", []), config=config)
        return {"messages": [response]}


def create_direct_llm_agent():
    """Create a direct LLM fallback agent without tool routing."""
    return DirectLLMAgent(create_chat_model())
