import argparse
import cmd
import json
import os
import re
import shlex
import sys
from typing import Any, Dict, List, Optional

from .server import AbletonConnection


DEFAULT_HOST = os.environ.get("ABLETON_MCP_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("ABLETON_MCP_PORT", "9877"))


class StubRegistry:
    """
    In-memory registry to stub not-yet-implemented commands.

    Supports add/list/remove/clear and toggle enable state. Each stub maps a
    command type to a static JSON-serializable result or an error.
    """

    def __init__(self) -> None:
        self._enabled: bool = True
        self._stubs: Dict[str, Dict[str, Any]] = {}

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def toggle(self) -> bool:
        self._enabled = not self._enabled
        return self._enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def add(self, command_type: str, response: Dict[str, Any]) -> None:
        self._stubs[command_type] = response

    def remove(self, command_type: str) -> bool:
        return self._stubs.pop(command_type, None) is not None

    def clear(self) -> None:
        self._stubs.clear()

    def get(self, command_type: str) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return None
        return self._stubs.get(command_type)

    def list(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._stubs)


def discover_known_commands(server_source: str) -> List[str]:
    """
    Best-effort discovery of command names used with
    AbletonConnection.send_command in the server module, so users can
    tab-complete and explore.
    """
    pattern = (
        r"send_command\(\s*([\"\'])"
        r"((?:\\\1|(?!\1).)*)\1"
    )
    commands = set(re.findall(pattern, server_source))
    return sorted({cmd_name for _, cmd_name in commands})


def load_server_source() -> str:
    try:
        here = os.path.dirname(__file__)
        server_path = os.path.join(here, "server.py")
        with open(server_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


class AbletonDebugger(cmd.Cmd):
    intro = "Ableton MCP Debugger. Type help or ? to list commands."
    prompt = "ableton> "

    def __init__(
        self,
        host: str,
        port: int,
        stubs: StubRegistry,
        known_commands: List[str],
    ) -> None:
        super().__init__()
        self.connection = AbletonConnection(host=host, port=port)
        self.stubs = stubs
        self.known_commands = known_commands

    # Core operations
    def do_send(self, arg: str) -> None:
        """
        send <command_type> [JSON_PARAMS]

        Example:
          send get_session_info
          send set_tempo {"tempo": 120}
        """
        try:
            parts = shlex.split(arg)
            if not parts:
                print("Usage: send <command_type> [JSON_PARAMS]")
                return
            command_type = parts[0]
            params: Dict[str, Any] = {}
            if len(parts) > 1:
                params = json.loads(" ".join(parts[1:]))

            # Stub check
            stubbed = self.stubs.get(command_type)
            if stubbed is not None:
                print(json.dumps(stubbed, indent=2))
                return

            if not self.connection.connect():
                print("Error: failed to connect to Ableton server")
                return

            result = self.connection.send_command(command_type, params)
            print(json.dumps(result, indent=2))
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
        except Exception as e:
            print(f"Error: {e}")

    def complete_send(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> List[str]:
        # Offer known command names for the first argument
        args = shlex.split(line[:begidx])
        if len(args) <= 1:
            return [c for c in self.known_commands if c.startswith(text)]
        return []

    def do_quit(self, arg: str) -> bool:
        """Quit the debugger."""
        return True

    def do_exit(self, arg: str) -> bool:
        """Exit the debugger."""
        return True

    # Convenience wrappers for common commands
    def do_info(self, arg: str) -> None:
        """Show session info (alias for: send get_session_info)."""
        self.do_send("get_session_info")

    # Stub management commands
    def do_stub_add(self, arg: str) -> None:
        """
        stub_add <command_type> <JSON_RESPONSE>

        Adds a stubbed response for a command. When enabled, send will
        return this response instead of reaching the server.
        """
        try:
            parts = shlex.split(arg)
            if len(parts) < 2:
                print("Usage: stub_add <command_type> <JSON_RESPONSE>")
                return
            command_type = parts[0]
            response = json.loads(" ".join(parts[1:]))
            self.stubs.add(command_type, response)
            print(f"Stub added for '{command_type}'")
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")

    def do_stub_remove(self, arg: str) -> None:
        """stub_remove <command_type>"""
        command_type = arg.strip()
        if not command_type:
            print("Usage: stub_remove <command_type>")
            return
        removed = self.stubs.remove(command_type)
        if removed:
            print(f"Removed stub for '{command_type}'")
        else:
            print(f"No stub for '{command_type}'")

    def do_stub_list(self, arg: str) -> None:
        """List configured stubs."""
        stubs = self.stubs.list()
        print(json.dumps(stubs, indent=2))

    def do_stub_clear(self, arg: str) -> None:
        """Clear all stubs."""
        self.stubs.clear()
        print("All stubs cleared")

    def do_stub_toggle(self, arg: str) -> None:
        """Toggle stubs enabled/disabled."""
        state = self.stubs.toggle()
        print(f"Stubs {'enabled' if state else 'disabled'}")

    def do_stub_on(self, arg: str) -> None:
        self.stubs.enable()
        print("Stubs enabled")

    def do_stub_off(self, arg: str) -> None:
        self.stubs.disable()
        print("Stubs disabled")

    # Utility
    def do_commands(self, arg: str) -> None:
        """Show known command types discovered from server source."""
        for c in self.known_commands:
            print(c)


def run_repl(host: str, port: int) -> int:
    stubs = StubRegistry()
    known = discover_known_commands(load_server_source())
    AbletonDebugger(host, port, stubs, known).cmdloop()
    return 0


def run_once(
    host: str,
    port: int,
    command_type: str,
    params: Optional[str]
) -> int:
    stubs = StubRegistry()
    # Try stub first
    stubbed = stubs.get(command_type)
    if stubbed is not None:
        print(json.dumps(stubbed, indent=2))
        return 0

    conn = AbletonConnection(host=host, port=port)
    if not conn.connect():
        print("Error: failed to connect to Ableton server")
        return 2
    try:
        params_obj: Dict[str, Any] = {}
        if params:
            params_obj = json.loads(params)
        result = conn.send_command(command_type, params_obj)
        print(json.dumps(result, indent=2))
        return 0
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        return 3
    except Exception as e:
        print(f"Error: {e}")
        return 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ableton-mcp-debug",
        description="Interactive debugger for Ableton MCP server"
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Ableton MCP host"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Ableton MCP port"
    )

    sub = parser.add_subparsers(dest="mode")

    sub.add_parser("repl", help="Start interactive REPL")

    once = sub.add_parser(
        "send",
        help="Send a single command and print the result"
    )
    once.add_argument("command_type", help="Command type to send")
    once.add_argument("params", nargs="?", help="JSON-encoded params")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.mode == "send":
        return run_once(args.host, args.port, args.command_type, args.params)
    # default to REPL
    return run_repl(args.host, args.port)


if __name__ == "__main__":
    sys.exit(main())
