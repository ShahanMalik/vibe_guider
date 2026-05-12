import sys
import importlib.util

spec = importlib.util.spec_from_file_location("app", "app.py")
app_module = importlib.util.module_from_spec(spec)
sys.modules["app"] = app_module

try:
    spec.loader.exec_module(app_module)
    print("✓ Module loaded successfully")
    print(f"✓ app object exists: {hasattr(app_module, 'app')}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
