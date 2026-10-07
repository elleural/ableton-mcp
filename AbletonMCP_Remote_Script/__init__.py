"""AbletonMCP Remote Script: lets the AbletonMCP server control Ableton Live.

This file is deliberately small and stable. It owns the ControlSurface, the TCP server and the
main-thread task queue. Command handling lives in reloadable modules (core.py, handlers/), which
the ``reload_remote_script`` command swaps in without restarting Live.

Wire protocol: newline-delimited JSON on 127.0.0.1:9877.
  request:  {"id": 1, "type": "<command>", "params": {...}}
  response: {"id": 1, "status": "success", "result": ...}
            {"id": 1, "status": "error", "error": {"code", "message", "hint"}, "message": ...}
Requests without a trailing newline (v1 clients) are also accepted.
"""
from __future__ import absolute_import, print_function, unicode_literals

import importlib
import json
import socket
import sys
import threading
import traceback

try:
    import queue
except ImportError:  # pragma: no cover - Live 12 runs Python 3
    import Queue as queue

from _Framework.ControlSurface import ControlSurface

HOST = "127.0.0.1"
DEFAULT_PORT = 9877
SCRIPT_VERSION = "2.0.0-shell"
RELOAD_TIMEOUT = 30.0


def create_instance(c_instance):
    """Entry point Live calls when the control surface is selected."""
    return AbletonMCP(c_instance)


class AbletonMCP(ControlSurface):
    """Control surface hosting the AbletonMCP socket server."""

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self.server = None
        self.server_thread = None
        self.client_threads = []
        self.running = False
        self._ensure_runtime()
        self.core = None
        self.core_report = None
        self.load_core()
        self.start_server()
        self.show_message("AbletonMCP: listening on port {0}".format(DEFAULT_PORT))

    def _ensure_runtime(self):
        """State that must exist on the instance and survive code reloads."""
        # Note: ControlSurface already uses "_tasks" (a TaskGroup); never reuse that name.
        if not isinstance(getattr(self, "_mcp_tasks", None), queue.Queue):
            self._mcp_tasks = queue.Queue()
        if not hasattr(self, "mcp_state"):
            self.mcp_state = {}

    def _after_reload(self):
        """Run when an older shell hot-swaps this live instance onto this class."""
        self._ensure_runtime()
        if not hasattr(self, "core"):
            self.core = None
        self.load_core()

    # ------------------------------------------------------------------
    # Reloadable core
    # ------------------------------------------------------------------

    def load_core(self):
        """(Re)import core and handler modules. On failure, keep running the previous code."""
        package = __name__
        package_module = sys.modules[package]
        previous = dict((name, module) for name, module in sys.modules.items() if name.startswith(package + "."))
        for name in previous:
            del sys.modules[name]
        # A submodule is also an attribute of its package, and `from . import x` returns that
        # attribute when present, so strip every submodule attribute too (even ones no longer in
        # sys.modules) or reloaded code would keep using stale modules.
        previous_attributes = {}
        for child, value in list(vars(package_module).items()):
            if getattr(value, "__name__", "").startswith(package + ".") and hasattr(value, "__file__"):
                previous_attributes[child] = value
                delattr(package_module, child)
        try:
            core = importlib.import_module(package + ".core")
            report = core.load_handlers()
        except Exception:
            sys.modules.update(previous)
            for child, module in previous_attributes.items():
                setattr(package_module, child, module)
            error = traceback.format_exc()
            self.log_message("AbletonMCP: core load failed:\n" + error)
            failure = {"ok": False, "error": error, "kept_previous_core": getattr(self, "core", None) is not None}
            if getattr(self, "core", None) is None:
                self.core_report = failure
            return failure
        self.core = core
        report["ok"] = True
        report["script_version"] = core.SCRIPT_VERSION
        if report.get("failed"):
            self.log_message("AbletonMCP: handler modules failed to load: " + ", ".join(report["failed"]))
        self.core_report = report
        return report

    def _full_reload(self):
        """Reload this shell module too, rebinding the running instance to the new class."""
        package = importlib.reload(sys.modules[__name__])
        self.__class__ = package.AbletonMCP
        self._after_reload()
        return self.core_report

    # ------------------------------------------------------------------
    # Main-thread execution
    # ------------------------------------------------------------------

    def submit(self, task):
        """Queue a callable to run on Live's main thread at the next display tick."""
        self._mcp_tasks.put(task)

    def update_display(self):
        """Live calls this on the main thread about ten times a second."""
        ControlSurface.update_display(self)
        tasks = getattr(self, "_mcp_tasks", None)
        while tasks is not None:
            try:
                task = tasks.get_nowait()
            except queue.Empty:
                break
            try:
                task()
            except Exception:
                self.log_message("AbletonMCP: task error:\n" + traceback.format_exc())
        core = getattr(self, "core", None)
        if core is not None:
            try:
                core.tick(self)
            except Exception:
                self.log_message("AbletonMCP: tick error:\n" + traceback.format_exc())

    # ------------------------------------------------------------------
    # Socket server
    # ------------------------------------------------------------------

    def start_server(self):
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((HOST, DEFAULT_PORT))
            self.server.listen(5)
            self.running = True
            self.server_thread = threading.Thread(target=self._server_thread)
            self.server_thread.daemon = True
            self.server_thread.start()
            self.log_message("AbletonMCP: server listening on {0}:{1}".format(HOST, DEFAULT_PORT))
        except Exception as error:
            self.log_message("AbletonMCP: could not start server: " + str(error))
            self.show_message("AbletonMCP: could not start server - " + str(error))

    def _server_thread(self):
        self.server.settimeout(1.0)
        while self.running:
            try:
                client, address = self.server.accept()
            except socket.timeout:
                continue
            except Exception as error:
                if self.running:
                    self.log_message("AbletonMCP: accept error: " + str(error))
                continue
            client_thread = threading.Thread(target=self._handle_client, args=(client,))
            client_thread.daemon = True
            client_thread.start()
            self.client_threads = [thread for thread in self.client_threads if thread.is_alive()] + [client_thread]

    def _handle_client(self, client):
        client.settimeout(None)
        decoder = json.JSONDecoder()
        buffer = ""
        try:
            while self.running:
                data = client.recv(65536)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while True:
                    buffer = buffer.lstrip()
                    if not buffer:
                        break
                    try:
                        request, end = decoder.raw_decode(buffer)
                    except ValueError:
                        if "\n" not in buffer:
                            break  # Incomplete request: wait for more data.
                        _, buffer = buffer.split("\n", 1)
                        self._send(client, self._error(None, "invalid_argument", "Malformed JSON request"))
                        continue
                    buffer = buffer[end:]
                    self._send(client, self._dispatch(request))
        except Exception as error:
            if self.running:
                self.log_message("AbletonMCP: client error: " + str(error))
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _send(self, client, response):
        client.sendall((json.dumps(response) + "\n").encode("utf-8"))

    @staticmethod
    def _error(request_id, code, message):
        response = {"status": "error", "error": {"code": code, "message": message}, "message": message}
        if request_id is not None:
            response["id"] = request_id
        return response

    def _dispatch(self, request):
        if not isinstance(request, dict):
            return self._error(None, "invalid_argument", "A request must be a JSON object")
        request_id = request.get("id")
        if request.get("type") == "reload_remote_script":
            try:
                response = self._reload(request.get("params") or {})
            except Exception:
                response = self._error(None, "live_error", traceback.format_exc())
        else:
            core = getattr(self, "core", None)
            if core is None:
                error = (getattr(self, "core_report", None) or {}).get("error", "unknown error")
                return self._error(request_id, "live_error", "AbletonMCP core is not loaded; fix it and call reload_remote_script.\n" + error)
            try:
                response = core.dispatch(self, request)
            except Exception as error:
                self.log_message("AbletonMCP: dispatch failed:\n" + traceback.format_exc())
                response = self._error(None, "live_error", str(error))
        if request_id is not None:
            response["id"] = request_id
        return response

    def _reload(self, params):
        """Reload code on the main thread so no command runs while modules are swapped."""
        outcome = queue.Queue(maxsize=1)

        def task():
            try:
                outcome.put(("ok", self._full_reload() if params.get("full") else self.load_core()))
            except Exception:
                outcome.put(("error", traceback.format_exc()))

        try:
            self.submit(task)
        except Exception:
            task()  # The task queue itself is broken: reload in place so the fix can load.
        try:
            status, value = outcome.get(timeout=RELOAD_TIMEOUT)
        except queue.Empty:
            return self._error(None, "timeout", "Reload did not run within {0:.0f}s".format(RELOAD_TIMEOUT))
        if status == "error":
            return self._error(None, "live_error", value)
        if not value.get("ok"):
            return self._error(None, "live_error", "Reload failed; previous code still running:\n" + value.get("error", ""))
        return {"status": "success", "result": value}

    def disconnect(self):
        """Called when Live quits or the control surface is deselected."""
        self.running = False
        if self.server:
            try:
                self.server.close()
            except Exception:
                pass
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(1.0)
        ControlSurface.disconnect(self)
