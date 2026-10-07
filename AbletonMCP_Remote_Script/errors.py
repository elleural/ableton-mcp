"""Structured errors returned to the MCP server.

Handlers raise CommandError for anything the caller can fix; the dispatcher turns it into
{"status": "error", "error": {"code", "message", "hint"}}. Unexpected exceptions become
code "live_error".
"""

CODES = ("not_found", "invalid_argument", "unsupported", "live_error", "timeout", "busy")


class CommandError(Exception):
    def __init__(self, code, message, hint=None):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.hint = hint

    def to_dict(self):
        error = {"code": self.code, "message": self.message}
        if self.hint:
            error["hint"] = self.hint
        return error


def not_found(what, ref, options=None, limit=40):
    """CommandError for an unresolvable reference, listing what does exist."""
    message = "{0} {1!r} not found.".format(what, ref)
    if options is not None:
        options = list(options)
        shown = ", ".join(str(option) for option in options[:limit])
        if len(options) > limit:
            shown += ", ... ({0} total)".format(len(options))
        message += " Available: {0}".format(shown or "(none)")
    return CommandError("not_found", message)
