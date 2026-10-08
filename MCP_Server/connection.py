"""Client for the AbletonMCP Remote Script socket (newline-delimited JSON with request ids)."""
import itertools
import json
import logging
import os
import socket
import sys
import threading
import time

HOST = os.environ.get("ABLETON_MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("ABLETON_MCP_PORT", "9877"))
DEFAULT_TIMEOUT = 30.0
CONNECT_TIMEOUT = 3.0


def _client_name():
    """Who is asking, for the Remote Script's command journal: "ableton-mcp:4242", "pytest:4243", "python:4244"."""
    program = os.path.basename(sys.argv[0] or "") if sys.argv else ""
    if not program or program.startswith("-"):      # python -c / python - (stdin)
        program = "python"
    return os.environ.get("ABLETON_MCP_CLIENT") or "{0}:{1}".format(program, os.getpid())


CLIENT = _client_name()

logger = logging.getLogger("ableton_mcp.connection")

NOT_CONNECTED_HINT = (
    "Is Ableton Live running with the AbletonMCP control surface selected "
    "(Settings > Link, Tempo & MIDI > Control Surface)? Run `ableton-mcp doctor` to diagnose."
)


class AbletonError(Exception):
    """An error reported by the Remote Script, or a transport failure."""

    def __init__(self, code, message, hint=None):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.hint = hint

    def __str__(self):
        return "{0} ({1})".format(self.message, self.hint) if self.hint else self.message


class AbletonConnectionError(AbletonError):
    def __init__(self, message, hint=NOT_CONNECTED_HINT):
        AbletonError.__init__(self, "not_connected", message, hint)


class AbletonConnection(object):
    """One persistent socket to the Remote Script. Thread-safe; reconnects on demand."""

    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self._sock = None
        self._buffer = b""
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    # -- lifecycle -----------------------------------------------------------

    def connect(self):
        """Open the socket if needed. Returns True on success (kept for v1 callers and tests)."""
        try:
            with self._lock:
                self._ensure_open()
            return True
        except AbletonConnectionError as error:
            logger.warning("Could not connect to Ableton: %s", error)
            return False

    def _ensure_open(self):
        if self._sock is not None:
            return False
        try:
            sock = socket.create_connection((self.host, self.port), timeout=CONNECT_TIMEOUT)
        except OSError as error:
            raise AbletonConnectionError("Cannot reach Ableton Live at {0}:{1} ({2})".format(self.host, self.port, error))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock
        self._buffer = b""
        return True

    def close(self):
        sock, self._sock = self._sock, None
        self._buffer = b""
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    disconnect = close

    # -- requests ------------------------------------------------------------

    def send_command(self, command_type, params=None, timeout=None):
        """Send one command and return its result. Raises AbletonError on failure."""
        timeout = DEFAULT_TIMEOUT if timeout is None else timeout
        with self._lock:
            request_id = next(self._ids)
            request = {"id": request_id, "type": command_type, "params": params or {}, "client": CLIENT}
            payload = (json.dumps(request) + "\n").encode("utf-8")
            response = self._exchange(payload, request_id, timeout)
        if response.get("status") == "error":
            error = response.get("error") or {}
            raise AbletonError(error.get("code", "live_error"), error.get("message") or response.get("message") or "Unknown error", error.get("hint"))
        return response.get("result")

    def _exchange(self, payload, request_id, timeout):
        """Send and await the response. A socket that died while idle (e.g. Live restarted) never
        delivered the request, so that case is retried once on a fresh connection."""
        for attempt in (1, 2):
            fresh = self._ensure_open()
            try:
                self._sock.sendall(payload)
            except OSError as error:
                self.close()
                if fresh or attempt == 2:
                    raise AbletonConnectionError("Connection to Ableton Live failed: {0}".format(error))
                continue
            try:
                return self._read_response(request_id, timeout)
            except _StaleSocket:
                if fresh or attempt == 2:
                    raise AbletonConnectionError("Ableton Live closed the connection")
            except ValueError as error:
                self.close()
                raise AbletonError("live_error", "Invalid response from Ableton Live: {0}".format(error))
            except OSError as error:
                self.close()
                raise AbletonConnectionError("Connection to Ableton Live failed: {0}".format(error))

    def _read_response(self, request_id, timeout):
        deadline = time.time() + timeout
        received_any = False
        while True:
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                response = json.loads(line.decode("utf-8"))
                if response.get("id") in (request_id, None):
                    return response
                logger.debug("Discarding stale response %s", response.get("id"))
            remaining = deadline - time.time()
            if remaining <= 0:
                self.close()
                raise AbletonError("timeout", "Ableton Live did not answer within {0:.0f}s".format(timeout))
            self._sock.settimeout(remaining)
            try:
                chunk = self._sock.recv(65536)
            except socket.timeout:
                self.close()
                raise AbletonError("timeout", "Ableton Live did not answer within {0:.0f}s".format(timeout))
            except (ConnectionResetError, BrokenPipeError):
                self.close()
                if not received_any:
                    raise _StaleSocket()
                raise AbletonConnectionError("Connection to Ableton Live was reset")
            if not chunk:
                self.close()
                if not received_any:
                    raise _StaleSocket()
                raise AbletonConnectionError("Ableton Live closed the connection mid-response")
            received_any = True
            self._buffer += chunk
            if b"\n" not in self._buffer:
                # v1 Remote Scripts answer without a trailing newline.
                try:
                    response = json.loads(self._buffer.decode("utf-8"))
                except ValueError:
                    continue
                self._buffer = b""
                return response


class _StaleSocket(Exception):
    """The peer closed before answering: the request was not processed."""


_connection = None
_connection_lock = threading.Lock()


def get_connection():
    """The process-wide connection to Live (created lazily)."""
    global _connection
    with _connection_lock:
        if _connection is None:
            _connection = AbletonConnection()
        return _connection
