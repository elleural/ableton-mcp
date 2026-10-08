"""Unit tests for ears/spec.py: the spec file every check reads (PRD section 4, plan section 2).

All offline and fast. The bundled NOVA spec is checked against the soundtrack brief as the PRD and the soundtrack
handoff state it; hand-built spec dicts cover layouts the bundled spec does not use (one track with clips A and B).
"""
import copy
import json

import pytest

from ears import spec as specs
from ears.spec import Spec, SpecError


@pytest.fixture(scope="module")
def nova():
    return specs.load("nova")


def clip_layout_data():
    """A hand-built spec where both variations live on one track, as clips named A and B (PRD 7.1)."""
    return {
        "name": "clipset",
        "key": "A minor",
        "progressions": {"A": ["Am", "Dm"], "B": ["Am", "F"]},
        "stems": {
            "kick": {"bars": 2, "pitched": False},
            "bass": {"bars": 4, "variations": ["A", "B"]},
            "lead": {"bars": 4, "variations": ["A", "B"], "rest_share": 0.4},
        },
        "tiers": {"T1": ["bass"], "T2": ["kick"], "T3": ["lead"]},
        "sets": {
            "demo": {
                "tempos": [120, 128, 136],
                "variations": {"A": "A", "B": "B"},
                "default_scene": "MAIN",
                "bands": [{"name": "ALL", "tempos": [100, 140], "scene": "MAIN"}],
            },
        },
        "targets": {"lufs_i": -14.0, "tail_ms": 40},
    }


# ---------------------------------------------------------------------------
# The bundled NOVA spec
# ---------------------------------------------------------------------------


def test_bundled_specs_include_nova():
    assert "nova" in specs.bundled()
    assert specs.BUNDLED_DIR.joinpath("nova.spec.json").is_file()


def test_load_nova_basics(nova):
    assert nova.name == "nova"
    assert (nova.key_name, nova.tonic, nova.mode) == ("A", 9, "minor")
    assert nova.scale == frozenset({9, 11, 0, 2, 4, 5, 7})           # A B C D E F G
    assert nova.meter == "4/4" and nova.beats_per_bar == 4.0 and nova.grid == 16 and nova.a4_hz == 440.0
    assert nova.target("lufs_i") == -14.0 and nova.target("true_peak_dbtp") == -1.0
    assert nova.target("sample_rate") == 48000 and nova.target("bit_depth") == 24
    assert nova.target("nope", "fallback") == "fallback"
    assert nova.tail_seconds() == pytest.approx(0.05)
    assert nova.bar_seconds(140) == pytest.approx(60.0 / 140 * 4)
    assert nova.bar_seconds(120) == pytest.approx(2.0)
    assert nova.set_names() == ["neon", "mainframe"] and nova.default_set() == "neon"
    assert [name for name in nova.progressions] == ["A", "B", "C", "D"]
    assert nova.progressions["B"] == ["Am", "F", "Dm", "E"]
    assert nova.to_dict() is nova.data and nova.path.endswith("nova.spec.json")


# The abridged spec the PRD prints in section 4 (values from the soundtrack PRD); the bundled spec must agree with it.
PRD_EXAMPLE = {
    "key": "A minor", "a4_hz": 440, "meter": "4/4", "grid": 16,
    "progressions": {"A": ["Am", "Am", "Dm", "Dm"], "B": ["Am", "F", "Dm", "E"], "C": ["Am", "Dm", "G", "E"], "D": ["Am", "F", "C", "G"]},
    "sets": {"neon": {"tempos": [100, 110, 120, 130, 140, 150, 160, 170, 180], "variations": {"A": "A", "B": "B"}}, "mainframe": {"tempos": [100, 110, 120, 130]}},
    "stems": {"kick": {"bars": 2, "pitched": False}, "perc": {"bars": 4, "pitched": False}, "pad": {"bars": 16},
              "bass": {"bars": 8, "variations": ["A", "B"]}, "arp": {"bars": 8, "variations": ["A", "B"]},
              "lead": {"bars": 8, "variations": ["A", "B"], "rest_share": 0.4}},
    "tiers": {"T1": ["pad", "arp"], "T2": ["bass"], "T3": ["kick"], "T4": ["perc"], "T5": ["lead"]},
    "targets": {"lufs_i": -14, "true_peak_dbtp": -1, "tail_ms": 50, "sample_rate": 48000, "bit_depth": 24},
}


def test_the_bundled_spec_agrees_with_the_prd_example(nova):
    data = nova.data
    for key in ("key", "a4_hz", "meter", "grid", "progressions", "tiers"):
        assert data[key] == PRD_EXAMPLE[key], key
    for set_name, entry in PRD_EXAMPLE["sets"].items():
        for key, value in entry.items():
            assert data["sets"][set_name][key] == value, (set_name, key)
    for stem, entry in PRD_EXAMPLE["stems"].items():
        for key, value in entry.items():
            assert data["stems"][stem][key] == value, (stem, key)
    assert list(data["stems"]) == list(PRD_EXAMPLE["stems"])                      # the order the tiers and files follow
    for key, value in PRD_EXAMPLE["targets"].items():
        assert data["targets"][key] == value, key


def test_every_tempo_of_every_set_falls_in_exactly_one_band_with_a_scene(nova):
    for set_name in nova.set_names():
        bands = nova.bands(set_name)
        for tempo in nova.tempos(set_name):
            holding = [band for band in bands if band["tempos"][0] <= tempo <= band["tempos"][1]]
            assert len(holding) == 1, (set_name, tempo)
            assert nova.band(set_name, tempo) is holding[0] and holding[0]["scene"] in nova.scenes_for(set_name, holding[0])
        assert all(nova.scenes_for(set_name, band)[-1] == nova.set_spec(set_name)["default_scene"] for band in bands)


def test_the_bundled_spec_is_internally_consistent(nova):
    from ears import theory
    for set_name in nova.set_names():
        parts = nova.parts(set_name)
        assert len(set(part.id for part in parts)) == len(parts) and len(set(part.track for part in parts)) == len(parts)
        assert all(part.bars in (2, 4, 8, 16) for part in parts)
        assert set(part.stem for part in parts) == set(nova.stems)
        for variation in nova.variations(set_name):
            assert all(theory.parse_chord(chord) for chord in nova.progression(set_name, variation))
            members = sum(nova.tier_parts(set_name, variation).values(), [])
            assert set(members) == set(part.id for part in nova.parts(set_name, variations=[variation]))     # every part is in some tier
    for tier, stems in nova.tiers.items():
        assert all(stem in nova.stems for stem in stems)
    assert 16 % nova.stems["kick"]["bars"] == 0 and all(16 % entry["bars"] == 0 for entry in nova.stems.values())      # all loops divide the longest


def test_tolerances_default_and_override(nova):
    assert nova.tolerance("lufs_i_lu") == 0.5 and nova.tolerance("duration_ms") == 1.0
    assert nova.tolerance("chord_tone_beats") == [1, 3]
    assert nova.tolerance("missing", 7) == 7
    data = copy.deepcopy(nova.data)
    data["tolerances"] = {"lufs_i_lu": 1.5, "brand_new": 3}
    custom = Spec(data)
    assert custom.tolerance("lufs_i_lu") == 1.5 and custom.tolerance("brand_new") == 3
    assert custom.tolerance("duration_ms") == specs.DEFAULT_TOLERANCES["duration_ms"]   # untouched defaults survive
    assert nova.tolerance("lufs_i_lu") == 0.5                                           # the original is not shared


def test_tail_seconds_defaults_to_the_briefs_50_ms():
    data = clip_layout_data()
    assert Spec(data).tail_seconds() == pytest.approx(0.04)
    del data["targets"]["tail_ms"]
    assert Spec(data).tail_seconds() == pytest.approx(0.05)


def test_neon_parts_ids_tracks_bars_and_progressions(nova):
    parts = nova.parts("neon")
    assert [part.id for part in parts] == ["kick", "perc", "pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"]
    by_id = dict((part.id, part) for part in parts)
    assert [by_id[name].track for name in by_id] == ["kick", "perc", "pad", "bassA", "bassB", "arpA", "arpB", "leadA", "leadB"]
    assert dict((part.id, part.bars) for part in parts) == {
        "kick": 2, "perc": 4, "pad": 16, "bassA": 8, "bassB": 8, "arpA": 8, "arpB": 8, "leadA": 8, "leadB": 8}
    assert [part.id for part in parts if not part.pitched] == ["kick", "perc"]
    assert by_id["bassA"].variation == "A" and by_id["bassB"].variation == "B" and by_id["kick"].variation is None
    assert by_id["bassA"].progressions == ["A"] and by_id["bassB"].progressions == ["B"]
    assert by_id["pad"].progressions == ["A", "B"]                      # the shared pad plays under both
    assert by_id["kick"].progressions == ["A", "B"]
    assert by_id["leadA"].rest_share == 0.4 and by_id["arpA"].rest_share is None
    assert by_id["bassA"].stem == "bass" and by_id["bassA"].role == "bass" and by_id["bassA"].set == "neon"
    assert all(part.clip_name is None for part in parts)                # track layout: clip names do not select anything


def test_mainframe_parts_use_the_mf_prefix_and_progression_c(nova):
    parts = dict((part.id, part) for part in nova.parts("mainframe"))
    assert parts["bassA"].track == "mf_bassA" and parts["bassB"].track == "mf_bassB"
    assert parts["kick"].track == "mf_kick" and parts["pad"].track == "mf_pad"
    assert nova.variations("mainframe") == ["A", "B"]
    assert nova.progression("mainframe", "A") == ["Am", "Am", "Dm", "Dm"]
    assert nova.progression("mainframe", "B") == ["Am", "Dm", "G", "E"]    # progression C (plan section 1)
    assert nova.progression_id("mainframe", "B") == "C" and nova.progression_id("neon", "B") == "B"
    assert parts["bassB"].progressions == ["C"]
    assert parts["pad"].progressions == ["A", "C"]
    assert nova.tempos("mainframe") == [100.0, 110.0, 120.0, 130.0]


def test_neon_progression_table(nova):
    assert nova.progression("neon", "A") == ["Am", "Am", "Dm", "Dm"]
    assert nova.progression("neon", "B") == ["Am", "F", "Dm", "E"]
    assert nova.tempos("neon") == [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0]
    assert nova.middle_tempo("neon") == 140.0 and nova.middle_tempo("mainframe") == 120.0


def test_progression_returns_a_copy(nova):
    chords = nova.progression("neon", "A")
    chords.append("X")
    assert nova.progression("neon", "A") == ["Am", "Am", "Dm", "Dm"]


def test_parts_can_be_limited_to_a_variation(nova):
    only_a = nova.parts("neon", variations="A")
    assert [part.id for part in only_a] == ["kick", "perc", "pad", "bassA", "arpA", "leadA"]
    assert [part.id for part in nova.parts("neon", variations=["B"])] == ["kick", "perc", "pad", "bassB", "arpB", "leadB"]
    assert [part.id for part in nova.parts("neon", variations=["A", "B"])] == [part.id for part in nova.parts("neon")]
    assert [part.id for part in nova.parts(None)] == [part.id for part in nova.parts("neon")]      # default set
    assert [part.id for part in nova.parts("NEON")] == [part.id for part in nova.parts("neon")]    # any spelling


def test_part_lookup(nova):
    assert nova.part("neon", "bassA").track == "bassA"
    with pytest.raises(SpecError, match="no part 'nope'.*kick, perc, pad, bassA"):
        nova.part("neon", "nope")


def test_set_names_are_found_in_any_spelling_and_unknown_ones_are_listed(nova):
    assert nova.set_name("NEON") == "neon" and nova.set_name(" Mainframe ") == "mainframe" and nova.set_name(None) == "neon"
    assert nova.set_spec("MainFrame") is nova.sets["mainframe"]
    with pytest.raises(SpecError, match=r"no set 'tetris'.*sets: neon, mainframe"):
        nova.set_name("tetris")
    with pytest.raises(SpecError, match="no set"):
        nova.set_spec("tetris")
    with pytest.raises(SpecError):
        nova.tempos("tetris")


def test_unknown_variation_errors_list_what_exists(nova):
    with pytest.raises(SpecError, match=r"no variation 'Z'.*variations: A, B"):
        nova.progression("neon", "Z")
    with pytest.raises(SpecError, match=r"no variation Z.*variations: A, B"):
        nova.parts("neon", variations="Z")
    with pytest.raises(SpecError, match="no variation"):
        nova.parts("neon", variations=["A", "Z"])


# -- bands -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("tempo, band", [
    (100, "LOW"), (110, "LOW"), (120, "LOW"), (130, "MID"), (140, "MID"), (150, "MID"), (160, "HIGH"), (170, "HIGH"), (180, "HIGH"),
    (135.5, "MID"), (100.0000001, "LOW"),
])
def test_band_by_tempo(nova, tempo, band):
    assert nova.band("neon", tempo)["name"] == band


def test_band_by_name_is_case_insensitive_and_carries_scene_and_kick(nova):
    band = nova.band("neon", name="mid")
    assert band["name"] == "MID" and band["scene"] == "NEON-MID" and band["kick"] == "four-on-the-floor"
    assert nova.band("neon", name="LOW")["kick"] == "half-time"
    assert nova.band("neon", name="HIGH")["kick"] is None                # the brief names none for 160-180
    assert nova.band("mainframe", 130)["scene"] == "MF-MID" and nova.band("mainframe", 100)["scene"] == "MF-LOW"


def test_band_name_wins_over_tempo(nova):
    assert nova.band("neon", tempo=180, name="LOW")["name"] == "LOW"


@pytest.mark.parametrize("tempo", [99, 125, 129.9, 190])
def test_tempo_outside_every_band_is_an_error_that_lists_the_bands(nova, tempo):
    with pytest.raises(SpecError) as caught:
        nova.band("neon", tempo)
    message = str(caught.value)
    assert "in no band of set 'neon'" in message and "LOW 100-120" in message and "MID 130-150" in message and "HIGH 160-180" in message


def test_unknown_band_name_is_an_error_that_lists_the_bands(nova):
    with pytest.raises(SpecError, match=r"no band 'HUGE'.*bands: LOW, MID, HIGH"):
        nova.band("neon", name="HUGE")


def test_band_is_none_for_a_set_without_bands():
    data = clip_layout_data()
    del data["sets"]["demo"]["bands"]
    spec = Spec(data)
    assert spec.bands("demo") == [] and spec.band("demo", 120) is None and spec.band("demo", name="ALL") is None


# -- scenes ----------------------------------------------------------------------------------------------


def test_scenes_for_lists_the_bands_scene_first_then_the_default(nova):
    assert nova.scenes_for("neon", nova.band("neon", 100)) == ["NEON-LOW", "NEON-MID"]
    assert nova.scenes_for("neon", nova.band("neon", 140)) == ["NEON-MID"]                  # no duplicate of the default
    assert nova.scenes_for("neon", nova.band("neon", 180)) == ["NEON-HIGH", "NEON-MID"]
    assert nova.scenes_for("neon") == ["NEON-MID"] and nova.scenes_for("neon", None) == ["NEON-MID"]
    assert nova.scenes_for("mainframe", nova.band("mainframe", 110)) == ["MF-LOW", "MF-MID"]
    assert nova.scenes_for("mainframe", nova.band("mainframe", 130)) == ["MF-MID"]


def test_scenes_for_ignores_a_band_without_a_scene(nova):
    assert nova.scenes_for("neon", {"name": "ODD"}) == ["NEON-MID"]
    assert nova.scenes_for("neon", {"name": "ODD", "scene": "X"}) == ["X", "NEON-MID"]


def test_scenes_for_a_set_with_no_default_scene():
    data = clip_layout_data()
    del data["sets"]["demo"]["default_scene"]
    spec = Spec(data)
    assert spec.scenes_for("demo") == [] and spec.scenes_for("demo", spec.band("demo", 120)) == ["MAIN"]


# -- layout ----------------------------------------------------------------------------------------------


def test_layout_track_for_the_bundled_sets(nova):
    assert nova.layout("neon") == "track" and nova.layout("mainframe") == "track"
    assert nova.track_pattern("neon") == "{stem}{variation}" and nova.track_pattern("mainframe") == "mf_{stem}{variation}"
    assert nova.track_name("neon", "bass", "A") == "bassA" and nova.track_name("mainframe", "bass", "B") == "mf_bassB"
    assert nova.track_name("neon", "kick") == "kick" and nova.track_name("mainframe", "kick") == "mf_kick"
    assert nova.track_name("neon", "kick", None) == "kick"


def test_layout_clip_puts_both_variations_on_one_track_with_clip_names():
    spec = Spec(clip_layout_data())
    assert spec.layout("demo") == "clip" and spec.track_pattern("demo") == "{stem}"
    parts = dict((part.id, part) for part in spec.parts("demo"))
    assert list(parts) == ["kick", "bassA", "bassB", "leadA", "leadB"]
    assert parts["bassA"].track == "bass" and parts["bassB"].track == "bass"      # one track
    assert parts["bassA"].clip_name == "A" and parts["bassB"].clip_name == "B"    # told apart by clip name
    assert parts["kick"].clip_name is None and parts["kick"].track == "kick"
    assert spec.tier_parts("demo", "B") == {"T1": ["bassB"], "T2": ["bassB", "kick"], "T3": ["bassB", "kick", "leadB"]}


def test_layout_clip_with_a_prefix_pattern():
    data = clip_layout_data()
    data["sets"]["demo"]["tracks"] = "x_{stem}"
    spec = Spec(data)
    assert spec.layout("demo") == "clip"
    assert [part.track for part in spec.parts("demo")] == ["x_kick", "x_bass", "x_bass", "x_lead", "x_lead"]


def test_stems_whose_variations_are_not_in_the_set_are_shared():
    data = clip_layout_data()
    data["sets"]["demo"]["variations"] = {"A": "A"}                   # the set only plays variation A
    spec = Spec(data)
    assert [part.id for part in spec.parts("demo")] == ["kick", "bassA", "leadA"]
    data["sets"]["demo"].pop("variations")                            # no variations at all: every stem is one part
    spec = Spec(data)
    assert [part.id for part in spec.parts("demo")] == ["kick", "bass", "lead"]


# -- tiers -----------------------------------------------------------------------------------------------


def test_tier_stems_are_cumulative(nova):
    assert nova.tier_stems() == {
        "T1": ["pad", "arp"], "T2": ["pad", "arp", "bass"], "T3": ["pad", "arp", "bass", "kick"],
        "T4": ["pad", "arp", "bass", "kick", "perc"], "T5": ["pad", "arp", "bass", "kick", "perc", "lead"]}
    assert list(nova.tier_stems()) == ["T1", "T2", "T3", "T4", "T5"]


def test_tier_parts_are_cumulative_per_variation(nova):
    a = nova.tier_parts("neon", "A")
    assert list(a) == ["T1", "T2", "T3", "T4", "T5"]
    assert a["T1"] == ["pad", "arpA"]
    assert a["T2"] == ["pad", "arpA", "bassA"]
    assert a["T3"] == ["pad", "arpA", "bassA", "kick"]
    assert a["T4"] == ["pad", "arpA", "bassA", "kick", "perc"]
    assert a["T5"] == ["pad", "arpA", "bassA", "kick", "perc", "leadA"]
    assert nova.tier_parts("neon", "B")["T5"] == ["pad", "arpB", "bassB", "kick", "perc", "leadB"]
    assert nova.tier_parts("mainframe", "B")["T2"] == ["pad", "arpB", "bassB"]
    for tier, members in a.items():                                  # each tier contains the one below it
        lower = list(a)[:list(a).index(tier)]
        for below in lower:
            assert set(a[below]) <= set(members)


def test_longest_bars(nova):
    assert nova.longest_bars(nova.parts("neon")) == 16
    assert nova.longest_bars(nova.parts("neon", variations="A")[:2]) == 4       # kick (2) and perc (4)
    assert nova.longest_bars([]) == 0


def test_fills_come_from_the_set_and_are_a_copy(nova):
    fills = nova.fills("neon")
    assert fills["levelup_fill"]["bars"] == 1 and fills["levelup_fill"]["scene"] == "NEON-FILL"
    fills["scratch"] = {"bars": 9}
    assert "scratch" not in nova.fills("neon")
    assert nova.fills("mainframe")["levelup_fill"]["track"] == "mf_fill"
    assert Spec(clip_layout_data()).fills("demo") == {}


def test_part_repr_and_to_dict(nova):
    part = nova.part("neon", "bassB")
    assert repr(part) == "Part(bassB, track='bassB')"
    data = part.to_dict()
    assert data["id"] == "bassB" and data["bars"] == 8 and data["variation"] == "B" and set(data) == set(specs.Part.__slots__)
    assert json.loads(json.dumps(data)) == data


# ---------------------------------------------------------------------------
# resolve_path and load
# ---------------------------------------------------------------------------


def test_resolve_a_bundled_name_and_a_path(tmp_path):
    assert specs.resolve_path("nova") == specs.BUNDLED_DIR / "nova.spec.json"
    copy_path = tmp_path / "mine.json"
    copy_path.write_text(specs.BUNDLED_DIR.joinpath("nova.spec.json").read_text())
    assert specs.resolve_path(str(copy_path)) == copy_path
    assert specs.resolve_path(copy_path) == copy_path


def test_resolve_unknown_name_lists_the_bundled_specs():
    with pytest.raises(SpecError) as caught:
        specs.resolve_path("tetris")
    message = str(caught.value)
    assert "No spec file 'tetris'" in message and "bundled specs: nova" in message


def test_resolve_missing_path_lists_the_bundled_specs(tmp_path):
    with pytest.raises(SpecError) as caught:
        specs.resolve_path(str(tmp_path / "absent.json"))
    assert "absent.json" in str(caught.value) and "nova" in str(caught.value)
    with pytest.raises(SpecError, match="No spec file"):
        specs.resolve_path("nowhere/spec")                              # a separator means a path, not a bundled name


def test_resolve_from_the_environment_and_from_the_ears_home(tmp_path, monkeypatch):
    monkeypatch.delenv("EARS_SPEC", raising=False)
    with pytest.raises(SpecError) as caught:
        specs.resolve_path(None)
    assert "EARS_SPEC is unset" in str(caught.value) and "<ears home>/spec.json" in str(caught.value) and "nova" in str(caught.value)
    with pytest.raises(SpecError) as caught:
        specs.resolve_path(None, home=tmp_path)
    assert str(tmp_path / "spec.json") in str(caught.value)
    (tmp_path / "spec.json").write_text("{}")
    assert specs.resolve_path(None, home=tmp_path) == tmp_path / "spec.json"
    monkeypatch.setenv("EARS_SPEC", "nova")
    assert specs.resolve_path(None, home=tmp_path) == specs.BUNDLED_DIR / "nova.spec.json"      # the variable wins over the home
    monkeypatch.setenv("EARS_SPEC", "tetris")
    with pytest.raises(SpecError, match="No spec file 'tetris'"):
        specs.resolve_path(None)


def test_load_accepts_names_paths_dicts_and_specs(tmp_path, monkeypatch, nova):
    monkeypatch.delenv("EARS_SPEC", raising=False)
    assert specs.load("nova").name == "nova"
    assert specs.load(nova) is nova
    from_dict = specs.load(clip_layout_data())
    assert from_dict.name == "clipset" and from_dict.path is None
    path = tmp_path / "custom.spec.json"
    path.write_text(json.dumps(clip_layout_data()))
    assert specs.load(str(path)).path == str(path)
    renamed = clip_layout_data()
    del renamed["name"]
    path.write_text(json.dumps(renamed))
    assert specs.load(str(path)).name == "custom"                       # the file stem before the first dot
    assert Spec(renamed).name == "spec"                                 # no name, no path
    monkeypatch.setenv("EARS_SPEC", str(path))
    assert specs.load().name == "custom"
    (tmp_path / "spec.json").write_text(json.dumps(clip_layout_data()))
    monkeypatch.delenv("EARS_SPEC")
    assert specs.load(None, home=tmp_path).name == "clipset"


def test_load_reports_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ not json")
    with pytest.raises(SpecError, match="is not valid JSON"):
        specs.load(str(path))


# ---------------------------------------------------------------------------
# SpecError cases
# ---------------------------------------------------------------------------


def with_changes(**changes):
    data = clip_layout_data()
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def test_unknown_stem_in_a_tier_is_a_spec_error():
    data = clip_layout_data()
    data["tiers"]["T2"] = ["kick", "theremin"]
    with pytest.raises(SpecError, match="Tier T2 names unknown stem 'theremin'"):
        Spec(data)


def test_unknown_progression_in_a_set_is_a_spec_error():
    data = clip_layout_data()
    data["sets"]["demo"]["variations"]["B"] = "Z"
    with pytest.raises(SpecError, match=r"Set 'demo' variation B plays unknown progression 'Z'"):
        Spec(data)


@pytest.mark.parametrize("changes, message", [
    ({"key": None}, "no key"),
    ({"key": "H minor"}, "Not a note name"),
    ({"key": "A dorian"}, "Unsupported mode"),
    ({"stems": {}}, "defines no stems"),
    ({"stems": None}, "defines no stems"),
    ({"sets": {}}, "defines no sets"),
    ({"sets": None}, "defines no sets"),
    ({"meter": "four-four"}, "meter must look like"),
    ({"meter": "4"}, "meter must look like"),
])
def test_malformed_specs_raise_spec_error(changes, message):
    with pytest.raises(SpecError, match=message):
        Spec(with_changes(**changes))


def test_a_set_without_tempos_has_no_middle_tempo():
    data = clip_layout_data()
    data["sets"]["demo"]["tempos"] = []
    with pytest.raises(SpecError, match="lists no tempos"):
        Spec(data).middle_tempo("demo")


def test_meter_other_than_four_four_sets_beats_per_bar():
    spec = Spec(with_changes(meter="3/4"))
    assert spec.beats_per_bar == 3.0 and spec.bar_seconds(120) == pytest.approx(1.5)
    assert Spec(with_changes(meter="6/8")).beats_per_bar == 3.0           # Live beats are quarter notes


def test_a_spec_file_that_is_not_a_json_object_is_a_spec_error(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(SpecError):
        specs.load(str(path))


def test_a_stem_without_bars_is_a_spec_error():
    data = clip_layout_data()
    del data["stems"]["kick"]["bars"]
    with pytest.raises(SpecError):
        Spec(data).parts("demo")


# ---------------------------------------------------------------------------
# Keys and note names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    ("A minor", ("A", 9, "minor")),
    ("Am", ("A", 9, "minor")),
    ("A natural minor", ("A", 9, "minor")),
    ("a minor", ("a", 9, "minor")),
    ("A MINOR", ("A", 9, "minor")),
    ("A min", ("A", 9, "minor")),
    ("A aeolian", ("A", 9, "minor")),
    ("  A   minor ", ("A", 9, "minor")),
    ("C major", ("C", 0, "major")),
    ("C", ("C", 0, "major")),
    ("C maj", ("C", 0, "major")),
    ("C ionian", ("C", 0, "major")),
    ("F#m", ("F#", 6, "minor")),
    ("F# minor", ("F#", 6, "minor")),
    ("Bbm", ("Bb", 10, "minor")),
    ("Bb minor", ("Bb", 10, "minor")),
    ("E♭ major", ("E♭", 3, "major")),
    ("G♯ minor", ("G♯", 8, "minor")),
])
def test_parse_key_variants(text, expected):
    assert specs.parse_key(text) == expected


@pytest.mark.parametrize("text, message", [
    ("", "Empty key"), ("   ", "Empty key"), ("H minor", "Not a note name"), ("x", "Not a note name"),
    ("A dorian", "Unsupported mode 'dorian'"), ("A mixolydian", "Unsupported mode"), ("Amin7", "Not a note name"),
])
def test_parse_key_rejects(text, message):
    with pytest.raises(SpecError, match=message):
        specs.parse_key(text)


@pytest.mark.parametrize("name, value", [
    ("C", 0), ("C#", 1), ("Db", 1), ("D", 2), ("D#", 3), ("Eb", 3), ("E", 4), ("F", 5), ("F#", 6), ("G", 7), ("G#", 8), ("Ab", 8),
    ("A", 9), ("A#", 10), ("Bb", 10), ("B", 11), ("B#", 0), ("Cb", 11), ("G♯", 8), ("B♭", 10), ("e", 4), ("db", 1), ("F##", 7), ("Gbb", 5),
])
def test_pitch_class(name, value):
    assert specs.pitch_class(name) == value


@pytest.mark.parametrize("bad", ["", "H", "Ax", "#", None, "12", "A#x"])
def test_pitch_class_rejects(bad):
    with pytest.raises(SpecError, match="Not a note name"):
        specs.pitch_class(bad)


def test_the_scale_of_the_key_follows_the_mode():
    assert Spec(with_changes(key="C major")).scale == frozenset({0, 2, 4, 5, 7, 9, 11})
    assert Spec(with_changes(key="C minor")).scale == frozenset({0, 2, 3, 5, 7, 8, 10})
    assert Spec(with_changes(key="F#m")).scale == frozenset((6 + step) % 12 for step in specs.MODES["minor"])
