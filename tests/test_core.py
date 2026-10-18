"""Unit tests that need no demo file: python -m unittest discover tests"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from povforge.compose import ComposeSettings, chapters, overlay_command, safe_filename
from povforge.config import load_config
from povforge.demo import decode_buttons, find_player
from povforge.maps import map_info_from_text, parse_keyvalues
from povforge.model import Death, Plan, Player, Round, Segment
from povforge.overlay.keyboard import KeyboardRenderer
from povforge.pipeline import parse_rounds
from povforge.planner import PlanOptions, build_rounds, plan_segments
from povforge.timeline import Track, frame_count, frame_to_tick

ME = "765611980000000001"
OTHER = "765611980000000002"


class BuildRounds(unittest.TestCase):
    def test_skips_warmup_and_pairs_ends(self):
        rounds = build_rounds([100, 1000, 2000], [50, 900, 1500, 2600], match_start_tick=1000, last_tick=3000)
        self.assertEqual(rounds, [Round(1, 1000, 1500), Round(2, 2000, 2600)])

    def test_cut_off_demo_ends_at_last_tick(self):
        rounds = build_rounds([10, 500], [300], 0, 800)
        self.assertEqual(rounds[-1], Round(2, 500, 800))

    def test_restart_without_round_end_is_dropped(self):
        rounds = build_rounds([10, 200, 500], [400, 900], 0, 1000)
        self.assertEqual([r.freeze_end_tick for r in rounds], [200, 500])


class PlanSegments(unittest.TestCase):
    rounds = [Round(1, 1000, 3000), Round(2, 4000, 6000), Round(3, 7000, 9000)]

    def plan(self, deaths, **kw):
        opts = PlanOptions(pre_roll_seconds=0, post_death_seconds=1, post_round_seconds=2, min_segment_seconds=0)
        return plan_segments(self.rounds, deaths, ME, 64, 10000, opts, **kw)

    def test_death_cuts_the_round(self):
        segs = self.plan([Death(2000, ME, OTHER, "ak47"), Death(2500, OTHER, ME, "ak47")])
        self.assertEqual(segs[0], Segment(1, 1000, 2064, "death"))
        self.assertEqual(segs[1], Segment(2, 4000, 6128, "round_end"))

    def test_exit_frag_after_round_end(self):
        segs = self.plan([Death(3050, ME, OTHER, "ak47")])
        self.assertEqual(segs[0], Segment(1, 1000, 3114, "round_end"))

    def test_pre_roll(self):
        opts = PlanOptions(pre_roll_seconds=3, min_segment_seconds=0)
        segs = plan_segments(self.rounds, [], ME, 64, 10000, opts)
        self.assertEqual(segs[0].start_tick, 1000 - 192)

    def test_rounds_not_played_are_skipped(self):
        segs = self.plan([], alive_at=lambda t: t < 5000)
        self.assertEqual([s.round_number for s in segs], [1, 2])


class Buttons(unittest.TestCase):
    def test_held_tap_and_minimum_length(self):
        held = np.array([0, 1, 1, 0, 0, 0, 0, 0], dtype="uint64")
        changed = np.array([0, 1, 0, 1, 0, 1, 0, 0], dtype="uint64")
        fire = decode_buttons(held, changed, min_ticks=2)["FIRE"]
        self.assertEqual(fire.astype(int).tolist(), [0, 1, 1, 0, 0, 1, 1, 0])

    def test_bits(self):
        keys = decode_buttons(np.array([8 | 512 | 65536], dtype="uint64"), min_ticks=1)
        on = sorted(k for k, v in keys.items() if v[0])
        self.assertEqual(on, ["FORWARD", "LEFT", "WALK"])


class Maps(unittest.TestCase):
    TEXT = '''// comment
    "de_nuke"
    {
        "pos_x"  "-3453"  // upper left
        "pos_y"  "2887"
        "scale"  "7"
        "verticalsections"
        {
            "default" { "AltitudeMax" "10000" "AltitudeMin" "-495" }
            "lower"   { "AltitudeMax" "-495"  "AltitudeMin" "-10000" }
        }
    }'''

    def test_parse_and_transform(self):
        self.assertIn("de_nuke", parse_keyvalues(self.TEXT))
        info = map_info_from_text("de_nuke", self.TEXT)
        self.assertEqual(info.to_radar(-3453, 2887), (0, 0))
        self.assertEqual(info.to_radar(-3453 + 700, 2887 - 1400), (100, 200))
        self.assertTrue(info.is_lower(-600))
        self.assertFalse(info.is_lower(0))


class Timeline(unittest.TestCase):
    def test_frames(self):
        self.assertEqual(frame_count(0, 640, 64, 60), 600)
        self.assertAlmostEqual(frame_to_tick(60, 1000, 64, 60), 1064)

    def test_interpolation(self):
        pos = pd.DataFrame({
            "tick": [10, 11], "steamid": [ME, ME], "X": [0.0, 10.0], "Y": [0.0, 0.0],
            "Z": [0.0, 0.0], "yaw": [350.0, 10.0], "is_alive": [True, True], "team_num": [3, 3],
        })
        st = Track(pos).player(ME, 10.5)
        self.assertAlmostEqual(st.x, 5.0)
        self.assertAlmostEqual(st.yaw % 360, 0.0, places=5)  # wraps the short way


class Misc(unittest.TestCase):
    def test_find_player(self):
        ps = [Player("1", "donk666"), Player("2", "Donkey"), Player("3", "ZywOo")]
        self.assertEqual(find_player(ps, "zywoo").steamid, "3")
        self.assertEqual(find_player(ps, "donk666").steamid, "1")
        with self.assertRaises(ValueError):
            find_player(ps, "donk")

    def test_rounds_spec(self):
        self.assertEqual(parse_rounds("1-3, 7"), {1, 2, 3, 7})
        self.assertIsNone(parse_rounds(None))

    def test_safe_filename(self):
        self.assertEqual(safe_filename('a|b*c?'), "a_b_c_")

    def test_overlay_command(self):
        cmd = overlay_command(Path("c.mp4"), {"keyboard": Path("k.mov"), "minimap": Path("m.mov")},
                              Path("o.mp4"), ComposeSettings())
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("[0:v][1:v]overlay=x=24:y=24", graph)                 # minimap, top left
        self.assertIn("[v1][2:v]overlay=x=(W-w)/2:y=H-h-140", graph)       # keyboard above the HUD
        self.assertIn("48000", cmd)                                         # same audio for every part

    def test_overlay_command_static_layers(self):
        with tempfile.TemporaryDirectory() as d:
            static = Path(d) / "s.json"
            static.write_text('{"crosshair": [[0, 1.5], [2, 3]], "scope": []}')
            cmd = overlay_command(Path("c.mp4"), {"hud": Path("h.mov"), "static": static}, Path("o.mp4"),
                                  ComposeSettings(), height=1440,
                                  static_images={"crosshair": Path("x.png"), "scope": Path("s.png")})
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertNotIn("s.png", cmd)                                      # never scoped: no scope input
        self.assertIn("enable='between(t,0,1.4999)+between(t,2,2.9999)'", graph)
        self.assertIn("[v1][2:v]overlay=x=(W-w)/2:y=H-h-0", graph)          # HUD at the very bottom

    def test_chapters(self):
        plan = Plan("d.dem", "de_dust2", 64, Player("1", "p"),
                    [Segment(1, 0, 640, "death"), Segment(2, 1000, 1320, "death")])
        self.assertEqual(chapters(plan, [10.0, 5.0]), [(0.0, 10.0, "Round 1"), (10.0, 15.0, "Round 2")])
        self.assertEqual(chapters(plan, [10.0, 5.0], intro=4.0)[0], (0.0, 4.0, "Intro"))
        self.assertEqual(chapters(plan, [10.0, 5.0], intro=4.0)[2], (14.0, 19.0, "Round 2"))

    def test_keyboard_cache(self):
        kb = KeyboardRenderer(scale=0.5)
        a = kb.render({"FORWARD": True, "FIRE": True})
        self.assertIs(a, kb.render({"FORWARD": True, "FIRE": True}))
        self.assertEqual(len(a), kb.size[0] * kb.size[1] * 4)
        self.assertNotEqual(a, kb.render({"FORWARD": True}))               # mouse button shows

    def test_hud(self):
        from povforge.overlay.hud import HudRenderer, intervals
        from povforge.timeline import HudState
        hud = HudRenderer(1920, 1.0)
        dead = hud.render(HudState(alive=False))
        alive = hud.render(HudState(alive=True, health=100, money=800, weapon="Glock-18", ammo=20, reserve=120))
        self.assertEqual(len(alive), 1920 * hud.size[1] * 4)
        self.assertNotEqual(dead, alive)
        self.assertEqual(intervals([True, True, False, True], 2.0), [(0.0, 1.0), (1.5, 2.0)])

    def test_place_names(self):
        from povforge.overlay.minimap import pretty_place
        self.assertEqual(pretty_place("BombsiteB"), "Bombsite B")
        self.assertEqual(pretty_place("TopofMid"), "Top of Mid")
        self.assertEqual(pretty_place("CTSpawn"), "CT Spawn")

    def test_hud_sampling(self):
        hud = pd.DataFrame({"tick": [10, 20], "health": [100, 40], "is_alive": [True, True],
                            "active_weapon_name": ["Smoke Grenade", "AK-47"], "active_weapon_ammo": [0, 25],
                            "total_ammo_left": [1, 90], "balance": [800, 0], "armor_value": [0, 100],
                            "has_helmet": [False, True], "is_scoped": [False, False],
                            "last_place_name": ["TSpawn", "BombsiteB"]})
        tr = Track(pd.DataFrame(columns=["tick", "steamid", "X", "Y", "Z", "yaw", "is_alive", "team_num"]),
                   None, hud)
        self.assertEqual(tr.hud(15).ammo, -1)            # grenade: no magazine
        st = tr.hud(25)
        self.assertEqual((st.health, st.ammo, st.reserve, st.helmet, st.place), (40, 25, 90, True, "BombsiteB"))

    def test_intro_card(self):
        from povforge.demo import PlayerStats, TeamStats
        from povforge.intro import IntroInfo, pretty_map, render_card
        teams = [TeamStats("team_a", 13, [PlayerStats("1", "donk666", 36, 14, 10, 151.8, 55.6, 6)]),
                 TeamStats("team_b", 10, [PlayerStats("2", "shuliZ", 21, 16, 2, 76.5, 47.6, 1)])]
        im = render_card(IntroInfo("donk666 POV", "Cache", "1", teams), (1280, 720))
        self.assertEqual(im.size, (1280, 720))
        self.assertEqual(pretty_map("de_cache"), "Cache")

    def test_config_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.toml"
            p.write_text('[output]\ndir = "out"\n[plan]\npost_death_seconds = 3\n'
                         '[overlay]\nshow_enemies = true\n[record]\nfps = 30\n')
            cfg = load_config(p)
        self.assertEqual(cfg.output_dir, Path("out"))
        self.assertEqual(cfg.plan.post_death_seconds, 3.0)
        self.assertTrue(cfg.overlay.show_enemies)
        self.assertEqual(cfg.record.fps, 30)


if __name__ == "__main__":
    unittest.main()
