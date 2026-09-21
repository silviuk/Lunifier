"""
Unit tests for Scalable Vector Graphics Icon Pipeline in Lunifier.
"""

from unittest.mock import MagicMock
from PIL import Image
from lunifier.icons import (
    render_scalable_icon,
    get_icon_pil,
    get_icon_ctk,
    set_window_icon
)


def test_render_scalable_icon_dimensions():
    for size in [16, 24, 32, 48, 64, 128, 256]:
        img = render_scalable_icon(size)
        assert isinstance(img, Image.Image)
        assert img.size == (size, size)
        assert img.mode == "RGBA"


def test_get_icon_pil_caching():
    img1 = get_icon_pil(size=48)
    img2 = get_icon_pil(size=48)
    assert img1.size == (48, 48)
    assert img2.size == (48, 48)


def test_get_icon_ctk():
    ctk_img = get_icon_ctk(size=(32, 32))
    assert ctk_img is not None
    assert getattr(ctk_img, "_size", None) == (32, 32)


def test_set_window_icon():
    mock_window = MagicMock()
    set_window_icon(mock_window)
    # Ensure either iconphoto or iconbitmap was called
    assert mock_window.iconphoto.called or mock_window.iconbitmap.called
