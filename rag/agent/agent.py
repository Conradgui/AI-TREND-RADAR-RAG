"""LangGraph ReAct agent for AI Topic Radar."""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from rag.agent.prompts import SYSTEM_PROMPT_ZH
from rag.agent.llm import create_chat_model
from rag.agent.tools import create_tools


def create_agent(neo4j_driver, hybrid_retriever):
    """Create a LangGraph ReAct agent with 6 RAG tools."""
    tools = create_tools(neo4j_driver, hybrid_retriever)
    llm = create_chat_model()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT_ZH,
    )
    return agent
