"""Shared test setup: project root on sys.path, and stand-ins for Live's Python modules.

Offline tests import the Remote Script package, which imports `_Framework` (and handler modules
may import `Live`). Outside Live those modules do not exist, so minimal stand-ins are installed.
"""
import os
import sys
import types
from pathlib import Path

# The Remote Script's command journal belongs to the real Live; offline tests that load the package keep out of it.
os.environ.setdefault("ABLETON_MCP_JOURNAL", "off")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class _StubControlSurface(object):
    def __init__(self, c_instance=None):
        self._tasks = object()  # Live's ControlSurface uses this name for a TaskGroup.

    def song(self):
        raise RuntimeError("No Live song outside Ableton")

    def application(self):
        raise RuntimeError("No Live application outside Ableton")

    def log_message(self, *args):
        pass

    def show_message(self, *args):
        pass

    def schedule_message(self, *args):
        pass

    def update_display(self):
        pass

    def disconnect(self):
        pass


class _StubModule(types.ModuleType):
    """A module whose every attribute is another stub, so `import Live; Live.Clip.X` works."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        child = _StubModule("{0}.{1}".format(self.__name__, name))
        setattr(self, name, child)
        return child

    def __call__(self, *args, **kwargs):
        return _StubModule(self.__name__ + "()")


if "_Framework" not in sys.modules:
    framework = types.ModuleType("_Framework")
    control_surface = types.ModuleType("_Framework.ControlSurface")
    control_surface.ControlSurface = _StubControlSurface
    framework.ControlSurface = control_surface
    sys.modules["_Framework"] = framework
    sys.modules["_Framework.ControlSurface"] = control_surface

if "Live" not in sys.modules:
    sys.modules["Live"] = _StubModule("Live")
