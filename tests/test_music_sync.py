from pathlib import Path
import json
import shutil
import subprocess

import numpy as np
import pytest

from povforge import effects


def test_audio_detects_beats_and_silence():
    from povforge.music_sync import analyze_samples
    rate = 8000
    samples = np.zeros(rate * 10, dtype=np.float32)
    for t in np.arange(0.5, 9.6, 0.5):
        i = int(t * rate)
        samples[i:i + 80] = np.hanning(80)
    track = analyze_samples(samples, rate)
    assert len(track.beats) >= 17
    assert min(abs(track.beats - 4.0)) < 0.08
    assert len(analyze_samples(np.zeros(rate * 2), rate).beats) == 0


def test_music_offset_prefers_strong_beats_at_dense_kills():
    from povforge.music_sync import Track, choose_offset
    beats = np.arange(0.5, 30, 0.5)
    strong = (beats >= 15) & (beats < 20)
    track = Track(30, beats, np.where(strong, 1.0, 0.2), beats, np.where(strong, 1.0, 0.1))
    result = choose_offset(track, [2.2, 2.7, 3.2], 6)
    assert 12 <= result["start"] < 18
    assert max(result["errors"]) < 0.02
    assert result["matched"] == 3


def test_short_song_or_no_kills_has_explicit_fallback():
    from povforge.music_sync import Track, choose_offset
    a = np.array([1.0, 2.0, 3.0])
    track = Track(4, a, np.ones(3), a, np.ones(3))
    assert choose_offset(track, [1], 8)["reason"] == "music_too_short"
    assert choose_offset(track, [], 3)["reason"] == "no_kills"


def test_rendered_kill_timeline_includes_intro_slowmo_and_crossfade():
    from povforge.music_sync import timeline_kills
    fx = effects.normalize({"kill_slowmo": True, "kill_scope": "last"})
    moments = [effects.Moment(Path("a"), 0, 5, [1, 3]), effects.Moment(Path("b"), 0, 4, [2])]
    chosen = effects.chosen_kills(moments, "last")
    seq = [("card", Path("intro.png")), ("moment", 0), ("moment", 1)]
    durations = [2, 6.1, 5.1]
    crossings = [0.4, 0.3]
    got = timeline_kills(moments, chosen, fx, seq, durations, crossings)
    assert got[0] == pytest.approx(1.6 + 1)
    assert got[1] == pytest.approx(1.6 + effects.mapped(3, effects.time_map(5, [3], 0.5)))
    assert got[2] == pytest.approx(1.6 + 6.1 - 0.3 + effects.mapped(2, effects.time_map(4, [2], 0.5)))


def test_sync_setting_survives_normalization_and_is_optional():
    assert effects.normalize({"music_sync": True})["music_sync"] is True
    assert effects.normalize({})["music_sync"] is False
    assert effects.is_plain({"music_sync": True})


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_sync_build_uses_full_song_and_emits_measured_report(tmp_path):
    import wave
    from povforge.compose import ComposeSettings
    from povforge.media import probe
    clip, song = tmp_path / "clip.mp4", tmp_path / "song.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=blue:s=320x180:r=30:d=2", "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=stereo", "-t", "2", "-c:v", "libx264",
                    "-preset", "ultrafast", "-c:a", "aac", str(clip)], check=True)
    rate = 8000
    samples = np.zeros(rate * 12, dtype=np.float32)
    for t in np.arange(0.5, 11.6, 0.5):
        i = int(t * rate)
        samples[i:i + 80] = np.hanning(80) * (0.9 if t >= 6 else 0.2)
    with wave.open(str(song), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate)
        f.writeframes((samples * 32767).astype("<i2").tobytes())
    work = tmp_path / "work"
    out = effects.build([effects.Moment(clip, 0, 2, [0.8, 1.3])],
                        {"music": str(song), "music_sync": True}, tmp_path / "out.mp4",
                        work, (320, 180), 30, ComposeSettings(preset="ultrafast"))
    report = json.loads((work / "music-sync.json").read_text())
    assert report["start"] > 4 and report["matched"] == 2
    assert probe(out).duration == pytest.approx(2, abs=0.15)
