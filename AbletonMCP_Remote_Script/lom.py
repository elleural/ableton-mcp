"""Generic Live Object Model access by path: the escape hatch behind lom_get/lom_set/lom_call.

Paths follow Max for Live's style, with spaces, dots or brackets between tokens:
    "live_set tracks 0 mixer_device volume"
    "live_set.view.selected_track"
    "live_app view"
A path that does not start with live_set/song or live_app/app starts at the song.
"""
import re

from . import refs
from .errors import CommandError
from .values import jsonable

SONG_ROOTS = ("live_set", "song")
APP_ROOTS = ("live_app", "app", "application")

# Functions that open modal dialogs (blocking Live's main thread until a human clicks) or that break the
# one-undo-step-per-command contract.
BLOCKED_METHODS = {
    ("Application", "show_message"), ("Application", "show_on_the_fly_message"),
    ("Song", "begin_undo_step"), ("Song", "end_undo_step"),
}
# Path tokens that lead to Python control-surface objects (including AbletonMCP itself), not Live objects.
BLOCKED_PATH_TOKENS = {"control_surfaces"}

_LIST_CHILDREN = (
    "tracks", "return_tracks", "visible_tracks", "scenes", "cue_points", "clip_slots", "arrangement_clips",
    "take_lanes", "devices", "chains", "return_chains", "drum_pads", "visible_drum_pads", "parameters",
    "sends", "grooves", "control_surfaces",
)
_SINGLE_CHILDREN = (
    "master_track", "view", "mixer_device", "clip", "volume", "panning", "track_activator", "crossfader",
    "cue_volume", "song_tempo", "left_split_stereo", "right_split_stereo", "groove_pool", "tuning_system",
    "sample", "chain_selector", "browser", "selected_track", "selected_scene", "detail_clip",
    "highlighted_clip_slot", "selected_chain", "selected_parameter", "selected_device", "selected_drum_pad",
)


def tokens(path):
    if isinstance(path, (list, tuple)):
        return [str(token) for token in path]
    text = str(path or "").replace("[", " ").replace("]", " ")
    return [token for token in re.split(r"[\s.]+", text.strip()) if token]


def resolve(song, app, path):
    """Walk a path to a Live object (or value). Returns (object, normalized path string)."""
    parts = tokens(path)
    current, walked = song, ["live_set"]
    if parts and parts[0] in SONG_ROOTS:
        parts = parts[1:]
    elif parts and parts[0] in APP_ROOTS:
        current, walked, parts = app, ["live_app"], parts[1:]
    for part in parts:
        if re.match(r"^-?\d+$", part):
            try:
                items = list(current)
            except TypeError:
                raise CommandError("invalid_argument", "'{0}' is not a list, so it cannot be indexed with {1}".format(" ".join(walked), part))
            position = int(part)
            if not -len(items) <= position < len(items):
                raise CommandError("not_found", "Index {0} out of range at '{1}' ({2} items)".format(part, " ".join(walked), len(items)))
            current = items[position]
        else:
            if part.startswith("_"):
                raise CommandError("invalid_argument", "Private attribute '{0}' is not accessible".format(part))
            if part in BLOCKED_PATH_TOKENS:
                raise CommandError("unsupported", "'{0}' leads to control-surface scripts, which lom tools do not touch".format(part))
            descriptor = getattr(type(current), part, None)
            if descriptor is None and not hasattr(current, part):
                raise CommandError("not_found", "'{0}' has no property '{1}'. Use lom_describe to list what exists".format(" ".join(walked), part))
            if descriptor is not None and not isinstance(descriptor, property) and callable(descriptor):
                raise CommandError("invalid_argument", "'{0}' is a function; use lom_call".format(part))
            current = getattr(current, part)
        walked.append(part)
    return current, " ".join(walked)


_LIVE_MODULES = None


def _live_module_names():
    """Live's Boost.Python classes report bare module names ("Track", "Browser"), so collect them."""
    global _LIVE_MODULES
    if _LIVE_MODULES is None:
        try:
            import Live
            _LIVE_MODULES = set(name for name in dir(Live) if not name.startswith("_"))
        except ImportError:
            _LIVE_MODULES = set()
    return _LIVE_MODULES


def _is_sequence(value):
    if isinstance(value, (str, bytes, dict)):
        return False
    return hasattr(value, "__len__") and hasattr(value, "__getitem__")


def _is_live_object(value):
    if value is None or isinstance(value, (str, bytes, int, float, bool, dict, list, tuple)) or _is_sequence(value):
        return False
    module = type(value).__module__
    return hasattr(value, "canonical_parent") or module.startswith("Live") or module in _live_module_names()


def summarize(value, max_items=32):
    """Compact JSON for a property value: primitives as-is, objects and lists summarised."""
    if _is_sequence(value):
        items = list(value)
        if items and _is_live_object(items[0]):
            names = []
            for item in items[:max_items]:
                try:
                    names.append(str(item.name))
                except Exception:
                    names.append(type(item).__name__)
            return {"count": len(items), "items": names}
        return {"value": jsonable(items)}
    if _is_live_object(value):
        out = {"object": type(value).__name__}
        try:
            out["name"] = str(value.name)
        except Exception:
            pass
        return out
    return {"value": jsonable(value)}


def members(obj):
    """(properties, methods) of an object's class, inherited members included, listeners omitted."""
    cls = type(obj)
    properties, methods = {}, {}
    for name in dir(cls):
        if name.startswith("_"):
            continue
        attribute = getattr(cls, name, None)
        if isinstance(attribute, property):
            properties[name] = attribute
        elif callable(attribute) and not (name.endswith("_listener") or name.endswith("_has_listener")):
            methods[name] = attribute
    return properties, methods


def _doc(attribute):
    doc = getattr(attribute, "__doc__", None) or ""
    doc = doc.split("C++ signature :")[0]
    return " ".join(doc.split()) or None


def describe(obj, path, values=True):
    properties, methods = members(obj)
    out = {"path": path, "type": type(obj).__name__, "properties": {}, "methods": sorted(methods)}
    for name, descriptor in sorted(properties.items()):
        entry = {"settable": descriptor.fset is not None}
        if values:
            try:
                entry.update(summarize(getattr(obj, name)))
            except Exception as error:
                entry["error"] = str(error)
        out["properties"][name] = entry
    return out


def documentation(obj, path):
    properties, methods = members(obj)
    return {
        "path": path,
        "type": type(obj).__name__,
        "properties": dict((name, {"settable": descriptor.fset is not None, "doc": _doc(descriptor)}) for name, descriptor in sorted(properties.items())),
        "methods": dict((name, _doc(method)) for name, method in sorted(methods.items())),
    }


def object_path(song, app, obj, depth=0):
    """Best-effort path for a Live object, found by walking canonical_parent."""
    if depth > 12 or obj is None:
        return None
    if refs.same(obj, song):
        return "live_set"
    if app is not None and refs.same(obj, app):
        return "live_app"
    try:
        parent = obj.canonical_parent
    except Exception:
        parent = None
    if parent is None:
        return None
    parent_path = object_path(song, app, parent, depth + 1)
    if parent_path is None:
        return None
    for name in _LIST_CHILDREN:
        try:
            items = getattr(parent, name)
        except Exception:
            continue
        position = refs.index_of(items, obj)
        if position is not None:
            return "{0} {1} {2}".format(parent_path, name, position)
    for name in _SINGLE_CHILDREN:
        try:
            if refs.same(getattr(parent, name), obj):
                return "{0} {1}".format(parent_path, name)
        except Exception:
            continue
    return None


def convert_argument(song, app, value):
    """Turn {"path": "..."} arguments into Live objects; leave everything else untouched."""
    if isinstance(value, dict) and set(value) == {"path"}:
        return resolve(song, app, value["path"])[0]
    if isinstance(value, list):
        return [convert_argument(song, app, item) for item in value]
    return value


def result_out(song, app, value):
    """JSON for a call result, with the path of any Live object returned."""
    if _is_live_object(value) and not _is_sequence(value):
        out = summarize(value)
        out["path"] = object_path(song, app, value)
        return out
    return jsonable(value)
