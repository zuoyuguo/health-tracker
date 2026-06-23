import garminconnect
import config
from garmin.session import get_token_path


class GarminClient:
    def __init__(self):
        self.garmin = None

    def connect(self) -> None:
        self.garmin = garminconnect.Garmin(
            email=config.GARMIN_EMAIL,
            password=config.GARMIN_PASSWORD,
            prompt_mfa=lambda: input("请输入 Garmin MFA 验证码: "),
        )
        self.garmin.login(tokenstore=get_token_path())
