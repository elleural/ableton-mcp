"""The Remote Script's hot reload must leave no stale module anywhere (offline, temp copy of the package)."""
import shutil
import sys
import types
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "AbletonMCP_Remote_Script"
PACKAGE = "AbletonMCP_reload_test"


@pytest.fixture
def shell(tmp_path, monkeypatch):
    shutil.copytree(SOURCE, tmp_path / PACKAGE, ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    module = __import__(PACKAGE)
    monkeypatch.setattr(module.AbletonMCP, "start_server", lambda self: None)
    instance = module.create_instance(None)
    yield instance, tmp_path / PACKAGE, module
    for name in [name for name in sys.modules if name == PACKAGE or name.startswith(PACKAGE + ".")]:
        del sys.modules[name]


def _assert_all_fresh(module):
    for child, value in vars(module).items():
        if isinstance(value, types.ModuleType) and value.__name__.startswith(PACKAGE + "."):
            assert sys.modules.get(value.__name__) is value, "stale package attribute: " + child


def test_reload_picks_up_changes_everywhere(shell):
    instance, root, module = shell
    assert instance.core_report["ok"] and not instance.core_report["failed"]
    (root / "values.py").write_text((root / "values.py").read_text() + "\nRELOAD_MARKER = 2\n")
    handlers_init = root / "handlers" / "__init__.py"
    handlers_init.write_text(handlers_init.read_text().replace('    "system",', '    "system",\n    "extra",'))
    (root / "handlers" / "extra.py").write_text("from ..core import command\n\n@command('extra_cmd', readonly=True)\ndef extra_cmd(ctx):\n    return 1\n")
    report = instance.load_core()
    assert report["ok"] and "extra" in report["loaded"] and "extra_cmd" in instance.core.COMMANDS
    assert sys.modules[PACKAGE + ".refs"].values.RELOAD_MARKER == 2
    assert sys.modules[PACKAGE + ".lom"].jsonable is sys.modules[PACKAGE + ".values"].jsonable
    _assert_all_fresh(module)


def test_reload_clears_orphaned_package_attributes(shell):
    """A module attached to the package but missing from sys.modules (left by an older reload) must not survive."""
    instance, root, module = shell
    orphan = sys.modules.pop(PACKAGE + ".lom")
    assert vars(module)["lom"] is orphan
    instance.load_core()
    assert sys.modules[PACKAGE + ".lom"] is not orphan
    _assert_all_fresh(module)


def test_failed_reload_keeps_previous_code(shell):
    instance, root, module = shell
    previous_core = instance.core
    (root / "core.py").write_text((root / "core.py").read_text() + "\nraise RuntimeError('broken')\n")
    report = instance.load_core()
    assert not report["ok"] and instance.core is previous_core
    assert "ping" in instance.core.COMMANDS
