import sys
import importlib.util

# Re-export RenphoClient and RenphoAPIError from the installed renpho-api library
# This allows code in our renpho/ package to import them

_site_packages_path = None
for path in sys.path:
    if 'site-packages' in path:
        _site_packages_path = path
        break

if _site_packages_path:
    renpho_path = f"{_site_packages_path}/renpho"
    spec = importlib.util.spec_from_file_location("_renpho_lib", f"{renpho_path}/__init__.py")
    _lib = importlib.util.module_from_spec(spec)
    sys.modules['_renpho_lib'] = _lib
    spec.loader.exec_module(_lib)

    RenphoClient = _lib.RenphoClient
    RenphoAPIError = _lib.RenphoAPIError
