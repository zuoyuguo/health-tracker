from renpho import RenphoClient
import config


class RenphoClientWrapper:
    def __init__(self):
        self.client = None

    def connect(self) -> None:
        if not config.RENPHO_EMAIL:
            raise ValueError("RENPHO_EMAIL is not set")
        if not config.RENPHO_PASSWORD:
            raise ValueError("RENPHO_PASSWORD is not set")
        self.client = RenphoClient(config.RENPHO_EMAIL, config.RENPHO_PASSWORD)
        self.client.login()
