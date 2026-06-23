import os
import importlib.util
import sys

# Re-export RenphoClient and RenphoAPIError from the installed renpho-api library.
# We search sys.path for a renpho/__init__.py that is NOT our own local package.

_own_dir = os.path.dirname(os.path.abspath(__file__))
_found = False
for _path in sys.path:
    _candidate = os.path.join(_path, "renpho", "__init__.py")
    if os.path.isfile(_candidate) and os.path.dirname(os.path.abspath(_candidate)) != _own_dir:
        _spec = importlib.util.spec_from_file_location("_renpho_lib", _candidate)
        _lib = importlib.util.module_from_spec(_spec)
        sys.modules["_renpho_lib"] = _lib
        _spec.loader.exec_module(_lib)
        RenphoClient = _lib.RenphoClient
        RenphoAPIError = _lib.RenphoAPIError
        _found = True
        break
if not _found:
    raise ImportError(
        "renpho-api library not found on sys.path — install it with: pip install renpho-api"
    )
