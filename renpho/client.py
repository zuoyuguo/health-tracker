import config


class RenphoClientWrapper:
    def __init__(self):
        self.client = None

    def connect(self) -> None:
        if not config.RENPHO_EMAIL:
            raise ValueError("RENPHO_EMAIL is not set")
        if not config.RENPHO_PASSWORD:
            raise ValueError("RENPHO_PASSWORD is not set")

        import renpho.client as _self_module
        RenphoClientClass = _self_module.RenphoClient

        self.client = RenphoClientClass(config.RENPHO_EMAIL, config.RENPHO_PASSWORD)
        self.client.login()


# Make RenphoClient available in module namespace so it can be patched.
# __getattr__ is only called when a normal attribute lookup fails, so patched
# values injected into __dict__ by unittest.mock take precedence automatically.
def __getattr__(name):
    if name == 'RenphoClient':
        from renpho import RenphoClient
        return RenphoClient
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
