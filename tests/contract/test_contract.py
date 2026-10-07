"""Offline contract between the MCP tools and the Remote Script commands (no Live needed).

- Every handler module imports cleanly outside Live.
- Every call("command", ...) in an MCP tool targets a registered command, passes only parameters the
  handler accepts, and passes every parameter the handler requires.
- Every MCP tool is documented and the catalogue stays within the PRD budget.
"""
import ast
import asyncio
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "MCP_Server" / "tools"
SHELL_COMMANDS = {"reload_remote_script"}  # Handled by the Remote Script shell, not the registry.
MAX_TOOLS = 80


@pytest.fixture(scope="module")
def registry():
    core = importlib.import_module("AbletonMCP_Remote_Script.core")
    # Always load every handler module: other unit tests may have imported only some of them,
    # and import_module is a no-op for modules already loaded, so nothing registers twice.
    report = core.load_handlers()
    assert not report["failed"], "Handler modules failed to import:\n" + "\n".join(report["failed"].values())
    return core.COMMANDS


def _tool_calls():
    """(file, line, command, keyword names, has **kwargs) for every call("...") in the tool modules."""
    found = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "call" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    keywords = [keyword.arg for keyword in node.keywords if keyword.arg not in (None, "timeout")]
                    splat = any(keyword.arg is None for keyword in node.keywords)
                    found.append((path.name, node.lineno, first.value, keywords, splat))
    return found


def test_handlers_import_offline(registry):
    assert "ping" in registry and "lom_get" in registry


def test_tool_calls_match_registered_commands(registry):
    problems = []
    for filename, line, command, keywords, splat in _tool_calls():
        where = "{0}:{1} call({2!r})".format(filename, line, command)
        if command in SHELL_COMMANDS:
            continue
        spec = registry.get(command)
        if spec is None:
            problems.append(where + ": no such Remote Script command")
            continue
        if not spec.accepts_any:
            unknown = sorted(set(keywords) - set(spec.params))
            if unknown:
                problems.append("{0}: handler does not accept {1}".format(where, unknown))
        if not splat:
            missing = sorted(set(spec.required) - set(keywords))
            if missing:
                problems.append("{0}: handler requires {1}".format(where, missing))
    assert not problems, "\n".join(problems)


def test_tools_are_documented_and_within_budget():
    from MCP_Server import server

    tools = asyncio.run(server.mcp.list_tools())
    undocumented = [tool.name for tool in tools if not (tool.description or "").strip()]
    assert not undocumented, "Tools without docstrings: {0}".format(undocumented)
    assert len(tools) <= MAX_TOOLS, "{0} tools exceeds the PRD budget of {1}".format(len(tools), MAX_TOOLS)
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names)), "Duplicate tool names"
