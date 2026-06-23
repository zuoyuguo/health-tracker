import config
import sys


class RenphoClientWrapper:
    def __init__(self):
        self.client = None

    def connect(self) -> None:
        if not config.RENPHO_EMAIL:
            raise ValueError("RENPHO_EMAIL is not set")
        if not config.RENPHO_PASSWORD:
            raise ValueError("RENPHO_PASSWORD is not set")

        # Get RenphoClient from this module's namespace, allowing for mocking
        # Access through __dict__ to avoid triggering any descriptors and to get the actual patched value
        module_dict = sys.modules[__name__].__dict__
        if 'RenphoClient' in module_dict:
            RenphoClientClass = module_dict['RenphoClient']
        else:
            # First time access - import and cache it
            from renpho import RenphoClient
            RenphoClientClass = RenphoClient
            # Don't assign to module - let tests patch the namespace directly

        self.client = RenphoClientClass(config.RENPHO_EMAIL, config.RENPHO_PASSWORD)
        self.client.login()


# Make RenphoClient available in module namespace so it can be patched
# Use a lazy import wrapper that doesn't get re-executed
def __getattr__(name):
    if name == 'RenphoClient':
        from renpho import RenphoClient
        return RenphoClient
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
