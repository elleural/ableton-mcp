import os
import json
from typing import Dict, Any, List

import pytest

from MCP_Server.server import AbletonConnection


HOST = os.environ.get("ABLETON_MCP_HOST", "localhost")
PORT = int(os.environ.get("ABLETON_MCP_PORT", "9877"))


@pytest.fixture(scope="module")
def connection() -> AbletonConnection:
    conn = AbletonConnection(host=HOST, port=PORT)
    if not conn.connect():
        pytest.skip(
            "Unable to connect to Ableton. Ensure Live is running and the "
            "AbletonMCP Remote Script is loaded."
        )
    # Try a simple call to ensure the Remote Script is responsive
    try:
        conn.send_command("get_session_info")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Remote Script not responding: {exc}")
    return conn


def _ensure_clean_state(conn: AbletonConnection) -> None:
    """
    Best-effort to create a deterministic baseline without requiring
    destructive operations.
    """
    try:
        conn.send_command("stop_all_clips", {"quantized": 0})
    except Exception:  # noqa: BLE001
        pass
    try:
        conn.send_command("stop_playback")
    except Exception:  # noqa: BLE001
        pass
    try:
        conn.send_command("set_loop", {"on": False})
    except Exception:  # noqa: BLE001
        pass
    try:
        conn.send_command("clear_arrangement")
    except Exception:  # noqa: BLE001
        # Older scripts may require explicit param
        pass


def test_create_song_from_scratch_flow(connection: AbletonConnection) -> None:
    conn = connection
    _ensure_clean_state(conn)

    # Set tempo
    result = conn.send_command("set_tempo", {"tempo": 120.0})
    assert isinstance(result, dict)

    # Create a MIDI track
    track = conn.send_command("create_midi_track", {"index": -1})
    assert isinstance(track, dict)

    # Create a 4-beat clip in first slot of first track
    clip_create = conn.send_command(
        "create_clip",
        {"track_index": 0, "clip_index": 0, "length": 4.0},
    )
    assert isinstance(clip_create, dict)

    # Add a single C4 note, 1 beat duration
    notes: List[Dict[str, Any]] = [
        {
            "pitch": 60,
            "start_time": 0.0,
            "duration": 1.0,
            "velocity": 100,
            "mute": False,
        }
    ]
    add_notes = conn.send_command(
        "add_notes_to_clip",
        {"track_index": 0, "clip_index": 0, "notes": notes},
    )
    assert isinstance(add_notes, dict)

    # Name the clip
    set_name = conn.send_command(
        "set_clip_name",
        {"track_index": 0, "clip_index": 0, "name": "Test Clip"},
    )
    assert isinstance(set_name, dict)


def test_application_info_and_version(connection: AbletonConnection) -> None:
    conn = connection
    info = conn.send_command("get_application_info")
    assert isinstance(info, dict)
    assert "control_surface_count" in info
    assert "average_process_usage" in info

    proc = conn.send_command("get_application_process_usage")
    assert isinstance(proc, dict)
    assert "average_process_usage" in proc
    assert "peak_process_usage" in proc

    version = conn.send_command("get_application_version")
    assert isinstance(version, dict)
    # version fields may be None depending on Live/permissions, but keys should exist
    for key in ["version_string", "major", "minor", "bugfix"]:
        assert key in version

    document = conn.send_command("get_application_document")
    assert isinstance(document, dict)
    assert "track_count" in document
    assert "scene_count" in document


def _assert_duplicate_result_shape(result: Dict[str, Any]) -> None:
    # Check minimal expected structure and types
    # These keys are expected per README and server intent
    for key in [
        "track_index",
        "arrangement_clip_index",
        "start_time",
        "end_time",
        "looping",
        "loop_start",
        "loop_end",
    ]:
        assert key in result, f"Missing key in result: {key}"

    assert isinstance(result["track_index"], int)
    # arrangement_clip_id can be None depending on Live version; index should be stable
    assert isinstance(result["arrangement_clip_index"], int)
    assert result["arrangement_clip_index"] >= 0


def _fetch_clip_info(conn: AbletonConnection, track_index: int, clip_index: int) -> Dict[str, Any]:
    info = conn.send_command("get_clip_info", {
        "track_index": track_index,
        "clip_index": clip_index
    })
    assert isinstance(info, dict)
    return info
    assert isinstance(result["start_time"], (int, float))
    assert isinstance(result["end_time"], (int, float))
    assert isinstance(result["looping"], bool)
    assert isinstance(result["loop_start"], (int, float))
    assert isinstance(result["loop_end"], (int, float))


def test_duplicate_track_clip_to_arrangement_loop_true(
    connection: AbletonConnection,
) -> None:
    conn = connection
    # Precondition: a clip exists at track 0, slot 0 from the previous test
    res = conn.send_command(
        "duplicate_track_clip_to_arrangement",
        {
            "track_index": 0,
            "clip_index": 0,
            "start_beats": 32.0,
            "length_beats": 16.0,
            "loop": True,
        },
    )
    assert isinstance(res, dict)
    _assert_duplicate_result_shape(res)

    # Basic invariants
    assert res["track_index"] == 0
    assert res["looping"] is True

    # Verify multi-segment coverage when length > unit length
    debug = res.get("debug", {})
    post = debug.get("post", {})
    snapshot = debug.get("track_arrangement_snapshot", [])
    created_count = int(debug.get("created_count", 1))
    unit_len = float(debug.get("source_unit_length", 4.0)) if debug.get("source_unit_length") is not None else 4.0
    expected_segments = int(16.0 / unit_len)

    # Emit helpful debug info (use `pytest -s` to see during success)
    print("DUP_LOOP_TRUE result:\n" + json.dumps(res, indent=2))
    if snapshot:
        print("DUP_LOOP_TRUE track snapshot:\n" + json.dumps(snapshot, indent=2))

    assert created_count >= expected_segments
    if post:
        # The first segment loops over its unit length
        assert abs(float(post.get("loop_end", 0.0)) - unit_len) < 1e-6
        assert abs(float(post.get("loop_start", 0.0)) - 0.0) < 1e-6

    region = [s for s in snapshot if s.get("start_time") and s["start_time"] >= 32.0 - 1e-6]
    region_sorted = sorted(region, key=lambda s: s["start_time"])[:expected_segments]
    # Segments should be contiguous and each segment length == unit_len
    for idx, s in enumerate(region_sorted):
        assert abs(s["start_time"] - (32.0 + idx * unit_len)) < 1e-6
        assert abs(float(s.get("length", 0.0)) - unit_len) < 1e-6
        assert s.get("looping") is True


def test_duplicate_track_clip_to_arrangement_loop_false(
    connection: AbletonConnection,
) -> None:
    conn = connection
    res = conn.send_command(
        "duplicate_track_clip_to_arrangement",
        {
            "track_index": 0,
            "clip_index": 0,
            "start_beats": 64.0,
            "length_beats": 8.0,
            "loop": False,
        },
    )
    assert isinstance(res, dict)
    _assert_duplicate_result_shape(res)

    # If this assertion fails, the implementation likely ignores the 'loop'
    # parameter, which is a known area to re-check.
    assert res["looping"] is False, (
        "Expected looping False when 'loop' parameter is False"
    )

    # Verify non-looping state in debug post
    post = res.get("debug", {}).get("post", {})
    snapshot = res.get("debug", {}).get("track_arrangement_snapshot", [])
    print("DUP_LOOP_FALSE result:\n" + json.dumps(res, indent=2))
    if snapshot:
        print("DUP_LOOP_FALSE track snapshot:\n" + json.dumps(snapshot, indent=2))
    if post:
        assert post.get("looping") is False


def test_duplicate_long_loop_into_arrangement(connection: AbletonConnection) -> None:
    conn = connection
    # Duplicate the same source clip across 32 beats with looping enabled
    length_beats = 32.0
    res = conn.send_command(
        "duplicate_track_clip_to_arrangement",
        {
            "track_index": 0,
            "clip_index": 0,
            "start_beats": 96.0,
            "length_beats": length_beats,
            "loop": True,
        },
    )
    assert isinstance(res, dict)
    _assert_duplicate_result_shape(res)

    debug = res.get("debug", {})
    created_count = int(debug.get("created_count", 1))
    unit_len = float(debug.get("source_unit_length", 4.0)) if debug.get("source_unit_length") is not None else 4.0
    expected_segments = int(length_beats / unit_len)
    # Expect multiple segments for long duplication
    assert created_count >= expected_segments

    snapshot = debug.get("track_arrangement_snapshot", [])
    # Filter snapshot to the region we just duplicated
    region = [s for s in snapshot if s.get("start_time") and s["start_time"] >= 96.0 - 1e-6]
    # At least expected number of segments present
    assert len(region) >= expected_segments
    # Verify contiguous layout and per-clip local length equals unit length
    region_sorted = sorted(region, key=lambda s: s["start_time"])
    for idx, s in enumerate(region_sorted[:expected_segments]):
        assert abs(s["start_time"] - (96.0 + idx * unit_len)) < 1e-6
        assert abs(float(s.get("length", 0.0)) - unit_len) < 1e-6
        assert s.get("looping") is True
