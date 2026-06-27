import os
import json
import config


def get_token_path() -> str:
    return os.path.expanduser(config.GARMIN_TOKEN_PATH)


def ensure_token_file() -> None:
    """Write token file from GARMIN_TOKEN_JSON env var if file doesn't exist."""
    token_json = os.getenv("GARMIN_TOKEN_JSON")
    if not token_json:
        return
    token_dir = get_token_path()
    os.makedirs(token_dir, exist_ok=True)
    token_file = os.path.join(token_dir, "garmin_tokens.json")
    with open(token_file, "w") as f:
        f.write(token_json)

