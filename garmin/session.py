import os
import config


def get_token_path() -> str:
    return os.path.expanduser(config.GARMIN_TOKEN_PATH)
