"""A player who disconnects has no team (NaN) in later rounds; that must not lose
the teams of everyone else (it used to empty duels and victim replays)."""
import math

import pandas as pd

from povforge import demo
from povforge.model import Round


class FakeParser:
    def __init__(self, frame):
        self.frame = frame

    def parse_ticks(self, fields, ticks=None):
        return self.frame


def test_round_sides_skips_player_without_team(monkeypatch):
    frame = pd.DataFrame([
        {"tick": 101, "steamid": "1", "team_num": 2.0, "is_alive": True},
        {"tick": 101, "steamid": "2", "team_num": 3.0, "is_alive": True},
        {"tick": 101, "steamid": "3", "team_num": math.nan, "is_alive": False},
        {"tick": 201, "steamid": "1", "team_num": 3.0, "is_alive": True},
        {"tick": 201, "steamid": "2", "team_num": 2.0, "is_alive": True},
        {"tick": 201, "steamid": "3", "team_num": 2.0, "is_alive": math.nan},
    ])
    monkeypatch.setattr(demo, "_parser", lambda path: FakeParser(frame))
    rounds = [Round(1, 100, 150), Round(2, 200, 250)]
    assert demo.round_sides("x.dem", rounds) == {1: {"1": 2, "2": 3}, 2: {"1": 3, "2": 2}}


def test_missing_numbers_are_zero_not_errors():
    assert demo._int(math.nan) == 0 and demo._int(None) == 0 and demo._int(3.0) == 3
    assert demo._flag(math.nan) is False and demo._flag(True) is True
    assert demo._float(math.nan) == 0.0 and demo._float(2.5) == 2.5
