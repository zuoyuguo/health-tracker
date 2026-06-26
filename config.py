import os
from dotenv import load_dotenv

load_dotenv()

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")
GARMIN_TOKEN_PATH = os.getenv("GARMINTOKENS", os.path.expanduser("~/.garmin_tokens"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
QA_MODEL: str = os.getenv("QA_MODEL", "qwen3-max")
_raw_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
if _raw_chat_id:
    try:
        TELEGRAM_CHAT_ID: int | None = int(_raw_chat_id)
    except ValueError:
        raise ValueError(f"TELEGRAM_CHAT_ID must be an integer, got: {_raw_chat_id!r}")
else:
    TELEGRAM_CHAT_ID = None
RENPHO_EMAIL = os.getenv("RENPHO_EMAIL", "")
RENPHO_PASSWORD = os.getenv("RENPHO_PASSWORD", "")
TIMEZONE = os.getenv("TIMEZONE", "America/Los_Angeles")
