"""WS-D: browser search, browse and loading (docs/PRD.md section 7.4).

Browser trees can be large (Samples alone can hold thousands of files), so searching uses an index
that is built incrementally: a search scans breadth-first for at most SEARCH_BUDGET seconds of main-
thread time, a ticker keeps scanning in short slices until every requested category is indexed, and
results say "truncated" while the index is incomplete. The index lives in a module-level dict.

The index follows the browser as it changes (packs installed while Live runs, new user files): a
Browser.full_refresh listener schedules a background rescan of every indexed category, and a TTL
(shorter for categories the user changes: samples, clips, user library, project) backs it up. While a
rescan runs, searches serve the last complete index merged with what the rescan found so far, and
search_browser(refresh=True) forces a rescan and waits for it (within the time budget).

Paths are "<category>/<folder>/.../<item>" with category keys such as "instruments", "sounds" or
"user_library". URIs are Live's own identifiers ("query:Synths#Operator:Bass:FileId_6972").
"""
import collections
import time

from .. import refs
from ..core import command, ticker
from ..errors import CommandError, not_found

# Search priority order: devices first, then presets and kits, then files and folders.
CATEGORIES = (
    "instruments", "audio_effects", "midi_effects", "sounds", "drums", "plugins", "max_for_live",
    "user_library", "clips", "samples", "packs", "current_project", "user_folders",
)
CATEGORY_ALIASES = {
    "instrument": "instruments", "synths": "instruments", "audio_effect": "audio_effects", "effects": "audio_effects",
    "audio effects": "audio_effects", "midi_effect": "midi_effects", "midi effects": "midi_effects", "sound": "sounds",
    "presets": "sounds", "drum": "drums", "kits": "drums", "plugin": "plugins", "plug-ins": "plugins", "vst": "plugins",
    "max": "max_for_live", "m4l": "max_for_live", "max for live": "max_for_live", "user library": "user_library",
    "user": "user_library", "clip": "clips", "sample": "samples", "pack": "packs", "project": "current_project",
    "current project": "current_project", "folders": "user_folders", "user folders": "user_folders",
}
VOLATILE = frozenset(("samples", "clips", "user_library", "current_project", "user_folders"))
STATIC_TTL = 300.0       # backstop for changes the full_refresh listener does not report
VOLATILE_TTL = 60.0
SEARCH_BUDGET = 1.5      # seconds of scanning a search may spend on the main thread
TICK_BUDGET = 0.02       # seconds per display tick for the background scan
MAX_DEPTH = 10
AUDIO_EXTENSIONS = frozenset(("wav", "aif", "aiff", "flac", "mp3", "ogg", "m4a", "aac", "wave"))
KIND_BY_EXTENSION = {"adv": "preset", "adg": "rack_preset", "amxd": "max_device", "alc": "clip", "als": "set", "agr": "groove", "ask": "skin", "alp": "pack"}

_INDEX = {}  # category -> _Scan (the module-level cache; rebuilt when the module reloads)


def _compact(text):
    return "".join(character for character in str(text).lower() if character.isalnum())


def category_key(value):
    """Canonical category for a name or alias ("Plug-Ins" -> "plugins", "m4l" -> "max_for_live")."""
    key = _compact(value or "all")
    if key == "all":
        return "all"
    for category in CATEGORIES:
        if _compact(category) == key:
            return category
    for alias, category in CATEGORY_ALIASES.items():
        if _compact(alias) == key:
            return category
    raise not_found("Browser category", value, ("all",) + CATEGORIES)


def category_roots(browser, category):
    """[(path, item)] roots of a category (user_folders has several)."""
    if category == "user_folders":
        return [("user_folders/" + item.name, item) for item in browser.user_folders]
    return [(category, getattr(browser, category))]


def stem(name):
    """Name without a file extension ('Acid Bass.adv' -> 'Acid Bass')."""
    text = str(name)
    head, dot, tail = text.rpartition(".")
    if dot and head and 1 <= len(tail) <= 5 and tail.isalnum() and not tail.isdigit():
        return head
    return text


def kind_of(name, is_folder, is_device, is_loadable, category):
    if is_device:
        return "plugin" if category == "plugins" else "device"
    tail = str(name).rpartition(".")[2].lower() if "." in str(name) else ""
    if tail in AUDIO_EXTENSIONS:
        return "sample"
    if tail in KIND_BY_EXTENSION:
        return KIND_BY_EXTENSION[tail]
    if is_folder or not is_loadable:
        return "folder"
    return "item"


def file_id(uri):
    """'FileId_7286' for file URIs, so one file found through several categories is listed once."""
    marker = str(uri).rfind("FileId_")
    return str(uri)[marker:] if marker >= 0 else None


# ---------------------------------------------------------------------------
# Incremental index
# ---------------------------------------------------------------------------

_NAME, _LOWER, _PATH, _URI, _KIND, _LOADABLE, _DEVICE, _DEPTH = range(8)


class _Folder(object):
    __slots__ = ("item", "path", "depth", "children", "position")

    def __init__(self, item, path, depth):
        self.item, self.path, self.depth = item, path, depth
        self.children, self.position = None, 0


class _Scan(object):
    """Breadth-first scan of one category; entries are tuples indexed by the _NAME.. constants."""

    def __init__(self, category, roots):
        self.category = category
        self.entries = []
        self.queue = collections.deque(_Folder(item, path, 0) for path, item in roots)
        self.started = time.time()
        self.finished = None
        self.busy_seconds = 0.0
        self.error = None

    @property
    def complete(self):
        return self.finished is not None

    def advance(self, budget):
        """Scan for about `budget` seconds (at least one item per call, so slow folders still progress).
        Returns True when the category is fully indexed."""
        start = time.time()
        deadline = start + budget
        progressed = False
        try:
            while self.queue and (not progressed or time.time() < deadline):
                folder = self.queue[0]
                if folder.children is None:
                    folder.children = list(folder.item.children)
                children = folder.children
                while folder.position < len(children) and (not progressed or time.time() < deadline):
                    child = children[folder.position]
                    folder.position += 1
                    self._add(child, folder)
                    progressed = True
                if folder.position >= len(children):
                    self.queue.popleft()
                    progressed = True
        except Exception as error:  # A browser refresh can invalidate items mid-scan: stop and report.
            self.error = str(error) or error.__class__.__name__
            self.queue.clear()
        self.busy_seconds += time.time() - start
        if not self.queue and self.finished is None:
            self.finished = time.time()
        return self.complete

    def _add(self, child, folder):
        name = child.name
        is_folder = bool(child.is_folder)
        is_device = bool(child.is_device)
        loadable = bool(child.is_loadable)
        path = folder.path + "/" + name
        depth = folder.depth + 1
        kind = kind_of(name, is_folder, is_device, loadable, self.category)
        self.entries.append((name, stem(name).lower(), path, child.uri, kind, loadable, is_device, depth))
        if (is_folder or is_device or not loadable) and depth < MAX_DEPTH:
            self.queue.append(_Folder(child, path, depth))

    def status(self):
        out = {
            "complete": self.complete, "items": len(self.entries), "pending_folders": len(self.queue),
            "scan_seconds": round(self.busy_seconds, 3),
        }
        if self.complete:
            out["wall_seconds"] = round(self.finished - self.started, 3)
            out["age_seconds"] = round(time.time() - self.finished, 1)
        if self.error:
            out["error"] = self.error
        return out


class _CategoryIndex(object):
    """The current scan of a category, plus the last complete one while a rescan runs."""

    def __init__(self):
        self.current = None
        self.previous = None

    def restart(self, browser, category):
        if self.current is not None and self.current.complete and self.current.error is None:
            self.previous = self.current
        self.current = _Scan(category, category_roots(browser, category))

    def entries(self):
        if self.current is not None and self.current.complete and self.current.error is None:
            return self.current.entries
        if self.previous is not None:  # Rescanning: the last complete index plus what is new so far.
            return self.previous.entries + (self.current.entries if self.current is not None else [])
        return self.current.entries if self.current is not None else []

    @property
    def ready(self):
        """A complete index exists (the previous one counts while a rescan runs)."""
        return (self.current is not None and self.current.complete) or self.previous is not None

    @property
    def refreshing(self):
        return self.previous is not None and self.current is not None and not self.current.complete

    def status(self):
        out = self.current.status() if self.current is not None else {"complete": False, "items": 0}
        if self.refreshing:
            out["refreshing"] = True
            out["previous_items"] = len(self.previous.entries)
        return out


def _expired(scan):
    ttl = VOLATILE_TTL if scan.category in VOLATILE else STATIC_TTL
    return scan.complete and (time.time() - scan.finished > ttl or scan.error is not None)


def ensure_scan(browser, category, force=False):
    """The category's index, starting a scan (or a rescan after the TTL, or when forced) if needed."""
    index = _INDEX.get(category)
    if index is None:
        index = _INDEX[category] = _CategoryIndex()
    if force or index.current is None or _expired(index.current):
        index.restart(browser, category)
    return index


def advance_scans(categories, budget):
    """Spend up to `budget` seconds scanning the given categories in priority order (the first pending
    category always advances by at least one item, so a scan finishes even with tiny budgets)."""
    deadline = time.time() + budget
    started = False
    for category in categories:
        index = _INDEX.get(category)
        if index is None or index.current is None or index.current.complete:
            continue
        remaining = deadline - time.time()
        if remaining <= 0 and started:
            break
        started = True
        if index.current.advance(max(remaining, 0.0)):
            index.previous = None


# -- Following browser changes ------------------------------------------------

PACK_CHECK_INTERVAL = 5.0   # seconds between checks of the installed packs (a pack install changes them)
PACK_SETTLE_DELAY = 30.0    # rescan again this long after a pack appears, once Live has indexed it
_LISTENER = {"status": None}  # per module load: this module's full_refresh listener
# Counters and flags; rebound to ctx.state on registration so they survive reload_remote_script.
_REFRESH = {"pending": False, "count": 0, "last": None, "pack_changes": 0, "packs": None, "checked": 0.0, "rescan_at": None}


def _on_full_refresh():
    """Browser.full_refresh listener (main thread): only flag it; the ticker rescans."""
    _REFRESH["pending"] = True
    _REFRESH["count"] += 1
    _REFRESH["last"] = time.time()


def ensure_listener(ctx):
    """Register the full_refresh listener once per module load, replacing the one a previous load
    of this module registered (kept in ctx.state, which survives reloads)."""
    global _REFRESH
    if _LISTENER["status"] is not None:
        return
    stored = ctx.state.setdefault("browser_refresh", _REFRESH)
    for key, value in _REFRESH.items():
        stored.setdefault(key, value)
    _REFRESH = stored
    browser = ctx.app.browser
    try:
        previous = ctx.state.get("browser_full_refresh_listener")
        if previous is not None and browser.full_refresh_has_listener(previous):
            browser.remove_full_refresh_listener(previous)
        browser.add_full_refresh_listener(_on_full_refresh)
        ctx.state["browser_full_refresh_listener"] = _on_full_refresh
        _LISTENER["status"] = True
    except Exception as error:  # No listener: the pack check and the TTL keep the index fresh instead.
        _LISTENER["status"] = "unavailable: {0}".format(error)


def check_packs(browser, now=None):
    """Flag a rescan when the installed packs change (checked every PACK_CHECK_INTERVAL seconds)."""
    now = time.time() if now is None else now
    if now - _REFRESH["checked"] < PACK_CHECK_INTERVAL:
        return
    _REFRESH["checked"] = now
    names = [item.name for item in browser.packs.children]
    if _REFRESH["packs"] is not None and names != _REFRESH["packs"]:
        _REFRESH["pending"] = True
        _REFRESH["pack_changes"] += 1
        _REFRESH["rescan_at"] = now + PACK_SETTLE_DELAY
    _REFRESH["packs"] = names
    if _REFRESH["rescan_at"] is not None and now >= _REFRESH["rescan_at"]:
        _REFRESH["pending"] = True
        _REFRESH["rescan_at"] = None


def rescan_all(browser):
    """Start a rescan of every indexed category (after Live refreshed its browser)."""
    for category, index in list(_INDEX.items()):
        index.restart(browser, category)


@ticker
def _browser_tick(ctx):
    if _LISTENER["status"] is None:
        ensure_listener(ctx)
    if _INDEX:
        try:
            check_packs(ctx.app.browser)
        except Exception:
            pass
    if _REFRESH["pending"]:
        _REFRESH["pending"] = False
        rescan_all(ctx.app.browser)
    pending = [category for category in CATEGORIES if category in _INDEX and _INDEX[category].current is not None and not _INDEX[category].current.complete]
    if pending:
        advance_scans(pending, TICK_BUDGET)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def score(entry, query, tokens):
    """Relevance of an index entry for a lower-case query (None = no match)."""
    name = entry[_LOWER]
    if name == query:
        value = 100
    elif name.startswith(query):
        value = 80
    elif all(token in name for token in tokens):
        words = name.replace("-", " ").replace("_", " ").split()
        value = 60 + (10 if all(any(word.startswith(token) for word in words) for token in tokens) else 0)
    elif all(token in entry[_PATH].lower() for token in tokens):
        value = 30
    else:
        return None
    if entry[_LOADABLE]:
        value += 5
    if entry[_DEVICE]:
        value += 3
    return value


def entry_out(entry, category):
    return {
        "name": entry[_NAME], "path": entry[_PATH], "uri": entry[_URI], "category": category, "kind": entry[_KIND],
        "is_loadable": entry[_LOADABLE], "is_device": entry[_DEVICE],
    }


def search(browser, query, category="all", limit=25, budget=SEARCH_BUDGET, kinds=None, loadable_only=False, refresh=False):
    """(results, scan report, match count). Results are ranked, deduplicated by file, at most `limit` long.

    Categories without a complete index are scanned for up to `budget` seconds before matching; a
    category being rescanned in the background is served from its previous index without waiting,
    unless refresh=True forces a rescan and waits for it.
    """
    text = " ".join(str(query or "").lower().split())
    if not text:
        raise CommandError("invalid_argument", "query must be a non-empty name or words to search for")
    tokens = [stem(token) if "." in token else token for token in text.split()]
    query_stem = stem(text)
    key = category_key(category)
    categories = list(CATEGORIES) if key == "all" else [key]
    for name in categories:
        ensure_scan(browser, name, force=refresh)
    waiting = [name for name in categories if refresh or not _INDEX[name].ready]
    advance_scans(waiting, budget)
    ranked = []
    order = dict((name, position) for position, name in enumerate(CATEGORIES))
    for name in categories:
        for entry in _INDEX[name].entries():
            if loadable_only and not entry[_LOADABLE]:
                continue
            if kinds and entry[_KIND] not in kinds:
                continue
            value = score(entry, query_stem, tokens)
            if value is not None:
                ranked.append((-value, order[name], entry[_DEPTH], len(entry[_NAME]), entry[_PATH], name, entry))
    ranked.sort(key=lambda item: item[:5])
    results, seen_ids, seen_names, total = [], set(), set(), 0
    for item in ranked:
        entry, name = item[-1], item[-2]
        identity = file_id(entry[_URI]) or entry[_URI]
        file_name = entry[_NAME].lower() if entry[_KIND] not in ("folder", "device", "plugin") else None
        # Packs list the same files as the category views under different URIs: list each file once.
        if identity in seen_ids or (name == "packs" and file_name in seen_names):
            continue
        seen_ids.add(identity)
        if file_name and name != "packs":
            seen_names.add(file_name)
        total += 1
        if len(results) < limit:
            results.append(entry_out(entry, name))
    report = dict((name, _INDEX[name].status()) for name in categories)
    complete = all(_INDEX[name].ready for name in categories)
    refreshing = any(_INDEX[name].refreshing for name in categories)
    return results, {"complete": complete, "refreshing": refreshing, "categories": report}, total


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


def _children_named(item, segment):
    children = list(item.children)
    key = str(segment).strip().lower()
    for test in (lambda child: child.name.lower() == key, lambda child: stem(child.name).lower() == key):
        hits = [child for child in children if test(child)]
        if hits:
            return hits[0], children
    return None, children


def item_at_path(browser, path):
    """The BrowserItem at '<category>/<child>/...' (names match case-insensitively, extensions optional)."""
    parts = [part for part in str(path or "").strip().strip("/").split("/") if part.strip()]
    if not parts:
        raise CommandError("invalid_argument", "path must start with a category: {0}".format(", ".join(CATEGORIES)))
    category = category_key(parts[0])
    if category == "all":
        raise CommandError("invalid_argument", "path must start with a category: {0}".format(", ".join(CATEGORIES)))
    if category == "user_folders":
        if len(parts) < 2:
            return None, "user_folders"
        folders = list(browser.user_folders)
        current = next((item for item in folders if item.name.lower() == parts[1].strip().lower()), None)
        if current is None:
            raise not_found("User folder", parts[1], [item.name for item in folders])
        walked, rest = ["user_folders", current.name], parts[2:]
    else:
        current, walked, rest = getattr(browser, category), [category], parts[1:]
    for segment in rest:
        found, children = _children_named(current, segment)
        if found is None:
            raise not_found("Browser item at '{0}': child".format("/".join(walked)), segment, [child.name for child in children])
        current = found
        walked.append(found.name)
    return current, "/".join(walked)


def item_by_uri(browser, uri):
    """Walk the tree to the item with this URI: each level's URI is a prefix of its children's."""
    target = str(uri).strip()
    for category in CATEGORIES:
        for path, root in category_roots(browser, category):
            root_uri = root.uri
            if not root_uri or not (target == root_uri or target.startswith(root_uri + "#") or target.startswith(root_uri + ":")):
                continue
            current, walked = root, path
            for _ in range(MAX_DEPTH + 2):
                if current.uri == target:
                    return current, walked
                step = None
                for child in current.children:
                    child_uri = child.uri
                    if target == child_uri or target.startswith(child_uri + ":") or target.startswith(child_uri + "#"):
                        step = child
                        break
                if step is None:
                    break
                current, walked = step, walked + "/" + step.name
    for category in CATEGORIES:  # Fall back to the index (URIs that do not nest, e.g. user folders).
        index = _INDEX.get(category)
        if index is None:
            continue
        for entry in index.entries():
            if entry[_URI] == target:
                return item_at_path(browser, entry[_PATH])
    raise CommandError("not_found", "No browser item has URI {0!r}".format(uri), hint="Find items with search_browser or browse.")


def describe(item, path, category):
    name = item.name
    is_folder, is_device, loadable = bool(item.is_folder), bool(item.is_device), bool(item.is_loadable)
    return {
        "name": name, "path": path, "uri": item.uri, "kind": kind_of(name, is_folder, is_device, loadable, category),
        "is_loadable": loadable, "is_device": is_device,
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@command("search_browser", readonly=True, timeout=15.0)
def search_browser(ctx, query, category="all", limit=25, refresh=False):
    """Search browser items by name across categories; returns names, paths and URIs."""
    count = int(limit) if limit is not None else 25
    if not 1 <= count <= 200:
        raise CommandError("invalid_argument", "limit must be 1..200, got {0!r}".format(limit))
    ensure_listener(ctx)
    results, scan, total = search(ctx.app.browser, query, category, count, refresh=bool(refresh))
    out = {"query": query, "category": category_key(category), "count": len(results), "matches": total, "results": results}
    if not scan["complete"]:
        out["truncated"] = True
        out["hint"] = "The browser index is still being built in the background; repeat the search in a few seconds for complete results."
    elif scan["refreshing"]:
        out["refreshing"] = True
        out["hint"] = "The browser changed and is being re-indexed; newly added items may appear in a few seconds (or pass refresh=true)."
    if not scan["complete"] or scan["refreshing"]:
        out["scan"] = dict((name, status) for name, status in scan["categories"].items() if not status["complete"])
    return out


@command("browse", readonly=True, timeout=15.0)
def browse(ctx, path="", limit=100, offset=0):
    """List a browser folder: categories at the root, else the children of '<category>/<folder>/...'."""
    browser = ctx.app.browser
    if not str(path or "").strip().strip("/"):
        return {"path": "", "items": [{"name": name, "path": name, "kind": "category"} for name in CATEGORIES]}
    count, start = int(limit), int(offset)
    if not 1 <= count <= 1000 or start < 0:
        raise CommandError("invalid_argument", "limit must be 1..1000 and offset >= 0")
    item, walked = item_at_path(browser, path)
    category = walked.split("/", 1)[0]
    if item is None:  # user_folders root
        folders = list(browser.user_folders)
        return {"path": walked, "count": len(folders), "items": [describe(folder, "user_folders/" + folder.name, category) for folder in folders]}
    children = list(item.children)
    page = children[start:start + count]
    out = {"path": walked, "item": describe(item, walked, category), "count": len(children), "offset": start,
           "items": [describe(child, walked + "/" + child.name, category) for child in page]}
    if start + count < len(children):
        out["more"] = True
    return out


@command("browser_scan_status", readonly=True)
def browser_scan_status(ctx, start=None):
    """Index state per category and the full_refresh listener; `start` (a category or "all") begins scans."""
    ensure_listener(ctx)
    if start is not None:
        key = category_key(start)
        for name in (CATEGORIES if key == "all" else (key,)):
            ensure_scan(ctx.app.browser, name)
    return {
        "categories": dict((name, index.status()) for name, index in _INDEX.items() if index.current is not None),
        "listener": _LISTENER["status"], "full_refreshes": _REFRESH["count"], "pack_changes": _REFRESH["pack_changes"],
        "packs": _REFRESH["packs"],
        "last_full_refresh_age_s": None if _REFRESH["last"] is None else round(time.time() - _REFRESH["last"], 1),
    }


def _pointers(items):
    return [getattr(item, "_live_ptr", None) for item in items]


def resolve_item(browser, uri=None, path=None, query=None, kinds=None):
    """(item, path, category, alternatives) for exactly one of uri, path or query."""
    given = [name for name, value in (("uri", uri), ("path", path), ("query", query)) if value is not None]
    if len(given) != 1:
        raise CommandError("invalid_argument", "Pass exactly one of uri, path or query (got {0})".format(", ".join(given) or "none"))
    alternatives = []
    if uri is not None:
        item, where = item_by_uri(browser, uri)
    elif path is not None:
        item, where = item_at_path(browser, path)
    else:
        results, scan, _ = search(browser, query, "all", 4, kinds=kinds, loadable_only=True)
        if not results:
            hint = "The browser index is still being built; retry in a few seconds." if not scan["complete"] else "Use search_browser to find items."
            raise CommandError("not_found", "No loadable browser item matches {0!r}{1}".format(query, " of kind " + "/".join(kinds) if kinds else ""), hint=hint)
        item, where = item_at_path(browser, results[0]["path"])
        alternatives = [result["path"] for result in results[1:]]
    return item, where, where.split("/", 1)[0], alternatives


def needs_midi_track(category, kind):
    """Whether Live loads this item only onto MIDI tracks (elsewhere it silently creates a MIDI track)."""
    if kind in ("device", "preset", "rack_preset"):
        return category in ("instruments", "sounds", "drums", "midi_effects")
    return False


def first_drum_rack(owner):
    for device in owner.devices:
        if device.can_have_drum_pads:
            return device
    return None


def load_item_on_track(ctx, owner, item, position=None, drum_pad=None, holder=None):
    """Load a BrowserItem onto a track, a device position, a drum pad or a Session slot.

    Live's browser loads onto the selected track (synchronously), so this selects the target,
    positions the insert point through Track.View.device_insert_mode and the selected device, selects
    the drum pad or highlights the slot, loads, and then restores the selection, insert mode and
    focused view. Returns (new devices, removed device names, created tracks).
    """
    song, app = ctx.song, ctx.app
    view = song.view
    previous_track, previous_scene = view.selected_track, view.selected_scene
    previous_focus = app.view.focused_document_view
    if app.view.browse_mode:
        app.view.toggle_browse()  # Leave hot-swap mode, or the load would replace the hot-swap target.
    tracks_before = _pointers(song.tracks)
    # Snapshot before loading: reading a device Live deleted raises (Boost ArgumentError), and a device
    # replaced by the same device type keeps its pointer, so names tell those replacements apart.
    devices_before = [(getattr(device, "_live_ptr", None), device.name) for device in owner.devices]
    try:
        view.selected_track = owner
        if position is None or drum_pad is not None or holder is not None:
            owner.view.device_insert_mode = 0  # A previous positioned load may have left "insert left".
        if drum_pad is not None:
            view.select_device(drum_pad.canonical_parent)
            drum_pad.canonical_parent.view.selected_drum_pad = drum_pad
        elif holder is not None:
            view.highlighted_clip_slot = holder
            if previous_focus != "Session":
                app.view.focus_view("Session")  # Slot loads do nothing while Arrangement View has focus.
        else:
            devices = list(owner.devices)
            if position is None or position < 0 or position >= len(devices):
                owner.view.device_insert_mode = 0  # Default: append at the end.
            else:
                view.select_device(devices[position])
                owner.view.device_insert_mode = 1  # Insert left of the selected device.
        ctx.app.browser.load_item(item)
    finally:
        try:
            owner.view.device_insert_mode = 0
        except Exception:
            pass
        for restore in (lambda: setattr(view, "selected_track", previous_track), lambda: setattr(view, "selected_scene", previous_scene)):
            try:
                restore()
            except Exception:
                pass
        if app.view.focused_document_view != previous_focus:
            try:
                app.view.focus_view("Arranger" if previous_focus == "Arranger" else "Session")
            except Exception:
                pass
    names_before = dict(devices_before)
    after = list(owner.devices)
    added, removed = [], []
    for index, device in enumerate(after):
        pointer = getattr(device, "_live_ptr", None)
        if pointer not in names_before:
            added.append((index, device))
        elif names_before[pointer] != device.name:  # Replaced in place (e.g. Operator loaded onto Operator).
            added.append((index, device))
            removed.append(names_before[pointer])
    kept = _pointers(after)
    removed = [name for pointer, name in devices_before if pointer not in kept] + removed
    created = [track for track in song.tracks if getattr(track, "_live_ptr", None) not in tracks_before]
    return added, removed, created


def _refuse_during_bounce(ctx):
    """Selecting or loading during a real-time bounce can arm a user track, which would record over it."""
    job = ctx.state.get("bounce")
    if isinstance(job, dict) and job.get("phase") in ("route", "arm", "go", "starting", "recording", "finalizing", "verifying", "aborting"):
        raise CommandError("busy", "A bounce is recording; selection and browser loads wait until get_bounce_status reports it done")


@command("load_from_browser", timeout=30.0)
def load_from_browser(ctx, track, uri=None, path=None, query=None, position=None, drum_pad=None, slot=None):
    """Load a browser item (by uri, path or query) onto a track, device position, drum pad or Session slot."""
    _refuse_during_bounce(ctx)
    from . import devices as device_handlers
    song = ctx.song
    owner = refs.track(song, track)
    targets = [name for name, value in (("position", position), ("drum_pad", drum_pad), ("slot", slot)) if value is not None]
    if len(targets) > 1:
        raise CommandError("invalid_argument", "Pass at most one target: position, drum_pad or slot (got {0})".format(", ".join(targets)))
    kind_filter = ("sample",) if slot is not None else None
    item, where, category, alternatives = resolve_item(ctx.app.browser, uri, path, query, kind_filter)
    entry = describe(item, where, category)
    if not entry["is_loadable"]:
        raise CommandError("invalid_argument", "'{0}' is a folder, not a loadable item".format(where), hint="List it with browse(path='{0}').".format(where))
    kind = entry["kind"]
    track_kind = refs.track_kind(song, owner)
    if position is not None and kind in ("sample", "clip"):
        raise CommandError("invalid_argument", "position places devices; '{0}' is a {1}".format(where, kind),
                           hint="Samples go to a Session slot (slot=) on audio tracks, a Simpler on MIDI tracks, or a pad (drum_pad=).")
    pad = holder = None
    index = None
    if drum_pad is not None:
        rack = first_drum_rack(owner)
        if rack is None:
            raise CommandError("not_found", "Track '{0}' has no Drum Rack".format(owner.name), hint="Add one with add_device(track, 'Drum Rack') or load a kit from 'drums'.")
        pad = device_handlers.drum_pad(rack, drum_pad)
    elif slot is not None or (kind == "sample" and track_kind == "audio"):
        if kind != "sample":
            raise CommandError("unsupported", "Session slots take samples (audio clips); '{0}' is a {1}".format(where, kind),
                               hint="Clips (.alc) load onto a new track; devices and presets load onto the track.")
        if track_kind != "audio":
            raise CommandError("unsupported", "Samples go into Session slots of audio tracks; '{0}' is a {1} track".format(owner.name, track_kind),
                               hint="On a MIDI track, load the sample without slot (it becomes a Simpler) or onto a Drum Rack pad with drum_pad.")
        slots = list(owner.clip_slots)
        if slot is None:
            free = [position_ for position_, item_ in enumerate(slots) if not item_.has_clip]
            if not free:
                raise CommandError("invalid_argument", "Track '{0}' has no empty Session slot; pass slot or add a scene".format(owner.name))
            slot = free[0]
        holder = refs.clip_slot(song, track, slot)
        if holder.has_clip:
            raise CommandError("invalid_argument", "Slot {0} of track '{1}' already holds a clip".format(slot, owner.name), hint="Delete it first or choose an empty slot.")
    elif kind == "sample" and track_kind in ("return", "master"):
        raise CommandError("unsupported", "Samples cannot load onto the {0} track".format(track_kind))
    elif track_kind != "midi" and needs_midi_track(category, kind):
        raise CommandError(
            "unsupported",
            "'{0}' is an instrument, instrument preset, drum kit or MIDI effect, which only loads on MIDI tracks; "
            "on the {1} track '{2}' Live would create a new MIDI track instead".format(where, track_kind, owner.name),
            hint="Load it onto a MIDI track (create_track(kind='midi')).",
        )
    elif position is not None:
        index = device_handlers._position(position)
        count = len(owner.devices)
        if index > count:
            raise CommandError("invalid_argument", "position {0} is out of range (0..{1}; -1 = end)".format(index, count))
    added, removed, created = load_item_on_track(ctx, owner, item, index, pad, holder)
    out = {"loaded": entry, "track": refs.track_label(song, owner)}
    if added:
        out["devices"] = [device_handlers.summary(device, position_) for position_, device in added]
    if removed:
        out["replaced"] = removed
    if pad is not None:
        out["pad"] = {"note": pad.note, "note_name": device_handlers.note_name(pad.note), "name": pad.name, "chains": [chain.name for chain in pad.chains]}
    if holder is not None:
        out["slot"] = {"slot": int(slot), "has_clip": bool(holder.has_clip)}
        if holder.has_clip:
            out["slot"]["clip"] = holder.clip.name
    if created:
        out["created_tracks"] = [refs.track_label(song, item_) for item_ in created]
        out["note"] = "Live put this item on a new track (clips load as a track with their devices)"
    if alternatives:
        out["alternatives"] = alternatives
    if not (added or removed or created or (holder is not None and holder.has_clip) or (pad is not None and len(pad.chains))):
        out["warning"] = ("No device, pad or slot changed. Loading the same device the track already has resets it in "
                          "place, which cannot be told apart; check with get_devices")
    return out
