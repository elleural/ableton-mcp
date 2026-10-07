"""Generate docs/TOOLS.md from the registered MCP tools: `uv run python scripts/gen_tool_docs.py`."""
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from MCP_Server import server  # noqa: E402,F401  (registers every tool)
from MCP_Server.app import REGISTERED_TOOLS  # noqa: E402

AREAS = [
    ("status", "Status and overview"), ("project", "Project lifecycle"), ("song", "Song, transport, scenes, locators, grooves, selection"),
    ("tracks", "Tracks, mixer and routing"), ("devices", "Devices and racks"), ("browser", "Browser"),
    ("clips", "Clips and notes"), ("automation", "Automation"), ("arrangement", "Arrangement"),
    ("export", "Export, analysis and release"), ("theory", "Music theory"), ("lom", "Object-model escape hatch"),
]


def _flags(annotations):
    flags = []
    if annotations.read_only_hint:
        flags.append("read-only")
    if annotations.destructive_hint:
        flags.append("destructive")
    return ", ".join(flags)


def _signature(func):
    parts = []
    for name, parameter in inspect.signature(func).parameters.items():
        parts.append(name if parameter.default is inspect.Parameter.empty else "{0}={1!r}".format(name, parameter.default))
    return "{0}({1})".format(func.__name__, ", ".join(parts))


def main():
    by_area = {}
    for func, annotations in REGISTERED_TOOLS:
        by_area.setdefault(func.__module__.rsplit(".", 1)[-1], []).append((func, annotations))
    lines = [
        "# AbletonMCP tools",
        "",
        "Generated from the code by `scripts/gen_tool_docs.py`; do not edit by hand. {0} tools.".format(len(REGISTERED_TOOLS)),
        "Conventions for every tool (addressing, units, errors) are in [PRD.md section 8](PRD.md#8-conventions-contract-for-every-tool).",
        "",
    ]
    for module, title in AREAS:
        tools = by_area.pop(module, [])
        if not tools:
            continue
        lines += ["## " + title, ""]
        for func, annotations in tools:
            doc = inspect.cleandoc(func.__doc__ or "")
            flags = _flags(annotations)
            lines.append("### `{0}`{1}".format(_signature(func), " *({0})*".format(flags) if flags else ""))
            lines += ["", doc, ""]
    for module, tools in sorted(by_area.items()):
        lines += ["## " + module, ""] + ["- `{0}`".format(_signature(func)) for func, _ in tools] + [""]
    (ROOT / "docs" / "TOOLS.md").write_text("\n".join(lines))
    print("Wrote docs/TOOLS.md with {0} tools".format(len(REGISTERED_TOOLS)))


if __name__ == "__main__":
    main()
