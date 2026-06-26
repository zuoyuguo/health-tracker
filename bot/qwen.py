from __future__ import annotations

import config

try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError("openai package required: pip install 'openai>=1.0.0'") from e

_MAX_ROUNDS = 10
_SYSTEM_PROMPT = (
    "你是用户的私人健康助手。基于以下用户健康数据回答问题，结合通用健康知识给出建议。\n"
    "回答简洁，中文，不超过 300 字。不提供医疗诊断或处方建议。"
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.DASHSCOPE_API_KEY:
            raise RuntimeError("DASHSCOPE_API_KEY not configured")
        _client = OpenAI(
            api_key=config.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _client


def chat(
    history: list[dict],
    health_context: str,
) -> tuple[str, list[dict]]:
    working = list(history)

    # Truncate to _MAX_ROUNDS pairs (keep newest), then append the last user msg
    if len(working) > _MAX_ROUNDS * 2:
        working = working[-((_MAX_ROUNDS * 2)):]

    system_content = _SYSTEM_PROMPT
    if health_context:
        system_content += f"\n\n{health_context}"

    messages = [{"role": "system", "content": system_content}] + working

    response = _get_client().chat.completions.create(
        model=config.QA_MODEL,
        messages=messages,
    )
    reply = response.choices[0].message.content or "抱歉，未能获得回答，请稍后重试。"

    updated = working + [{"role": "assistant", "content": reply}]
    return reply, updated
