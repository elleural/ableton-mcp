"""Unit tests for WS-D browser logic (handlers/browser.py): naming, the incremental index, ranking,
de-duplication, refresh, and path/URI navigation, against a fake browser tree."""
import pytest

from AbletonMCP_Remote_Script import core
from AbletonMCP_Remote_Script.errors import CommandError

core.load_handlers()  # the full registry, so this module never leaves a partial one for other tests
from AbletonMCP_Remote_Script.handlers import browser  # noqa: E402


class Item(object):
    """A BrowserItem: URIs nest like Live's ("query:Synths" > "query:Synths#Operator" > "...:Bass")."""

    def __init__(self, name, uri, children=(), is_folder=False, is_device=False, is_loadable=True):
        self.name, self.uri, self.children = name, uri, list(children)
        self.is_folder, self.is_device, self.is_loadable = is_folder, is_device, is_loadable


def folder(name, uri, children=()):
    return Item(name, uri, children, is_folder=True, is_loadable=False)


def make_browser(extra_sample=None):
    operator = Item("Operator", "query:Synths#Operator", is_device=True, children=[
        folder("Bass", "query:Synths#Operator:Bass", [
            Item("Acid Bass.adv", "query:Synths#Operator:Bass:FileId_6972"),
            Item("Sub Bass.adv", "query:Synths#Operator:Bass:FileId_6973"),
        ]),
    ])
    samples = [Item("Kick 808.wav", "query:Samples#FileId_1"), Item("Snare Tight.aif", "query:Samples#FileId_2")]
    if extra_sample:
        samples.append(Item(extra_sample, "query:Samples#FileId_3"))
    roots = {
        "instruments": folder("Instruments", "query:Synths", [operator, Item("Simpler", "query:Synths#Simpler", is_device=True)]),
        "audio_effects": folder("Audio Effects", "query:AudioFx", [Item("Reverb", "query:AudioFx#Reverb", is_device=True)]),
        "midi_effects": folder("MIDI Effects", "query:MidiFx"),
        "sounds": folder("Sounds", "query:Sounds", [folder("Bass", "query:Sounds#Bass", [Item("Acid Bass.adv", "query:Sounds#Bass:FileId_6972")])]),
        "drums": folder("Drums", "query:Drums", [Item("808 Core Kit.adg", "query:Drums#FileId_5483")]),
        "plugins": folder("Plug-Ins", "query:Plugins"),
        "max_for_live": folder("Max for Live", "query:MaxForLive"),
        "user_library": folder("User Library", "query:UserLibrary"),
        "clips": folder("Clips", "query:Clips"),
        "samples": folder("Samples", "query:Samples", samples),
        "packs": folder("Packs", "query:LivePacks", [folder("Core Library", "query:LivePacks#core", [
            Item("Acid Bass.adv", "query:LivePacks#core:Acid%20Bass.adv"),
            Item("Kick 808.wav", "query:LivePacks#core:Kick%20808.wav"),
        ])]),
        "current_project": folder("Current Project", "query:CurrentProject"),
    }

    class Browser(object):
        user_folders = [folder("Loops", "userfolder:/Users/me/Loops", [Item("Break.wav", "userfolder:/Users/me/Loops#Break.wav")])]

    fake = Browser()
    for key, value in roots.items():
        setattr(fake, key, value)
    return fake


@pytest.fixture(autouse=True)
def fresh_index(monkeypatch):
    monkeypatch.setattr(browser, "_INDEX", {})


@pytest.mark.parametrize("name, result", [("Acid Bass.adv", "Acid Bass"), ("Kick 808.wav", "Kick 808"), ("Operator", "Operator"),
                                          ("Piano & Keys", "Piano & Keys"), ("Mr. Bass", "Mr. Bass"), ("Track 1.2", "Track 1.2")])
def test_stem(name, result):
    assert browser.stem(name) == result


@pytest.mark.parametrize("args, kind", [
    (("Operator", False, True, True, "instruments"), "device"), (("Serum", False, True, True, "plugins"), "plugin"),
    (("Acid Bass.adv", False, False, True, "sounds"), "preset"), (("Kit.adg", False, False, True, "drums"), "rack_preset"),
    (("Kick.WAV", False, False, True, "samples"), "sample"), (("Groove.alc", False, False, True, "clips"), "clip"),
    (("LFO.amxd", False, False, True, "max_for_live"), "max_device"), (("Bass", True, False, False, "sounds"), "folder"),
])
def test_kind_of(args, kind):
    assert browser.kind_of(*args) == kind


def test_file_id():
    assert browser.file_id("query:Synths#Operator:Bass:FileId_6972") == "FileId_6972"
    assert browser.file_id("query:Synths#Operator") is None


@pytest.mark.parametrize("value, key", [("all", "all"), (None, "all"), ("Sounds", "sounds"), ("audio effects", "audio_effects"),
                                        ("m4l", "max_for_live"), ("user-library", "user_library"), ("plug-ins", "plugins")])
def test_category_key(value, key):
    assert browser.category_key(value) == key


def test_category_key_rejects_unknown():
    with pytest.raises(CommandError) as error:
        browser.category_key("synthesizers")
    assert "instruments" in error.value.message


def test_scan_indexes_everything_breadth_first_in_small_slices():
    fake = make_browser()
    scan = browser._Scan("instruments", browser.category_roots(fake, "instruments"))
    rounds = 0
    while not scan.advance(0.0):  # A zero budget still makes progress (one item per call).
        rounds += 1
        assert rounds < 50
    paths = [entry[browser._PATH] for entry in scan.entries]
    assert paths == ["instruments/Operator", "instruments/Simpler", "instruments/Operator/Bass",
                     "instruments/Operator/Bass/Acid Bass.adv", "instruments/Operator/Bass/Sub Bass.adv"]
    assert scan.status()["complete"] and scan.status()["items"] == 5


def test_scan_reports_errors_from_stale_items():
    class Broken(object):
        name, uri = "Broken", "query:Broken"

        @property
        def children(self):
            raise RuntimeError("Object no longer exists")

    scan = browser._Scan("samples", [("samples", Broken())])
    assert scan.advance(1.0)
    assert scan.status()["error"] == "Object no longer exists"


def test_search_ranks_exact_names_first_and_dedupes_files():
    results, report, total = browser.search(make_browser(), "acid bass", "all", 10)
    assert report["complete"]
    assert [item["path"] for item in results] == ["instruments/Operator/Bass/Acid Bass.adv"]  # same FileId in sounds; same file name in packs
    assert results[0]["kind"] == "preset" and results[0]["uri"].endswith("FileId_6972") and total == 1


def test_search_devices_folders_and_limits():
    fake = make_browser()
    results, _, total = browser.search(fake, "operator", "all", 10)
    assert results[0] == {"name": "Operator", "path": "instruments/Operator", "uri": "query:Synths#Operator", "category": "instruments",
                          "kind": "device", "is_loadable": True, "is_device": True}
    assert total == 4  # the device, its Bass folder and two presets (matched by path)
    assert len(browser.search(fake, "operator", "all", 2)[0]) == 2
    loadable, _, _ = browser.search(fake, "bass", "instruments", 10, loadable_only=True)
    assert all(item["is_loadable"] for item in loadable)
    samples, _, _ = browser.search(fake, "kick", "all", 10, kinds=("sample",))
    assert [item["path"] for item in samples] == ["samples/Kick 808.wav"]


def test_search_rejects_empty_query():
    with pytest.raises(CommandError):
        browser.search(make_browser(), "  ", "all", 5)


def test_search_scans_within_budget_and_reports_truncation():
    fake = make_browser()
    results, report, _ = browser.search(fake, "kick", "samples", 5, budget=0.0)
    assert not report["complete"] or results  # one item per call at least; the ticker finishes the rest
    while not browser._INDEX["samples"].current.complete:
        browser.advance_scans(["samples"], 0.0)
    results, report, _ = browser.search(fake, "kick", "samples", 5)
    assert report["complete"] and results[0]["name"] == "Kick 808.wav"


def test_refresh_picks_up_new_items_and_serves_the_old_index_meanwhile():
    fake = make_browser()
    assert browser.search(fake, "clap", "samples", 5)[0] == []
    fake.samples.children.append(Item("Clap Wide.wav", "query:Samples#FileId_9"))
    index = browser.ensure_scan(fake, "samples", force=True)  # what the full_refresh listener triggers
    assert index.refreshing and len(index.entries()) == 2      # the previous index still answers
    browser.advance_scans(["samples"], 1.0)
    assert not index.refreshing
    assert [item["name"] for item in browser.search(fake, "clap", "samples", 5)[0]] == ["Clap Wide.wav"]


def test_search_refresh_flag_rescans_before_answering():
    fake = make_browser()
    browser.search(fake, "kick", "samples", 5)
    fake.samples.children.append(Item("Kick Deep.wav", "query:Samples#FileId_10"))
    assert len(browser.search(fake, "kick", "samples", 5)[0]) == 1        # cached index
    assert len(browser.search(fake, "kick", "samples", 5, refresh=True)[0]) == 2


@pytest.fixture
def refresh_state(monkeypatch):
    state = {"pending": False, "count": 0, "last": None, "pack_changes": 0, "packs": None, "checked": 0.0, "rescan_at": None}
    monkeypatch.setattr(browser, "_REFRESH", state)
    return state


def test_full_refresh_listener_flags_a_rescan(refresh_state):
    fake = make_browser()
    browser.search(fake, "kick", "samples", 5)
    browser._on_full_refresh()
    assert refresh_state["pending"] and refresh_state["count"] == 1
    browser.rescan_all(fake)
    assert browser._INDEX["samples"].refreshing


def test_pack_installs_flag_a_rescan_now_and_after_settling(refresh_state):
    fake = make_browser()
    browser.check_packs(fake, now=100.0)
    assert refresh_state["packs"] == ["Core Library"] and not refresh_state["pending"]
    fake.packs.children.append(folder("Drum Essentials", "query:LivePacks#drums"))
    browser.check_packs(fake, now=102.0)                 # within the check interval: not looked at yet
    assert not refresh_state["pending"]
    browser.check_packs(fake, now=106.0)
    assert refresh_state["pending"] and refresh_state["pack_changes"] == 1
    refresh_state["pending"] = False
    browser.check_packs(fake, now=106.0 + browser.PACK_SETTLE_DELAY)
    assert refresh_state["pending"] and refresh_state["rescan_at"] is None


def test_expired_scans_restart(monkeypatch):
    fake = make_browser()
    browser.search(fake, "kick", "samples", 5)
    scan = browser._INDEX["samples"].current
    monkeypatch.setattr(browser, "VOLATILE_TTL", -1.0)
    assert browser.ensure_scan(fake, "samples").current is not scan


def test_item_at_path_matches_case_and_extensions():
    fake = make_browser()
    item, walked = browser.item_at_path(fake, "instruments/operator/BASS/acid bass")
    assert item.uri.endswith("FileId_6972") and walked == "instruments/Operator/Bass/Acid Bass.adv"
    item, walked = browser.item_at_path(fake, "/user_folders/Loops/Break.wav/")
    assert walked == "user_folders/Loops/Break.wav"
    with pytest.raises(CommandError) as error:
        browser.item_at_path(fake, "instruments/Operator/Lead")
    assert "Bass" in error.value.message
    with pytest.raises(CommandError):
        browser.item_at_path(fake, "")
    with pytest.raises(CommandError):
        browser.item_at_path(fake, "all/Operator")


def test_item_by_uri_walks_nested_uris():
    fake = make_browser()
    item, walked = browser.item_by_uri(fake, "query:Synths#Operator:Bass:FileId_6973")
    assert item.name == "Sub Bass.adv" and walked == "instruments/Operator/Bass/Sub Bass.adv"
    assert browser.item_by_uri(fake, "query:Synths#Operator")[0].name == "Operator"
    assert browser.item_by_uri(fake, "userfolder:/Users/me/Loops#Break.wav")[1] == "user_folders/Loops/Break.wav"
    with pytest.raises(CommandError) as error:
        browser.item_by_uri(fake, "query:Synths#Nothing")
    assert error.value.code == "not_found"


def test_score_order():
    entry = lambda name, path, loadable=True, device=False: (name, browser.stem(name).lower(), path, "u", "x", loadable, device, 1)
    exact = browser.score(entry("Kick.wav", "drums/Kick.wav"), "kick", ["kick"])
    prefix = browser.score(entry("Kick Deep.wav", "drums/Kick Deep.wav"), "kick", ["kick"])
    words = browser.score(entry("Deep Kick.wav", "drums/Deep Kick.wav"), "kick", ["kick"])
    inner = browser.score(entry("Kickstart.wav", "drums/x/Kickstart.wav"), "kick start", ["kick", "start"])
    path_only = browser.score(entry("Boom.wav", "drums/Kick/Boom.wav"), "kick", ["kick"])
    assert exact > prefix > words > path_only and inner is not None
    assert browser.score(entry("Snare.wav", "drums/Snare.wav"), "kick", ["kick"]) is None
