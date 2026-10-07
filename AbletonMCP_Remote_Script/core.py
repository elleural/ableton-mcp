"""Command registry and dispatcher (reloadable).

Handlers register with @command and receive a Context plus keyword parameters:

    @command("set_mixer")
    def set_mixer(ctx, track, volume_db=None, pan=None):
        ...
        return {...}  # JSON-safe result

Every handler runs on Live's main thread. Mutating handlers run inside one Live undo step.
Raise errors.CommandError for problems the caller can fix.
"""
import importlib
import inspect
import time
import traceback

try:
    import queue
except ImportError:  # pragma: no cover - Live 12 runs Python 3
    import Queue as queue

from .errors import CommandError

SCRIPT_VERSION = "2.0.0"
PROTOCOL_VERSION = 2

COMMANDS = {}
TICKERS = []


class CommandSpec(object):
    def __init__(self, name, func, readonly, timeout, undo):
        self.name = name
        self.func = func
        self.readonly = readonly
        self.timeout = timeout
        self.undo = undo
        self.signature = inspect.signature(func)
        parameters = list(self.signature.parameters.values())[1:]
        self.accepts_any = any(item.kind == item.VAR_KEYWORD for item in parameters)
        self.params = [item.name for item in parameters if item.kind != item.VAR_KEYWORD]
        self.required = [item.name for item in parameters if item.default is item.empty and item.kind != item.VAR_KEYWORD]

    def describe(self):
        return {"params": self.params, "required": self.required, "readonly": self.readonly, "timeout": self.timeout}


def command(name=None, readonly=False, timeout=10.0, undo=None):
    """Register a handler ``func(ctx, **params)`` under ``name`` (default: the function name).

    readonly: the handler never changes the Live Set (no undo step is opened).
    timeout: seconds the caller waits for the main thread to finish the handler.
    undo: override whether the handler runs inside one undo step (default: not readonly).
    """
    def decorator(func):
        command_name = name or func.__name__
        if command_name in COMMANDS:
            raise ValueError("Duplicate AbletonMCP command: " + command_name)
        COMMANDS[command_name] = CommandSpec(command_name, func, readonly, timeout, (not readonly) if undo is None else undo)
        return func
    return decorator


def ticker(func):
    """Register ``func(ctx)`` to run on Live's main thread at every display tick (about 10 Hz)."""
    TICKERS.append(func)
    return func


class Context(object):
    """What a handler gets: Live's song and application, logging, and reload-safe state."""

    def __init__(self, control_surface):
        self.cs = control_surface

    @property
    def song(self):
        return self.cs.song()

    @property
    def app(self):
        return self.cs.application()

    @property
    def state(self):
        """A dict stored on the control surface, so it survives reload_remote_script."""
        return self.cs.mcp_state

    def log(self, message):
        self.cs.log_message("AbletonMCP: " + str(message))

    def show_message(self, message):
        self.cs.show_message(str(message))


# ---------------------------------------------------------------------------
# Dispatch (socket thread) and execution (main thread)
# ---------------------------------------------------------------------------


def _error_response(error):
    return {"status": "error", "error": error.to_dict(), "message": error.message}


def validate(spec, params):
    if not isinstance(params, dict):
        raise CommandError("invalid_argument", "params must be an object")
    try:
        spec.signature.bind(None, **params)
    except TypeError as error:
        raise CommandError(
            "invalid_argument",
            "{0}: {1}. Parameters: {2} (required: {3})".format(spec.name, error, ", ".join(spec.params) or "none", ", ".join(spec.required) or "none"),
        )


def run_on_main_thread(cs, func, timeout):
    """Run func on Live's main thread and wait for its result.

    A task whose caller has already timed out is skipped rather than run late.
    """
    results = queue.Queue(maxsize=1)
    deadline = time.time() + timeout

    def task():
        if time.time() > deadline:
            return
        try:
            results.put(("ok", func()))
        except Exception as error:  # Raised back on the socket thread below.
            results.put(("error", error, traceback.format_exc()))

    cs.submit(task)
    try:
        outcome = results.get(timeout=timeout)
    except queue.Empty:
        raise CommandError("timeout", "Live did not finish within {0:.0f}s (main thread busy, or a modal dialog is open)".format(timeout))
    if outcome[0] == "error":
        error = outcome[1]
        if not isinstance(error, CommandError):
            cs.log_message("AbletonMCP handler error:\n" + outcome[2])
        raise error
    return outcome[1]


def execute(cs, spec, params):
    """Run a validated command on the current (main) thread, as one undo step if it mutates."""
    ctx = Context(cs)
    if not spec.undo:
        return spec.func(ctx, **params)
    song = ctx.song
    song.begin_undo_step()
    try:
        return spec.func(ctx, **params)
    finally:
        song.end_undo_step()


def _run_batch(cs, params):
    commands = params.get("commands") or []
    stop_on_error = params.get("stop_on_error", True)
    results = []
    song = cs.song()
    song.begin_undo_step()
    try:
        for item in commands:
            name = item.get("type")
            spec = COMMANDS.get(name)
            try:
                if spec is None:
                    raise CommandError("not_found", "Unknown command: {0}".format(name))
                item_params = item.get("params") or {}
                validate(spec, item_params)
                results.append({"status": "success", "result": spec.func(Context(cs), **item_params)})
            except CommandError as error:
                results.append(_error_response(error))
                if stop_on_error:
                    break
            except Exception as error:
                cs.log_message("AbletonMCP batch error:\n" + traceback.format_exc())
                results.append(_error_response(CommandError("live_error", str(error))))
                if stop_on_error:
                    break
    finally:
        song.end_undo_step()
    return {"results": results}


def dispatch(cs, request):
    """Handle one request (called on a socket thread). Always returns a response dict."""
    command_type = request.get("type", "")
    params = request.get("params") or {}
    try:
        if command_type == "batch":
            result = run_on_main_thread(cs, lambda: _run_batch(cs, params), float(params.get("timeout", 30.0)))
        else:
            spec = COMMANDS.get(command_type)
            if spec is None:
                raise CommandError("not_found", "Unknown command: {0}".format(command_type),
                                   hint="get_commands lists every command; the MCP server and Remote Script may be different versions")
            validate(spec, params)
            result = run_on_main_thread(cs, lambda: execute(cs, spec, params), spec.timeout)
        return {"status": "success", "result": result}
    except CommandError as error:
        return _error_response(error)
    except Exception as error:
        cs.log_message("AbletonMCP dispatch error:\n" + traceback.format_exc())
        return _error_response(CommandError("live_error", str(error) or error.__class__.__name__))


def tick(cs):
    """Called by the shell on every display tick (main thread)."""
    if not TICKERS:
        return
    ctx = Context(cs)
    for func in list(TICKERS):
        try:
            func(ctx)
        except Exception:
            cs.log_message("AbletonMCP ticker error:\n" + traceback.format_exc())


def load_handlers():
    """Import every handler module, isolating failures so one broken module cannot block the rest."""
    from . import handlers
    loaded, failed = [], {}
    for module_name in handlers.MODULES:
        try:
            importlib.import_module(__package__ + ".handlers." + module_name)
            loaded.append(module_name)
        except Exception:
            failed[module_name] = traceback.format_exc(limit=6)
    return {"loaded": loaded, "failed": failed, "command_count": len(COMMANDS)}
