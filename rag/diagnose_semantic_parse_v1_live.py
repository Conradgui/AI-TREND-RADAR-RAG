"""Single-call diagnostic for incomplete SemanticParseV1 model output."""

from __future__ import annotations

import json
import os

from openai import OpenAI

from rag.semantic_parse_client import SCHEMA_PATH, SYSTEM_PROMPT


def main() -> None:
    query = "打开《潮汐编译器：把稀疏专家模型搬到端侧》。"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        timeout=45,
        max_retries=0,
    )
    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        temperature=0,
        max_tokens=1200,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT + "\nSEMANTIC_PARSE_V1_SCHEMA:\n" + json.dumps(schema, ensure_ascii=False),
            },
            {"role": "user", "content": "QUERY:\n" + query + "\n\nPUBLIC_CONTEXT:\n(none)"},
        ],
    )
    content = response.choices[0].message.content or ""
    try:
        parsed = json.loads(content)
        observed = {"json_valid": True, "top_level_keys": list(parsed), "content_length": len(content)}
    except json.JSONDecodeError as exc:
        observed = {
            "json_valid": False,
            "json_error": str(exc),
            "content_length": len(content),
            "content_tail": content[-300:],
        }
    usage = response.usage
    print(json.dumps({
        "model": response.model,
        "finish_reason": response.choices[0].finish_reason,
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        },
        **observed,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
