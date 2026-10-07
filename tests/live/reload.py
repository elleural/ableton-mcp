"""Hot-reload the Remote Script under the shared-Live lock: `uv run python -m tests.live.reload [--full]`.

Exits non-zero when any handler module failed to import, printing the tracebacks.
"""
import json
import sys

from MCP_Server.connection import AbletonConnection, AbletonError
from tests.live.conftest import live_lock


def main(argv):
    with live_lock():
        connection = AbletonConnection()
        try:
            report = connection.send_command("reload_remote_script", {"full": "--full" in argv}, timeout=40)
        except AbletonError as error:
            print("Reload failed: {0}".format(error))
            return 2
        finally:
            connection.close()
    failed = report.get("failed") or {}
    print(json.dumps({"loaded": report.get("loaded"), "failed": sorted(failed), "command_count": report.get("command_count")}))
    for module, trace in failed.items():
        print("\n--- {0} ---\n{1}".format(module, trace))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
