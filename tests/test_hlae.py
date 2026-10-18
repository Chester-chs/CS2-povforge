"""Tests for the HLAE backend that don't need Windows or CS2."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from povforge import hlae
from povforge.model import Plan, Player, Segment

PLAN = Plan("D:/demos/match.dem", "de_dust2", 64.0, Player("76561198386265483", "donk666"),
            [Segment(1, 4747, 8029, "death"), Segment(2, 9778, 14974, "death")])


class Job(unittest.TestCase):
    def test_job_and_director(self):
        s = hlae.RecordSettings(fps=60, preroll_seconds=2, extra_setup="cl_hud_color 3; ")
        job = hlae.build_job(PLAN, PLAN.segments[1:], Path("out/raw"), s)
        self.assertEqual(job["clips"], [{"id": "r02", "start": 9778, "end": 14974}])
        self.assertEqual(job["prerollTicks"], 128)
        self.assertIn("mirv_streams record fps 60", job["setup"])
        self.assertIn("cl_hud_color 3", job["setup"])
        preset = next(c for c in job["setup"] if c.startswith("mirv_streams settings add ffmpeg"))
        self.assertIn("{QUOTE}{AFX_STREAM_PATH}\\\\video.mp4{QUOTE}", preset)
        with tempfile.TemporaryDirectory() as d:
            js = hlae.write_director(job, Path(d) / "director.js").read_text(encoding="utf-8")
        self.assertNotIn("__POVFORGE_JOB__", js)
        self.assertIn('"steamid": "76561198386265483"', js)
        if shutil.which("node"):  # the director must still be valid JavaScript
            subprocess.run(["node", "-e", f"new Function('mirv', {json.dumps(js)})"], check=True)

    def test_launch_command(self):
        cmd = hlae.launch_command(Path("C:/Tools/hlae/HLAE.exe"),
                                  Path("D:/Steam/game/bin/win64/cs2.exe"), hlae.RecordSettings())
        self.assertIn("-customLoader", cmd)
        self.assertTrue(cmd[cmd.index("-hookDllPath") + 1].endswith("AfxHookSource2.dll"))
        game = cmd[cmd.index("-cmdLine") + 1]
        for opt in ("-insecure", "-condebug", "+exec povforge_job", "-width 1920"):
            self.assertIn(opt, game)

    def test_csgo_dir(self):
        exe = Path("D:/SteamLibrary/steamapps/common/Counter-Strike Global Offensive/game/bin/win64/cs2.exe")
        self.assertEqual(hlae.csgo_dir(exe).as_posix(),
                         "D:/SteamLibrary/steamapps/common/Counter-Strike Global Offensive/game/csgo")


class Files(unittest.TestCase):
    def test_steam_libraries(self):
        with tempfile.TemporaryDirectory() as d:
            steam = Path(d)
            (steam / "steamapps").mkdir()
            (steam / "steamapps" / "libraryfolders.vdf").write_text(
                '"libraryfolders"\n{\n "0"\n {\n  "path" "C:\\\\Program Files (x86)\\\\Steam"\n'
                '  "apps" { "228980" "1" }\n }\n "1"\n {\n  "path" "D:\\\\SteamLibrary"\n'
                '  "apps" { "730" "1" }\n }\n}\n')
            libs = hlae.steam_libraries(steam)
        self.assertIn(Path("D:\\SteamLibrary"), libs)

    def test_console_log(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "console.log"
            log.write_text("junk\n[povforge] START r01 tick=4747.531\n[povforge] END r01 tick=8029.000 why=end_tick\n"
                           "10/17 01:02:03 [povforge] START r02 tick=9778.016\n")
            got = hlae.read_console_log(log)
        self.assertEqual(got, {"r01": {"START": 4747.531, "END": 8029.0}, "r02": {"START": 9778.016}})

    @unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
    def test_latest_take_and_mux(self):
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d)
            (raw / "r01" / "take0000").mkdir(parents=True)
            (raw / "r01" / "take0000" / "video.mp4").write_bytes(b"")  # failed take
            good = raw / "r01" / "take0001"
            good.mkdir()
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=64x36:r=60",
                            "-frames:v", "30", str(good / "video.mp4")], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=d=1",
                            str(good / "audio.wav")], check=True)
            self.assertEqual(hlae.latest_take(raw, "r01"), good)
            self.assertIsNone(hlae.latest_take(raw, "r02"))
            out = raw / "clip_000.mp4"
            hlae.mux_take(good, out, "ffmpeg")
            streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                                      "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout
        self.assertEqual(sorted(streams.split()), ["audio", "video"])


@unittest.skipUnless(shutil.which("node"), "needs node")
class DirectorSimulation(unittest.TestCase):
    def test_simulation(self):
        sim = Path(__file__).with_name("director_sim.js")
        r = subprocess.run(["node", str(sim)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()


def _fake_cs2_dirs(tmp_path):
    steam = tmp_path / "steam"
    ucfg = steam / "userdata" / "123" / "730" / "local" / "cfg"
    ucfg.mkdir(parents=True)
    csgo = tmp_path / "game" / "csgo"
    (csgo / "cfg").mkdir(parents=True)
    (ucfg / "cs2_user_convars_0_slot0.vcfg").write_text('"cl_spec_stats" "1"')
    (ucfg / "cs2_video.txt").write_text('"setting.defaultres" "2560"')
    (csgo / "cfg" / "boot.vcfg").write_text("boot")
    (csgo / "cfg" / "autoexec.cfg").write_text("mine")
    return steam, csgo, ucfg


def test_settings_are_restored_exactly(tmp_path, monkeypatch):
    from povforge import settings_guard as g
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    steam, csgo, ucfg = _fake_cs2_dirs(tmp_path)
    before = {f: f.read_bytes() for f in tmp_path.rglob("*") if f.is_file()}
    assert g.backup(steam, csgo) == 3          # 2 userdata files + boot.vcfg
    assert g.pending()
    # what CS2 does during a recording
    (ucfg / "cs2_user_convars_0_slot0.vcfg").write_text('"cl_spec_stats" "0"')
    (ucfg / "cs2_video.txt").write_text('"setting.defaultres" "1920"')
    (ucfg / "new_file.vcfg").write_text("created by cs2")
    (csgo / "cfg" / "boot.vcfg").unlink()
    assert g.restore() == 4
    assert not g.pending()
    after = {f: f.read_bytes() for f in tmp_path.rglob("*") if f.is_file() and "state" not in f.parts}
    assert after == before


def test_unfinished_backup_is_restored_before_a_new_one(tmp_path, monkeypatch):
    from povforge import settings_guard as g
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    steam, csgo, ucfg = _fake_cs2_dirs(tmp_path)
    f = ucfg / "cs2_user_convars_0_slot0.vcfg"
    g.backup(steam, csgo)
    f.write_text("changed by an interrupted recording")
    g.backup(steam, csgo)                       # must not back up the changed file
    assert f.read_text() == '"cl_spec_stats" "1"'
    f.write_text("changed again")
    g.restore()
    assert f.read_text() == '"cl_spec_stats" "1"'


def test_player_hud_setting():
    from povforge import hlae
    assert "cl_spec_stats 0" in hlae.setup_commands(hlae.RecordSettings())
    assert "cl_spec_stats 1" in hlae.setup_commands(hlae.RecordSettings(player_hud=False))
