English | [简体中文](README.zh-CN.md)

# CS2 POVForge

A personal, non-commercial tool that turns Counter-Strike 2 demos into full-match first-person (POV) videos of a chosen player.

## What it does

- Takes a CS2 demo (professional matches from HLTV, or FACEIT matches) and a player to follow
- Records the whole match from that player's point of view
- Skips dead time: freeze time, timeouts, halftime, and the rest of a round after the player dies
- Overlays a synced 2D minimap and a keyboard input display (W/A/S/D, jump, crouch, fire)
- Subscription mode: watches followed players for new matches and queues them for recording

## FACEIT integration

The FACEIT Data API is used to look up a followed player's recent matches. The FACEIT Downloads API is used only to download demo files of those matches for local processing into POV videos. No FACEIT data is redistributed or sold.

## Status

Early development.

## Disclaimer

This project is not affiliated with Valve, FACEIT, or HLTV. Demo playback runs locally in the user's own CS2 installation and never connects to VAC-secured servers.
