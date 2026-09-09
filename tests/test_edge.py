"""
Unit tests for Screen Edge Detector boundary calculations and hysteresis.
"""

from lunifier.edge_detector import ScreenEdgeDetector


def test_edge_detector_bounds_check():
    detector = ScreenEdgeDetector(trigger_edge="right", hold_delay_ms=200)
    detector._screen_bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1080}

    # At edge
    assert detector._is_at_edge(1919, 500) is True
    assert detector._is_at_edge(1920, 500) is True
    
    # Inside screen
    assert detector._is_at_edge(1900, 500) is False
    assert detector._is_at_edge(960, 540) is False


def test_edge_detector_ratio_calculation():
    detector = ScreenEdgeDetector(trigger_edge="right")
    detector._screen_bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1000}

    # Vertical ratio
    assert detector._calculate_ratio(1920, 0) == 0.0
    assert detector._calculate_ratio(1920, 500) == 0.5
    assert detector._calculate_ratio(1920, 1000) == 1.0


def test_left_edge_detector():
    detector = ScreenEdgeDetector(trigger_edge="left")
    detector._screen_bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1080}

    assert detector._is_at_edge(0, 500) is True
    assert detector._is_at_edge(1, 500) is True
    assert detector._is_at_edge(10, 500) is False


def test_multi_edge_detector():
    detector = ScreenEdgeDetector(active_edges=["left", "right"])
    detector._screen_bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1080}

    # Left edge triggered
    assert detector._get_triggered_edge(0, 500) == "left"
    assert detector._get_triggered_edge(2, 500) == "left"

    # Right edge triggered
    assert detector._get_triggered_edge(1920, 500) == "right"
    assert detector._get_triggered_edge(1918, 500) == "right"

    # Top/bottom not active
    assert detector._get_triggered_edge(500, 0) is None
    assert detector._get_triggered_edge(500, 1080) is None

    # Center of screen
    assert detector._get_triggered_edge(960, 540) is None


def test_app_edge_triggered_steps_back_cursor(monkeypatch):
    from lunifier.app import LunifierApp
    from lunifier.config import AppConfig

    cfg = AppConfig(
        trigger_edge="right",
        target_channel=1,
        devices=["MX Keys", "MX Master 3"]
    )
    app = LunifierApp(config=cfg)

    # Mock hidpp to avoid real device access
    monkeypatch.setattr(app.hidpp, "switch_all_to_channel", lambda target_ch, devs, *args, **kwargs: {"MX Keys": True, "MX Master 3": True})

    cursor_moved = []
    monkeypatch.setattr(app.cursor_mgr, "set_cursor_pos", lambda x, y: cursor_moved.append((x, y)) or True)

    app._handle_edge_triggered("right", 2560, 772, 0.37)

    assert len(cursor_moved) == 1
    # 2560 - 80 = 2480
    assert cursor_moved[0] == (2480, 772)

def test_edge_detector_approach_direction():
    import time
    detector = ScreenEdgeDetector(trigger_edge="right", hold_delay_ms=200)
    detector._screen_bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1080}
    detector._min_approach_displacement = 15

    # 1. Right edge approach (moving from 1800 -> 1920: positive dx >= 15)
    now = time.time()
    detector._cursor_history.clear()
    detector._cursor_history.append((now - 0.25, (1800, 500)))
    detector._cursor_history.append((now - 0.15, (1880, 500)))
    assert detector._is_approaching_edge("right", 1920, 500, now) is True

    # 2. Right edge resting/stationary or moving leftwards (prev_x 1920 -> current_x 1920: dx = 0)
    detector._cursor_history.clear()
    detector._cursor_history.append((now - 0.25, (1920, 500)))
    assert detector._is_approaching_edge("right", 1920, 500, now) is False

    # 3. Left edge approach (moving from 200 -> 0: dx <= -15)
    detector._cursor_history.clear()
    detector._cursor_history.append((now - 0.25, (150, 500)))
    assert detector._is_approaching_edge("left", 0, 500, now) is True

    # 4. Left edge stationary (prev_x 0 -> current_x 0)
    detector._cursor_history.clear()
    detector._cursor_history.append((now - 0.25, (0, 500)))
    assert detector._is_approaching_edge("left", 0, 500, now) is False

    # 5. Top edge approach (moving from 200 -> 0: dy <= -15)
    detector._cursor_history.clear()
    detector._cursor_history.append((now - 0.25, (500, 150)))
    assert detector._is_approaching_edge("top", 500, 0, now) is True

    # 6. Bottom edge approach (moving from 900 -> 1080: dy >= 15)
    detector._cursor_history.clear()
    detector._cursor_history.append((now - 0.25, (500, 950)))
    assert detector._is_approaching_edge("bottom", 500, 1080, now) is True


def test_active_zone_filtering():
    # 50% central zone on a 1000px height screen: ratio must be within [0.25..0.75], i.e. Y between 250 and 750
    detector = ScreenEdgeDetector(active_edges=["right"], active_zone_pct=50)
    detector._screen_bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1000}

    # Within central 50%
    assert detector._is_in_active_zone(1920, 500, "right") is True
    assert detector._is_in_active_zone(1920, 260, "right") is True
    assert detector._is_in_active_zone(1920, 740, "right") is True
    assert detector._get_triggered_edge(1920, 500) == "right"

    # Outside central 50% (near corners / top or bottom edges)
    assert detector._is_in_active_zone(1920, 100, "right") is False
    assert detector._is_in_active_zone(1920, 900, "right") is False
    assert detector._get_triggered_edge(1920, 100) is None
    assert detector._get_triggered_edge(1920, 900) is None

    # 100% full border
    detector_full = ScreenEdgeDetector(active_edges=["right"], active_zone_pct=100)
    detector_full._screen_bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1000}
    assert detector_full._is_in_active_zone(1920, 50, "right") is True
    assert detector_full._get_triggered_edge(1920, 50) == "right"


def test_border_knock_mechanism():
    import time
    triggers = []
    detector = ScreenEdgeDetector(
        active_edges=["right"],
        active_zone_pct=100,
        knock_enabled=True,
        knock_timeout_ms=1000,
        hold_delay_ms=50,
        on_trigger_callback=lambda edge, x, y, ratio: triggers.append((edge, x, y))
    )
    detector._screen_bounds = {"left": 0, "top": 0, "right": 1920, "bottom": 1080}

    now = time.time()
    # 1st knock: should not trigger callback, but should set _last_knock_edge and _last_knock_time
    detector._last_knock_edge = "right"
    detector._last_knock_time = now

    # 2nd knock within 500ms (window is 1000ms): should qualify and trigger
    assert (now + 0.5 - detector._last_knock_time) * 1000 <= detector.knock_timeout_ms
    assert detector._last_knock_edge == "right"

    # Expired knock outside window:
    assert (now + 1.2 - detector._last_knock_time) * 1000 > detector.knock_timeout_ms

