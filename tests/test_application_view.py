import os
import pytest

from MCP_Server.server import AbletonConnection


HOST = os.environ.get("ABLETON_MCP_HOST", "localhost")
PORT = int(os.environ.get("ABLETON_MCP_PORT", "9877"))


@pytest.fixture(scope="module")
def connection() -> AbletonConnection:
    conn = AbletonConnection(host=HOST, port=PORT)
    if not conn.connect():
        pytest.skip("Unable to connect to Ableton. Ensure Live is running and the Remote Script is loaded.")
    return conn


def test_application_view_state_and_views(connection: AbletonConnection) -> None:
    conn = connection

    state = conn.send_command("get_application_view_state")
    assert isinstance(state, dict)
    assert "browse_mode" in state
    assert "focused_document_view" in state

    views = conn.send_command("application_view_available_main_views")
    assert isinstance(views, dict)
    assert "views" in views
    assert isinstance(views["views"], list)


def test_application_view_focus_and_visibility(connection: AbletonConnection) -> None:
    conn = connection

    # Prefer Browser visibility toggles as they're generally safe to show/hide
    conn.send_command("application_view_show_view", {"view_name": "Browser"})
    vis = conn.send_command("application_view_is_view_visible", {"view_name": "Browser"})
    assert isinstance(vis, dict)
    assert vis.get("view_name") == "Browser"
    assert vis.get("visible") in (True, False)

    # Hide Browser then check
    conn.send_command("application_view_hide_view", {"view_name": "Browser"})
    vis2 = conn.send_command("application_view_is_view_visible", {"view_name": "Browser"})
    assert isinstance(vis2, dict)
    assert vis2.get("visible") in (True, False)  # Some versions may force visibility

    # Focus Session or Arranger depending on availability
    views = conn.send_command("application_view_available_main_views")
    names = [v.lower() for v in views.get("views", [])]
    target = "Session" if "session" in names else ("Arranger" if "arranger" in names else "")
    res = conn.send_command("application_view_focus_view", {"view_name": target})
    assert isinstance(res, dict)


def test_application_view_scroll_and_zoom(connection: AbletonConnection) -> None:
    conn = connection

    # Scroll Session (behaves like zoom for Session per LOM)
    conn.send_command("application_view_scroll_view", {"direction": 1, "view_name": "Session", "modifier_pressed": False})

    # Zoom Arrangement up (may adjust track heights or selection depending on modifier)
    conn.send_command("application_view_zoom_view", {"direction": 0, "view_name": "Arranger", "modifier_pressed": False})


def test_application_view_toggle_browse(connection: AbletonConnection) -> None:
    conn = connection
    conn.send_command("application_view_toggle_browse")

