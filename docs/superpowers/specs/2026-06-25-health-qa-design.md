# 健康问答功能设计文档

**日期：** 2026-06-25
**状态：** 架构师已批准（含修订）

---

## 概述

在现有 Telegram 健康追踪机器人中新增健康问答功能，用户可通过 `/ask` 命令以自然语言提问，机器人结合用户自身健康数据（饮食、睡眠、运动、体重）及通用健康知识给出回答，支持多轮对话。文本 AI 服务从 Claude 迁移至 Qwen（阿里云 DashScope），视觉识别（食物照片）暂保留 Claude。

---

## 功能范围

**包含：**
- `/ask <问题>` 启动问答会话
- 会话期间直接发文字继续多轮对话
- `/ask_end` 明确结束会话
- 基于过去 7 天健康数据的上下文回答
- 结合通用健康知识的建议

**不包含：**
- 医疗诊断或处方建议
- 历史问答记录持久化（重启后丢失）
- 食物照片识别迁移（保留 Claude vision）

---

## 架构

### 新增模块

| 文件 | 职责 |
|---|---|
| `bot/qwen.py` | Qwen API 客户端，发送消息、维护 history |
| `bot/health_context.py` | 查询 DB，构建过去 7 天健康数据摘要字符串 |

### 变更模块

| 文件 | 变更内容 |
|---|---|
| `bot/handlers.py` | 新增 `cmd_ask`、`cmd_ask_end`；扩展 `handle_text` 加 Q&A 续接路由 |
| `config.py` | 新增 `DASHSCOPE_API_KEY`、`QA_MODEL` |
| `main.py` / bot 注册入口 | 注册 `/ask`、`/ask_end` 命令处理器 |

---

## 详细设计

### 交互流程

```
用户：/ask 我最近睡眠质量怎么样？
bot：[查询 DB] [调用 Qwen] 根据你过去 7 天数据...

用户：那运动量够吗？          ← 直接文字，无需再 /ask
bot：[继续多轮对话]

用户：/ask_end               ← 明确退出
bot：问答已结束。

── 或 ──

用户：[发照片]               ← 自动切回食物识别模式，Q&A session 结束
```

**会话状态存储：** `context.user_data["qa_history"]`，格式为 `list[dict]`，每条 `{"role": "user"|"assistant", "content": str}`。

**会话结束条件（任一触发）：**
1. 用户发送 `/ask_end`
2. 用户发送照片（`handle_photo` 在处理前清除 `qa_history`）
3. 超过 10 分钟无消息（`handle_text` 检查 `qa_last_active` 时间戳）

**最大历史轮数：** 10 轮（20 条消息），超出时丢弃最旧的一对 user/assistant。

### `bot/health_context.py`

函数签名：
```python
def build_health_context(session, days: int = 7) -> str
```

查询范围：过去 `days` 天（以本地时区 `config.TIMEZONE` 计算起止时间）。

输出格式（无数据的字段省略）：
```
[用户健康数据摘要 - 过去7天]
睡眠：平均 6.8h，范围 5.1-8.2h，深睡均值 22%
运动：共 4 次，类型：跑步×2、力量×2，总时长 210min
饮食：平均 1850 kcal/天，蛋白质均值 72g
体重：68.2→67.8 kg（-0.4kg）
HRV：均值 52ms（3天数据）
```

### `bot/qwen.py`

使用 `openai` SDK 的 OpenAI 兼容模式调用 DashScope。客户端采用 lazy init，避免 import 时以空 key 实例化：

```python
from openai import OpenAI

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
```

核心函数返回回复文本及截断后的 history（调用方用返回值更新 `user_data`，`chat` 本身保持纯函数）：
```python
def chat(history: list[dict], health_context: str) -> tuple[str, list[dict]]
```

System prompt：
```
你是用户的私人健康助手。基于以下用户健康数据回答问题，结合通用健康知识给出建议。
回答简洁，中文，不超过 300 字。不提供医疗诊断或处方建议。

{health_context}
```

### `bot/handlers.py` 变更

**新增 `cmd_ask`：**
```python
@require_owner
async def cmd_ask(update, context):
    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text("用法：/ask <你的问题>，例如：/ask 我最近睡眠质量怎么样？")
        return
    # 首次 /ask：查一次 DB，缓存到 user_data["qa_health_context"]，后续多轮复用
    if "qa_health_context" not in context.user_data:
        with SessionLocal() as session:
            context.user_data["qa_health_context"] = build_health_context(session)
    history = context.user_data.get("qa_history", [])
    history.append({"role": "user", "content": question})
    reply, history = qwen.chat(history, context.user_data["qa_health_context"])
    context.user_data["qa_history"] = history
    context.user_data["qa_last_active"] = datetime.datetime.now(tz=datetime.timezone.utc)
    await update.message.reply_text(reply)
```

**新增 `cmd_ask_end`：**
```python
@require_owner
async def cmd_ask_end(update, context):
    context.user_data.pop("qa_history", None)
    context.user_data.pop("qa_last_active", None)
    await update.message.reply_text("问答已结束。")
```

**新增 `_qa_session_expired`：**
```python
_QA_TIMEOUT = datetime.timedelta(minutes=10)

def _qa_session_expired(context: ContextTypes.DEFAULT_TYPE) -> bool:
    last_active = context.user_data.get("qa_last_active")
    if last_active is None:
        return True
    return datetime.datetime.now(tz=datetime.timezone.utc) - last_active > _QA_TIMEOUT
```

**扩展 `handle_text`（在餐食确认逻辑之前）：**
```python
# Q&A 续接：有活跃 history 且未超时
if context.user_data.get("qa_history") and not _qa_session_expired(context):
    history = context.user_data["qa_history"]
    history.append({"role": "user", "content": text})
    reply, history = qwen.chat(history, context.user_data["qa_health_context"])
    context.user_data["qa_history"] = history
    context.user_data["qa_last_active"] = datetime.datetime.now(tz=datetime.timezone.utc)
    await update.message.reply_text(reply)
    return
```

**扩展 `handle_photo`（在"识别中..."之前清除 Q&A session）：**
```python
# 用户发照片时终止 Q&A session
context.user_data.pop("qa_history", None)
context.user_data.pop("qa_health_context", None)
context.user_data.pop("qa_last_active", None)
```

### 配置

`.env` 新增变量：
```
DASHSCOPE_API_KEY=sk-...
QA_MODEL=qwen3-max
```

`config.py` 新增：
```python
DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
QA_MODEL: str = os.getenv("QA_MODEL", "qwen3-max")
```

**启动检查策略：** `DASHSCOPE_API_KEY` 不在启动时校验（`ANTHROPIC_API_KEY` 目前也无启动检查）。未配置时由 `_get_client()` 在首次调用时抛出 `RuntimeError`，`cmd_ask` 捕获后回复用户"服务暂不可用"。两个 key 的处理方式保持一致。

---

## 错误处理

| 场景 | 处理 |
|---|---|
| `DASHSCOPE_API_KEY` 未配置 | `cmd_ask` 返回"服务暂不可用，请联系管理员" |
| Qwen API 调用失败 | 捕获异常，回复"回答失败，请稍后重试" |
| DB 查询无数据 | `build_health_context` 返回空字符串，system prompt 中省略数据块 |

---

## 依赖

新增 Python 包：
```
openai>=1.0.0
```

（DashScope 兼容模式使用 openai SDK，无需单独安装 dashscope 包）

---

## 测试要点

- `build_health_context`：各数据组合（全有、部分有、全无）
- `qwen.chat`：mock API，验证 history 截断逻辑（>10 轮），验证返回 `tuple[str, list[dict]]`
- `cmd_ask`：无参数时返回用法提示
- `handle_text` 路由：Q&A 活跃时不走餐食确认；超时后走餐食确认
- `handle_photo`：清除 Q&A session
- `cmd_ask_end`：清除 history

---

## 不在本期范围

- 分析类主动推送（"今天睡眠偏少，提醒你..."）
- 问答记录持久化到 DB
- 食物照片识别迁移至 Qwen vision
- 多用户支持
