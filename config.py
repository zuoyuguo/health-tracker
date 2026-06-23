import os
from dotenv import load_dotenv

load_dotenv()

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")
GARMIN_TOKEN_PATH = os.getenv("GARMINTOKENS", os.path.expanduser("~/.garmin_tokens"))
