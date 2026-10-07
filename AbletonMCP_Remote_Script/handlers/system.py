"""Lead-owned system commands: liveness, command listing and API introspection."""
import sys

from .. import core, introspection
from ..core import command


@command("ping", readonly=True)
def ping(ctx):
    """Liveness check reporting versions and which handler modules are loaded."""
    report = getattr(ctx.cs, "core_report", None) or {}
    return {
        "pong": True,
        "script_version": core.SCRIPT_VERSION,
        "protocol_version": core.PROTOCOL_VERSION,
        "live_version": ctx.app.get_version_string(),
        "python_version": sys.version.split()[0],
        "handlers_loaded": report.get("loaded", []),
        "handlers_failed": sorted(report.get("failed", {})),
        "command_count": len(core.COMMANDS),
    }


@command("get_commands", readonly=True)
def get_commands(ctx, include_failures=False):
    """Every registered command with its parameters; optionally handler import tracebacks."""
    out = {"commands": dict((name, spec.describe()) for name, spec in sorted(core.COMMANDS.items()))}
    if include_failures:
        out["failed"] = (getattr(ctx.cs, "core_report", None) or {}).get("failed", {})
    return out


@command("dump_live_api", readonly=True, timeout=30.0)
def dump_live_api(ctx, output_path):
    """Write the full description of Live's Python API to output_path as JSON."""
    return introspection.dump_live_api(output_path, ctx.app)

