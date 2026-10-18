from povforge.overlay.playerbar import PlayerBarRenderer
from povforge.timeline import HudState


def test_bar_covers_the_spectator_panel():
    r = PlayerBarRenderer()
    im = r.image(HudState(alive=True, health=100, armor=100, ammo=30, reserve=90), 3, (True, False))
    assert im.size == (820, 104)
    # solid in the middle (hides the panel underneath), see-through at the far edges
    assert im.getpixel((410, 90))[3] > 240
    assert im.getpixel((0, 90))[3] == 0


def test_bar_changes_with_kills_and_is_cached():
    r = PlayerBarRenderer()
    st = HudState(alive=True, health=50, armor=0, ammo=5, reserve=10)
    a, b = r.render(st, 2, ()), r.render(st, 2, (True,))
    assert a != b
    assert r.render(st, 2, (True,)) is b


def test_dead_player_gets_only_the_cover():
    r = PlayerBarRenderer()
    assert r.render(HudState(alive=False), 3, ()) == r._cover.tobytes()
