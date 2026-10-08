"""The Spotify desktop app, driven by AppleScript (PRD 11.2 `ref_play`).

Only playback control and track facts: play a track (optionally from a position), seek, pause, and read
the state, position, volume and current track. The audio itself is never touched here; ears.meter
measures it from the interface's loopback while it plays. macOS asks once for permission to control
Spotify (System Settings > Privacy & Security > Automation).
"""
import re
import subprocess
import time

TIMEOUT = 20.0
TRACK_RE = re.compile(r"^(?:spotify:track:|(?:https?://)?open\.spotify\.com/(?:intl-[a-z-]+/)?track/)?([A-Za-z0-9]{22})(?:[?#].*)?$")


class PlayerError(Exception):
    """Spotify cannot be controlled (not installed, not permitted, not answering)."""


def track_uri(value):
    """spotify:track:<id> from a URI, an open.spotify.com link or a bare 22-character id."""
    match = TRACK_RE.match(str(value or "").strip())
    if not match:
        raise PlayerError("Not a Spotify track: {0!r} (use spotify:track:<id> or an open.spotify.com/track link)".format(value))
    return "spotify:track:" + match.group(1)


def _number(text):
    try:
        return float(str(text).strip().replace(",", "."))   # AppleScript writes decimals in the system locale
    except ValueError:
        return None


class Spotify(object):
    """The Spotify desktop app through osascript."""

    def __init__(self, timeout=TIMEOUT, runner=None):
        self.timeout = float(timeout)
        self._run = runner or self._osascript

    def _osascript(self, script):
        try:
            done = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=self.timeout)
        except FileNotFoundError:
            raise PlayerError("osascript is missing: the Spotify player needs macOS")
        except subprocess.TimeoutExpired:
            raise PlayerError("Spotify did not answer within {0:g} s. macOS may be showing a prompt to let this app control "
                              "Spotify: allow it (System Settings > Privacy & Security > Automation)".format(self.timeout))
        if done.returncode != 0:
            message = (done.stderr or done.stdout).strip()
            if "-1743" in message or "Not authorized" in message or "not allowed" in message:
                raise PlayerError("This app may not control Spotify: allow it in System Settings > Privacy & Security > "
                                  "Automation (Spotify)")
            if "-1728" in message or "Can’t get application" in message or "Can't get application" in message:
                raise PlayerError("The Spotify desktop app is not installed")
            raise PlayerError("Spotify: {0}".format(message or "osascript failed"))
        return done.stdout.strip()

    def running(self):
        """True when the Spotify app is open, checked without starting it (unknown counts as open)."""
        try:
            return subprocess.run(["pgrep", "-x", "Spotify"], capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return True

    def _tell(self, body):
        return self._run('tell application "Spotify"\n{0}\nend tell'.format(body))

    def status(self):
        """{"state": playing|paused|stopped, "volume", "position" (s), "track": {uri, name, artist, album, duration (s)} or None}."""
        text = self._tell(
            'set s to player state as string\n'
            'set out to s & linefeed & (sound volume as string) & linefeed & (player position as string)\n'
            'if s is not "stopped" then\n'
            '  set t to current track\n'
            '  set out to out & linefeed & (id of t) & linefeed & (name of t) & linefeed & (artist of t) & linefeed & '
            '(album of t) & linefeed & ((duration of t) as string)\n'
            'end if\n'
            'return out')
        lines = text.split("\n")
        out = {"state": lines[0].strip() if lines else "stopped",
               "volume": _number(lines[1]) if len(lines) > 1 else None,
               "position": _number(lines[2]) if len(lines) > 2 else None, "track": None}
        if len(lines) >= 8:
            duration = _number(lines[7])
            out["track"] = {"uri": lines[3].strip(), "name": lines[4].strip(), "artist": lines[5].strip(),
                            "album": lines[6].strip(), "duration": round(duration / 1000.0, 3) if duration else None}
        return out

    def play(self, uri, position=None):
        """Start a track (optionally at `position` seconds) and wait until Spotify reports it playing."""
        uri = track_uri(uri)
        body = 'play track "{0}"'.format(uri)
        if position:
            body += "\ndelay 0.2\nset player position to {0:.3f}".format(float(position))
        self._tell(body)
        deadline = time.time() + 10.0
        status = None
        while time.time() < deadline:
            status = self.status()
            if status["state"] == "playing" and status["track"] and status["track"]["uri"] == uri:
                return status
            time.sleep(0.2)
        raise PlayerError("Spotify did not start {0} (state {1})".format(uri, status and status["state"]))

    def pause(self):
        self._tell("pause")
        return self.status()

    def resume(self):
        """Continue the current track from where it is paused."""
        self._tell("play")
        return self.status()

    def seek(self, position):
        self._tell("set player position to {0:.3f}".format(float(position)))
        return self.status()
