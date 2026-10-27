"""Retired camera preferences cannot change the first-person reel contract."""

import pytest

from povforge import camera, effects, hlae
from povforge.model import Plan, Player


LEGACY = {"mode": "reference", "follow": True, "orbit": True, "wide": True,
          "frequency": 1, "durations": {"orbit": 1.5, "victim": 1.2}}


@pytest.mark.parametrize("victim", [False, True])
def test_legacy_preferences_only_allow_explicit_victim_replays(victim):
    choice = camera.normalize_camera({**LEGACY, "victim": victim})
    assert choice == {"mode": "pov", "victim": victim, "durations": {"victim": 1.2},
                      "placement": "after_kill"}
    shots = camera.plan_shots(start_tick=0, end_tick=1280, kill_ticks=[512, 896],
                              victims=[[512, "222"], [896, "333"]], steamid="111",
                              tickrate=64, camera={**LEGACY, "victim": victim}, key="test")
    assert len(shots) == (2 if victim else 0)
    assert all(s["cam"] == "pov" and s["insert"] and s["at"] == 20 for s in shots)
    assert effects.is_plain({"camera": LEGACY})


@pytest.mark.parametrize("cam", ["follow", "orbit", "wide"])
def test_recording_rejects_retired_third_person_requests(tmp_path, cam):
    plan = Plan("match.dem", "de_dust2", 64, Player("111", "Player"), [])
    with pytest.raises(ValueError):
        hlae.build_job(plan, [], tmp_path, hlae.RecordSettings(), extra_shots=[
            {"id": "legacy", "start": 0, "end": 64, "steamid": "111", "cam": cam}])
