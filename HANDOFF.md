# 交接说明 / Handoff prompt (for another AI coding agent)

把下面整段作为提示词交给接手的 AI（GPT / Codex 等）。
Give everything below to the agent that takes over.

---

You are taking over **CS2 POVForge** (https://github.com/Chester-chs/CS2-povforge), a personal Windows tool.
It records a chosen pro player's full-match first-person view from a CS2 demo. It also makes highlight reels.
Recording uses CS2 + HLAE. The app is Python; its UI is Alpine.js in an Edge `--app` window.

## Rules from the owner (must follow)

1. **Always answer the owner in Chinese.**
2. **Recording must never change the owner's CS2 settings.**
   - `settings_guard` backs the settings up before CS2 starts and restores them afterwards. Keep that working.
   - Anything the director changes must be a non-archived console variable, or it must be put back.
3. **Open source.** If you copy code from a GitHub project, say so and follow its licence.
   - Credit every third-party project in `THIRD_PARTY_NOTICES.md`.
4. **Commits.**
   - Author: `Haosheng Chao <chqua75@gmail.com>`.
   - No `Co-Authored-By` lines and no other AI trailers.
   - Run `git pull --rebase` before every push.
5. **When something is unclear, ask the owner. Don't guess.** They prefer short multiple-choice questions.
6. They want things delivered fast. Release small, working versions.

## Layout

| Path | What it is |
|---|---|
| `povforge/cli.py` | CLI `povforge` (record, reel, analyze-style, restore-settings…) |
| `povforge/gui/server.py` | Local HTTP server, job queue, preferences. It writes the per-job `config.toml` (`write_job_config`). |
| `povforge/gui/static/{index.html,app.js,app.css}` | The UI. Sidebar has two equal modes: 整场录制 / 高光集锦. |
| `povforge/pipeline.py` | Plan (parse demo) → record → compose → publish. Also `videos_dir`, `make_upload_copy`. |
| `povforge/demo.py` | Demo parsing. `Death(tick, victim_steamid, attacker_steamid, weapon, headshot)`. |
| `povforge/hlae.py` | Launches CS2 through HLAE, writes `director.js` with the job (`build_job`), waits, then muxes takes. |
| `povforge/director.js` | Runs inside CS2 (HLAE mirv-script). State machine BOOT/LOADING/SEEK/PREROLL/REC/FINISH. For each clip it seeks, locks the spectator camera on the player and records with `mirv_streams`. |
| `tests/director_sim.js` | Node mock of HLAE's `mirv` API. Run with `node tests/director_sim.js`; `tests/test_hlae.py` runs it too. |
| `povforge/reel.py` | Highlight reels. It cuts kill moments from recordings (`_cut_points`); plain join or `effects.build`. |
| `povforge/effects.py` | FFmpeg-only effects engine: transitions, slow-mo, zoom, flash, grade, title/outro cards, music. |
| `povforge/style.py` | Analyses an imported finished video (file or link via yt-dlp). It returns the `effects` settings that reproduce its style. |
| `povforge/compose.py` | Final video, `concat_line`, `upload_copy` (4K upscale). |
| `packaging/` | PyInstaller spec, Inno Setup script, release notes. |
| `.github/workflows/windows-app.yml` | Tests → build → bundle FFmpeg → smoke test → installer → release. Runs on tag `v*` only. |

## How to test and release

- Run `python -m pytest -q` (113 pass, 4 skip on Linux) and `node tests/director_sim.js`. Install FFmpeg for the effects tests.
- To release:
  1. Bump the version in `pyproject.toml`, `povforge/__init__.py` and the comment in `packaging/povforge.iss`.
  2. Add a section to `packaging/RELEASE_NOTES.md`.
  3. Commit, then `git tag vX.Y.Z && git push origin main vX.Y.Z`.
  4. CI builds the Windows installer and the release. The app updates itself in place (`selfupdate.py`), downloading only the changed files.
- Real recording only works on the owner's Windows PC with CS2 and HLAE. They agreed to test on their machine; ask them to run it and send screenshots or logs (`cs2_console.log` in the job folder).

## Current state

- v0.13.0 is tagged. It adds:
  - recording size and frame rate in settings;
  - quality-first encoding;
  - an optional 4K upload copy;
  - importing a finished video by link (yt-dlp);
  - the owner's own music library for reels.
- Check that its GitHub Actions run succeeded. Then ask the owner to update in the app and verify:
  - 播放视频 / 打开所在文件夹 work;
  - old videos were moved into per-player folders under `职业选手POV`.
- Effects exist **only** when the owner imports a finished video (成片). With no imported video, a reel is a plain join.
- Imported styles are saved as named presets. Each part can be mixed between presets: intro, transition, kills, grade, outro, pace.

## The unfinished feature: camera simulation (镜头模拟)

What the owner asked for: "如果我要导入成片，软件也要模拟镜头选择，也可以不模拟镜头选择". When a finished video is imported, the reel should be able to copy its camera choices. Copying is optional: a switch with two choices, 照成片的镜头 / 只用第一人称.

The four camera types they want:
- 第三人称跟随 (follow, behind the player);
- 击杀时环绕 (orbit around the player at a kill);
- 自由机位 (a free / wide fixed camera);
- 被击杀者视角 (replay from the victim's eyes).

### Already done (uncommitted work, see branch `camera-wip`)

`povforge/director.js` now supports per-clip fields:
- `steamid`: whose view to record; defaults to the job's player. Use the victim's steamid for a victim replay.
- `player`: a name, for the log only.
- `cam`: `pov` | `follow` | `orbit` | `wide`.
- `focus`: the kill tick, used by `orbit`.

How it works:
- For a non-`pov` clip, it switches to `spec_mode 3` (third person, so the model is drawn) and sets `cl_drawhud 0`.
- It replaces the view every frame through `mirv.events.cViewRenderSetupView.on(name, cb)`, returning `{x,y,z,rX(pitch),rY(yaw),rZ,fov}`, and smooths it.
- It returns to `spec_mode 2` and `cl_drawhud 1` afterwards, and again at FINISH.
- Camera math is in `cameraView()`. It uses the observed pawn's `getRenderEyeOrigin()` / `getRenderEyeAngles()`.
- Existing simulator scenarios still pass. **Nothing new is tested yet.**

HLAE API types: https://github.com/advancedfx/advancedfx, folder `misc/mirv-script` (typings).
- `getObserverMode()`: 2 = in-eye, 3 = chase, 4 = roaming.

### Still to do, in order

1. **Simulator.** Extend `tests/director_sim.js`:
   - a `cViewRenderSetupView` event the fake game calls each frame;
   - pawns with `getRenderEyeOrigin` / `getRenderEyeAngles` / `getObserverMode`;
   - handling of `spec_mode N`.
   Add scenarios:
   - a follow clip and an orbit clip both return views;
   - the HUD goes off and comes back on;
   - a victim clip locks onto the other controller (the mock's `wrongCam` check assumes entity 7, so make it per clip);
   - after a non-pov clip, a pov clip goes back to `spec_mode 2`.
2. **Victims.** In `pipeline.make_plan`, also save `victims.json`: `[[tick, victim_steamid], ...]` for the player's kills. For old jobs without it, re-read the demo deaths (`demo.py`) when needed.
3. **Recording extra shots.**
   - `hlae.build_job` / `hlae.record` should accept extra shots: `{id, start, end, steamid, cam, focus}`.
   - Save them as `job/shots/<id>.mp4`, recorded in the same CS2 session.
   - `recorded.json` keeps their actual start ticks too.
4. **Reel assembly** (`reel.py` + `effects.py`), when camera copying is on:
   - **follow**: replaces the first ~1.5 s lead-in of a moment;
   - **orbit**: replaces ~1 s around a kill. Keep the POV game sound under it so the sound stays continuous;
   - **wide**: a 1.5–2 s establishing shot at the very start of the reel or of a moment;
   - **victim**: an extra 1–1.5 s piece inserted right after the kill, joined with hard cuts.
   - Shots are recorded at the reel step: one extra CS2 session per demo, only for the needed shots. Tell the owner this makes reels slower.
5. **Analyser** (`style.py`): detect the camera kinds in the imported video and store them in the style as e.g. `camera: {follow: bool, orbit: bool, wide: bool, victim: bool}`, or as a list of shots with positions.
   - **POV** frames have a static HUD (bottom corners, ammo/health area) at higher resolution. Sample at e.g. 320×180 and check how stable those regions are.
   - **Non-POV**: a smooth circular pan around a centre = orbit; a near-still camera = wide; otherwise follow.
   - **Victim replay**: a short POV insert that interrupts a continuous shot right after a kill flash.
   - Calibrate on synthetic tests the way `tests/test_effects.py` does, then on real reels the owner gives you.
6. **UI.**
   - A 「镜头」 category in the per-part mix rows on the reel page (`fxParts` in `app.js`).
   - The switch 照成片的镜头 / 只用第一人称.
   - Show detected camera kinds in the analysis report (`refRows`).
7. **Docs and release.** Update the READMEs (English + Chinese) and the release notes. Release v0.14.0. Then ask the owner to test a reel with each camera kind on their PC.

### Known gotchas

- The frozen PyInstaller app ignores `PYTHON*` env vars. The CLI forces UTF-8 output itself. Paths with Chinese must survive.
- Pillow 12 rejects crop boxes outside the image; pad first.
- Child processes use `CREATE_NO_WINDOW`.
- Run `git pull --rebase` before pushing: the repo may have been changed elsewhere.
- `cl_drawhud` needs `sv_cheats 1`, which the setup already sets.
- Entity indices can change after a seek. The director already resets `controllerIndex` per seek.
