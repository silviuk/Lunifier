"""
Unit tests for multi-monitor geometry, layout normalization, and edge detection.
"""
import pytest
from lunifier.monitors import MonitorInfo, get_monitor_for_point, get_virtual_desktop_bounds
from lunifier.edge_detector import ScreenEdgeDetector
from lunifier.config import AppConfig


def test_monitor_info_geometry():
    # Primary 1080p monitor at (0, 0)
    m1 = MonitorInfo(id=0, index=0, left=0, top=0, right=1920, bottom=1080, primary=True)
    assert m1.width == 1920
    assert m1.height == 1080
    assert m1.contains_point(100, 100) is True
    assert m1.contains_point(1920, 1080) is True
    assert m1.contains_point(-5, 500) is False
    assert m1.contains_point(2000, 500) is False

    # Secondary 4K monitor at (1920, 0)
    m2 = MonitorInfo(id=1, index=1, left=1920, top=0, right=5760, bottom=2160, primary=False)
    assert m2.width == 3840
    assert m2.height == 2160
    assert m2.contains_point(1920, 0) is True
    assert m2.contains_point(3000, 1000) is True
    assert m2.contains_point(5760, 2160) is True
    assert m2.contains_point(1915, 500) is False


def test_get_monitor_for_point():
    m1 = MonitorInfo(id=0, index=0, left=0, top=0, right=1920, bottom=1080, primary=True)
    m2 = MonitorInfo(id=1, index=1, left=1920, top=0, right=3840, bottom=1080, primary=False)
    monitors = [m1, m2]

    assert get_monitor_for_point(monitors, 500, 500) == m1
    assert get_monitor_for_point(monitors, 1920, 500) == m1  # right border of m1
    assert get_monitor_for_point(monitors, 2500, 500) == m2
    assert get_monitor_for_point(monitors, 3840, 500) == m2


def test_virtual_desktop_bounds():
    # Side-by-side monitors: 1080p and 1440p
    m1 = MonitorInfo(id=0, index=0, left=0, top=0, right=1920, bottom=1080, primary=True)
    m2 = MonitorInfo(id=1, index=1, left=1920, top=-200, right=4480, bottom=1240, primary=False)
    bounds = get_virtual_desktop_bounds([m1, m2])

    assert bounds["left"] == 0
    assert bounds["top"] == -200
    assert bounds["right"] == 4480
    assert bounds["bottom"] == 1240


def test_monitor_ratio_calculation():
    m = MonitorInfo(id=1, index=1, left=1920, top=100, right=3840, bottom=1180, primary=False)
    # Width: 1920, Height: 1080
    # Vertical edge ratios (top to bottom: 100 to 1180)
    assert m.calculate_ratio(1920, 100, "left") == 0.0
    assert m.calculate_ratio(1920, 640, "left") == 0.5
    assert m.calculate_ratio(1920, 1180, "left") == 1.0

    # Horizontal edge ratios (left to right: 1920 to 3840)
    assert m.calculate_ratio(1920, 100, "top") == 0.0
    assert m.calculate_ratio(2880, 100, "top") == 0.5
    assert m.calculate_ratio(3840, 100, "top") == 1.0


def test_multi_monitor_edge_detection():
    # Two monitors:
    # Monitor 0: 0..1920, 0..1080 (Primary)
    # Monitor 1: 1920..3840, 0..1080
    m0 = MonitorInfo(id=0, index=0, left=0, top=0, right=1920, bottom=1080, primary=True)
    m1 = MonitorInfo(id=1, index=1, left=1920, top=0, right=3840, bottom=1080, primary=False)

    monitor_configs = {
        "0": {
            "enabled": True,
            "edges": {"left": 1, "right": None, "top": None, "bottom": None}
        },
        "1": {
            "enabled": True,
            "edges": {"left": None, "right": 2, "top": None, "bottom": None}
        }
    }

    detector = ScreenEdgeDetector(
        monitor_configs=monitor_configs,
        active_zone_pct=100
    )
    detector.monitors = [m0, m1]

    # Cursor on Left border of Monitor 0 -> should trigger left for Channel 1
    res0 = detector._get_triggered_edge_info(0, 500)
    assert res0 is not None
    edge0, ratio0, mid0, ch0 = res0
    assert edge0 == "left"
    assert mid0 == "0"
    assert ch0 == 1

    # Cursor on Right border of Monitor 0 -> configured as None, should not trigger
    res_mid = detector._get_triggered_edge_info(1920, 500)
    assert res_mid is None

    # Cursor on Right border of Monitor 1 -> should trigger right for Channel 2
    res1 = detector._get_triggered_edge_info(3840, 500)
    assert res1 is not None
    edge1, ratio1, mid1, ch1 = res1
    assert edge1 == "right"
    assert mid1 == "1"
    assert ch1 == 2


def test_multi_monitor_disabled_monitor():
    m0 = MonitorInfo(id=0, index=0, left=0, top=0, right=1920, bottom=1080, primary=True)
    m1 = MonitorInfo(id=1, index=1, left=1920, top=0, right=3840, bottom=1080, primary=False)

    monitor_configs = {
        "0": {
            "enabled": True,
            "edges": {"left": 1, "right": None, "top": None, "bottom": None}
        },
        "1": {
            "enabled": False,  # Disabled
            "edges": {"left": None, "right": 2, "top": None, "bottom": None}
        }
    }

    detector = ScreenEdgeDetector(
        monitor_configs=monitor_configs,
        active_zone_pct=100
    )
    detector.monitors = [m0, m1]

    # Monitor 1 right edge should be ignored since monitor is disabled
    res = detector._get_triggered_edge_info(3840, 500)
    assert res is None


def test_config_monitor_backward_compatibility():
    cfg = AppConfig()
    cfg.edge_channels = {"left": 1, "right": 2, "top": None, "bottom": None}

    # Should automatically initialize/fallback for Monitor 0
    m0_cfg = cfg.get_monitor_config("0")
    assert m0_cfg["enabled"] is True
    assert m0_cfg["edges"]["left"] == 1
    assert m0_cfg["edges"]["right"] == 2

    # Setting config on monitor 0 should update legacy edge_channels
    cfg.set_monitor_config("0", True, {"left": None, "right": 3, "top": None, "bottom": None})
    assert cfg.edge_channels["right"] == 3
    assert cfg.edge_channels["left"] is None

    # Multi-monitor active borders list
    cfg.set_monitor_config("1", True, {"left": 1, "right": None, "top": None, "bottom": None})
    active_borders = cfg.get_all_active_monitor_borders()
    # Monitor 0 right->3, Monitor 1 left->1
    assert ("0", "right", 3) in active_borders
    assert ("1", "left", 1) in active_borders
