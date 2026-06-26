import pytest
from unittest.mock import MagicMock, patch


def _make_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_chat_returns_reply_and_updated_history():
    from bot import qwen
    mock_resp = _make_response("睡眠还不错！")
    with patch("bot.qwen._get_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_resp

        reply, new_history = qwen.chat([], "健康数据摘要")

    assert reply == "睡眠还不错！"
    assert new_history[-1] == {"role": "assistant", "content": "睡眠还不错！"}


def test_chat_is_pure_does_not_mutate_input():
    from bot import qwen
    mock_resp = _make_response("好的")
    original = [{"role": "user", "content": "问题"}]
    with patch("bot.qwen._get_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_resp
        qwen.chat(original, "")

    assert len(original) == 1  # not mutated


def test_chat_truncates_history_beyond_10_rounds():
    from bot import qwen
    # 11 rounds = 22 messages; after truncation should be 10 rounds = 20 + new pair
    history = []
    for i in range(11):
        history.append({"role": "user", "content": f"q{i}"})
        history.append({"role": "assistant", "content": f"a{i}"})

    mock_resp = _make_response("回答")
    with patch("bot.qwen._get_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_resp
        _, new_history = qwen.chat(history, "")

    # After truncation: 10 rounds kept (20 msgs) + new user msg passed to API
    # new_history = truncated(10 rounds) + assistant reply = 21 items
    assert len(new_history) == 21
    # Oldest pair (q0/a0) dropped
    assert new_history[0]["content"] == "q1"


def test_chat_handles_none_content():
    from bot import qwen
    mock_resp = _make_response(None)
    with patch("bot.qwen._get_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_resp
        reply, _ = qwen.chat([], "")
    assert reply == "抱歉，未能获得回答，请稍后重试。"


def test_get_client_raises_when_key_missing(monkeypatch):
    import config as cfg
    monkeypatch.setattr(cfg, "DASHSCOPE_API_KEY", "")
    import bot.qwen as qwen_mod
    # Reset lazy client
    qwen_mod._client = None
    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
        qwen_mod._get_client()
