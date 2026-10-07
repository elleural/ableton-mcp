"""Command-line debugger for the Remote Script (`ableton-mcp-debug`).

    ableton-mcp-debug send ping
    ableton-mcp-debug send lom_get '{"path": "live_set", "properties": ["tempo"]}'
    ableton-mcp-debug repl
"""
import argparse
import cmd
import json
import shlex
import sys

from .connection import HOST, PORT, AbletonConnection, AbletonError


def _print(result):
    print(json.dumps(result, indent=2, ensure_ascii=False))


class AbletonDebugger(cmd.Cmd):
    intro = "AbletonMCP debugger. Type help or ? to list commands."
    prompt = "ableton> "

    def __init__(self, host, port):
        cmd.Cmd.__init__(self)
        self.connection = AbletonConnection(host=host, port=port)
        self._commands = None

    def _send(self, command_type, params=None):
        try:
            _print(self.connection.send_command(command_type, params or {}))
        except AbletonError as error:
            print("Error [{0}]: {1}".format(error.code, error))

    def do_send(self, arg):
        """send <command> [JSON params]   e.g. send set_song {"tempo": 120}"""
        parts = arg.split(None, 1)
        if not parts:
            print("Usage: send <command> [JSON params]")
            return
        try:
            params = json.loads(parts[1]) if len(parts) > 1 else {}
        except ValueError as error:
            print("Invalid JSON: {0}".format(error))
            return
        self._send(parts[0], params)

    def complete_send(self, text, line, begidx, endidx):
        if len(shlex.split(line[:begidx])) > 1:
            return []
        if self._commands is None:
            try:
                self._commands = sorted(self.connection.send_command("get_commands")["commands"])
            except AbletonError:
                self._commands = []
        return [name for name in self._commands if name.startswith(text)]

    def do_commands(self, arg):
        """List every command the Remote Script registers, with its parameters."""
        self._send("get_commands")

    def do_ping(self, arg):
        """Check the connection and show versions."""
        self._send("ping")

    def do_reload(self, arg):
        """Hot-reload the Remote Script (reload full to include the shell module)."""
        self._send("reload_remote_script", {"full": arg.strip() == "full"})

    def do_quit(self, arg):
        """Quit the debugger."""
        return True

    do_exit = do_quit


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="ableton-mcp-debug", description="Talk to the AbletonMCP Remote Script directly")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    sub = parser.add_subparsers(dest="mode")
    sub.add_parser("repl", help="Interactive session")
    once = sub.add_parser("send", help="Send one command and print the result")
    once.add_argument("command_type")
    once.add_argument("params", nargs="?", help="JSON-encoded parameters")
    once.add_argument("--timeout", type=float, default=None)
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    if args.mode != "send":
        AbletonDebugger(args.host, args.port).cmdloop()
        return 0
    try:
        params = json.loads(args.params) if args.params else {}
    except ValueError as error:
        print("Invalid JSON: {0}".format(error))
        return 3
    try:
        _print(AbletonConnection(args.host, args.port).send_command(args.command_type, params, timeout=args.timeout))
        return 0
    except AbletonError as error:
        print("Error [{0}]: {1}".format(error.code, error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
