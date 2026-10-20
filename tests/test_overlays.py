from PIL import Image

from povforge.maps import MapInfo
from povforge.overlay.minimap import MinimapRenderer


def test_minimap_of_a_radar_that_fills_the_image(tmp_path):
    """The square around the map reaches past the image edge; Pillow 12 refuses a
    crop box like that, which stopped whole-match recordings at the minimap."""
    radar = tmp_path / "de_test_radar_psd.png"
    Image.new("RGBA", (1024, 1024), (90, 90, 90, 255)).save(radar)   # map right to the edges
    m = MinimapRenderer(MapInfo("de_test", -2000, 2000, 4.0), radar, size=200)
    assert m.crop[0] < 0                                                # it does reach past the edge
    base = m._bases[False]
    assert base.size == (200, 200)
    # the map is in the middle, the border it was padded with is see-through
    assert base.getpixel((100, 100))[3] > 0
