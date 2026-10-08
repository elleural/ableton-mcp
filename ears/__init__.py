"""ears: the listening loop's analysis package (docs/listening-loop-prd.md).

A composing agent cannot hear, so ears turns what it made into numbers, images and differences:
exact checks on the notes, measurements on the audio, and comparisons between takes, against the spec
and against references. It is standalone: it imports nothing from the MCP server or the Remote Script,
runs without Live, and its CLI (`ears`) doubles as the soundtrack's acceptance script.
"""
import os
import re
from pathlib import Path

__version__ = "0.1.0"

DEFAULT_ROOT = Path("~/Music/AbletonMCP/Ears").expanduser()


def safe_name(text, fallback="untitled"):
    """A file-system friendly name: letters, digits, dot, dash and underscore."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text or "").strip()).strip("._")
    return name or fallback


def home(set_path=None, set_name=None):
    """Where takes, references, calibration and the ledger live (PRD section 4).

    EARS_HOME wins; a saved Live Set keeps them beside itself in `<set folder>/ears`; an unsaved set
    uses ~/Music/AbletonMCP/Ears/<set name or "untitled">.
    """
    override = os.environ.get("EARS_HOME")
    if override:
        return Path(override).expanduser()
    if set_path:
        return Path(set_path).expanduser().resolve().parent / "ears"
    return DEFAULT_ROOT / safe_name(set_name)


def left_behind(set_path=None, set_name=None):
    """The untitled home whose takes a set left behind when it was first saved, or None.

    An unsaved set keeps its takes in ~/Music/AbletonMCP/Ears/untitled; saving moves the home beside the set,
    so those takes stay where they were until someone moves the folder.
    """
    if os.environ.get("EARS_HOME") or not set_path:
        return None
    current = home(set_path, set_name)
    untitled = DEFAULT_ROOT / safe_name(None)
    if (current / "ledger.jsonl").is_file() or not (untitled / "ledger.jsonl").is_file():
        return None
    return untitled
