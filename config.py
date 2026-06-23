import os
from dotenv import load_dotenv

load_dotenv()

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")
GARMIN_TOKEN_PATH = os.getenv("GARMINTOKENS", os.path.expanduser("~/.garmin_tokens"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
RENPHO_EMAIL = os.getenv("RENPHO_EMAIL", "")
RENPHO_PASSWORD = os.getenv("RENPHO_PASSWORD", "")
