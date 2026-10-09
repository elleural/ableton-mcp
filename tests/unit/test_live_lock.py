"""The shared-Live lock is one file for every checkout, because every worktree drives the same Live (docs/PLAN.md,
shared-Live protocol). Offline: copies of tests/live/conftest.py stand in for the checkouts."""
import fcntl
import importlib.util
import shutil
from pathlib import Path

import pytest

CONFTEST = Path(__file__).resolve().parents[1] / "live" / "conftest.py"


def _checkout(root):
    """tests/live/conftest.py as a checkout at `root` loads it (a separate module each time)."""
    target = root / "tests" / "live" / "conftest.py"
    target.parent.mkdir(parents=True)
    shutil.copy(CONFTEST, target)
    spec = importlib.util.spec_from_file_location("live_conftest_copy", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_checkout_resolves_the_same_lock_outside_the_checkouts(tmp_path, monkeypatch):
    monkeypatch.delenv("ABLETON_MCP_LIVE_LOCK", raising=False)
    main = _checkout(tmp_path / "ableton-mcp")
    worktree = _checkout(tmp_path / "ableton-mcp" / ".claude" / "worktrees" / "feature")
    assert main.lock_path() == worktree.lock_path()
    assert main.lock_path().is_absolute() and tmp_path not in main.lock_path().parents


def test_the_lock_follows_the_environment_and_excludes_other_checkouts(tmp_path, monkeypatch):
    monkeypatch.setenv("ABLETON_MCP_LIVE_LOCK", str(tmp_path / "shared" / "live.lock"))
    main, worktree = _checkout(tmp_path / "main"), _checkout(tmp_path / "worktree")
    assert worktree.lock_path() == tmp_path / "shared" / "live.lock"
    with main.live_lock():
        with open(worktree.lock_path(), "a") as handle, pytest.raises(BlockingIOError):
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with open(worktree.lock_path(), "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)                    # free again once released
