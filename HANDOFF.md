# POVForge handoff — 2026-10-27

## Current agreed scope

v0.17.0 adds persisted queued tasks, weapon filtering and library playback with
finished-video event jumps. queue.json is bounded and atomically replaced after
flushing; recovered running tasks become queued and the queue starts paused.
Per-task options are captured when queued. Job preparation preserves current
app preferences while using the saved options, including player destinations.
No draft editor autosave or automatic startup recording is added.

ReelItem carries normalized weapon identifiers through GUI, queue, CLI and disk.
Solo windows are merged before filtering, preserving mixed-weapon streaks.
Highlights retain an entire matching round's first-to-last-kill sequence; duel
filtering retains each selected A/B encounter. Frontend windows, estimates,
labels and victim choices agree. Whole-match recording is unchanged.

New jobs save event-index.json with source kill/death metadata. Finished MP4s
get a stat-bound .mp4.povforge.json index outside work files. Plain composition
uses actual piece durations; effects use the render speed map, cards and actual
overlaps. Inline replays are included in output offsets. Old source jobs can
fall back to kill markers; old videos without indexes remain playable.
Library playback uses a same-origin/CSRF-protected POST to create an opaque,
bounded, expiring video handle. GET/Range streams only that registered video;
arbitrary client paths, wrong Host and changed files are rejected. No Demo
parse, mass probe, new dependency or game process is needed to view videos.

Local full regression: 397 passed in 184.92s. Later targeted assertions for
live-preference preservation and filtered replay choices passed 13/13; the
real-player/queue/filter target passed 9/9. Player checks decode synthetic H.264
and wait for seeking to finish; 900px geometry and 1920px light/dark previews
were checked. Existing text audits include the player in light/dark/Auto.
Startup failures now pause remaining queued work so the Resume action stays
available; 51 queue/lifecycle/GUI checks passed in 2.92s after this final fix.
See docs/releases/v0.17.0/verification.md for checkpoints and limits.

v0.16.4 simplifies the by-player switch to one line. Player destination rows are
derived only from the active whole-match player or the reel's selected players
(both sides for duel), never unrelated history or stale selections in the match
library. Existing custom paths and pick/reset actions remain available there.
The sidebar Video library has a collapsible folder list with counts. Folders
come from saved destinations and actual video parent paths, so custom paths and
legacy videos without player metadata work. Path comparisons normalize Windows
case and slash style and require exact parent equality, avoiding prefix matches.
The folder tree stays available with by-player disabled and can show empty saved
destinations. Main Video library opens all videos; refresh retains folder filters.

Default highlight/event padding is 5s before and 3s after (previously 4s/1.5s).
Frontend estimates match. Existing overlap merging, continuous highlight rounds,
round boundaries, duel A/B ordering and explicit highlight pace options remain.
No recording, file movement/deletion, new API, parser or cache changes were added.
Current-task TDD: 6 RED, then 6 GREEN; affected regression: 88 passed in 32.35s.
Full run: 374 passed, two old-timing expectations failed; after updating only
those expectations, both test files plus the new target passed 17 in 23.03s.
Private 1920px light/dark folder-library and compact public-panel previews checked.
See docs/releases/v0.16.4/verification.md for final evidence and limits.

v0.16.3 publishes the v0.16.2 palette below with an isolated browser audit.
v0.16.2 CI 40043670824 stopped before packaging: 347 passed, 22 skipped and one
offline-dialog test failed because the normal successful health poll cleared the
simulated offline flag. After boot, the audit now suspends only /api/state and
/api/job reads in its private browser; view-specific reads still run. All 64 view
audits and 16 accent/theme checks remain enforced. The final affected target
passed 8 tests in 17.13s. No v0.16.2 installer was published. No production CSS,
capture logic or game settings changed during this test isolation fix.

v0.16.2 supersedes the gray text palette below: all interface text is pure black
in light mode and pure white in dark mode, including Auto following the system.
Labels 2/3 alias the primary label; title/body hierarchy uses size, weight and
spacing. Colored icons and decorative surfaces remain. Text-specific accent/error
colors are monochrome too. Disabled/dragged text is not faded; outlines signal
state. Dark accent-filled controls use half-intensity accent backgrounds to keep
white text readable across all eight accents. Decorative outlines retain their
own token so they do not become black/white text borders everywhere.

Real browser audit checks visible text nodes and placeholders across 16 main
views/states in four theme combinations (64 audits), plus primary-button contrast
for all eight accents in light/dark. Relevant browser/appearance target: 8 passed
in 18.62s. One existing video-library test now waits for layout after Alpine shows
the section, rather than assuming cached rows imply the page is already visible.
See docs/releases/v0.16.2/verification.md. No game/capture/backend/cache changes.

v0.16.1 fixes low-contrast gray text reported in the v0.16.0 preflight card.
Secondary/tertiary text uses opaque theme-specific colors instead of 30-62%
opacity, including the system-dark media-query path. Hints are 13px with 1.6
line-height; input/textarea placeholders have explicit readable colors.
Real browser contrast checks cover preflight hints/headings, counts, totals,
weapon summaries and library metadata in light/dark/auto. Minimum measured
ratios: 6.07 light, 7.16 dark; library 7.44/9.18. Four browser regressions passed
in 10.44s, including responsive geometry and existing user flows. Backend and
recording code use v0.16.0 evidence. See docs/releases/v0.16.1/verification.md.

v0.16.0 adds pre-recording main-footage estimates, a persistent finished-video
library, and expandable per-round weapon/event details in all five modes. The
user cancelled the AI editor; it is absent from this branch/release. Earlier AI
work was preserved only in a local archive branch/stash, never pushed.

Inspection keeps the v4 disk key. Normal cache reads remain compatible; the GUI
requests details and upgrades an older entry once to include version-1
recording_details (events, round boundaries, default whole-match durations).
Event counts, merged windows, duel A/B playback and player identities remain
unchanged. Estimates exclude optional effects/replays/intros/outros and are
labelled accordingly. Processing/size estimates require three local samples
with matching mode/FPS and whole-match overlay flags. Profiles are captured
when jobs start; actual time still depends on the PC and reusable recordings.

Completed jobs save best-effort metadata atomically in app_dir/recordings.json,
outside work files and the queue. Library listing scans only configured output
roots and immediate player folders, with bounded entries and no link traversal;
no Demo parsing or mass FFprobe occurs while listing. Changed/missing videos keep
history with invalidated timing samples. Old files appear with unknown metadata.
No video deletion/move command was added. GET /api/library retains the existing
Host boundary; playback uses the existing authenticated open API.

See docs/releases/v0.16.0/verification.md for current-task RED/GREEN evidence.
No CS2 launch or game/Steam settings edits were performed.

v0.15.10 supersedes the earlier victim replay scope for duel mode: hide the entire
Perspective replays section in head-to-head mode. The submitted duel task and
backend ignore saved victim opt-ins; other modes retain their saved choices.
Existing A/B encounter views remain intact. The requested AI style editor is
planning only: no style layout changes or API integration are included here.
Local affected checks: 16 passed in 28.19s and 18 event regressions passed in
9.12s. JS syntax, Python compilation and diff checks passed. No game/settings
side effects. See docs/releases/v0.15.10/verification.md.


v0.15.9 publishes the v0.15.8 UI/replay features below plus a browser startup
race fix. v0.15.8 CI run 40030178920 stopped before packaging: 330 passed,
22 skipped, one PermissionError while Chromium held DevToolsActivePort.
The port reader now retries locks, missing/partial/invalid endpoint data within
the existing startup deadline, reads readiness from one snapshot, and cleans
up on timeout. Regression tests reproduced RED (2 failed), then GREEN (5 passed
including real browser/FACEIT fixture/UI checks in 14.70s). The earlier 350-test
local suite remains valid for unchanged feature code. No game launch/settings
changes. See docs/releases/v0.15.9/verification.md.


v0.15.8 supersedes all earlier ending-only victim replay rules below. The reel
editor now shares the library's wide desktop grid and right-side recording panel.
Style/reference/visual effect controls appear only in Highlights (`kills`). Event
reels discard hidden visual style and pace settings, preserving music/audio and
camera choices. Every reel mode (kill_events, kills_deaths, duel, kills) offers
Victim perspective; whole-match recording does not. It is off by default. Users
may select individual real kills, default to inserting immediately after each
selected kill, or explicitly collect them at the end. Main footage resumes after
inline replays. Selection identities use original Demo path + attacker + tick +
victim; only actual victims from parsed recording metadata can be captured.
Duel A/B encounter ordering is preserved through replay planning. Replay footage
stops before death to avoid switching spectator target; missing captures are
skipped, with main footage retained. No parsing cache version bump is needed.
This update was developed without launching CS2 or modifying game settings.
Final local regression: 350 passed in 160.86s; three additional selection cases
also passed in the 12-test inline target. Python compile, JS syntax, 25 director
assertions, browser mode/payload checks and native maximized preview passed.
See docs/releases/v0.15.8/verification.md for RED/GREEN evidence and boundaries.


v0.15.7 supersedes the app quality choices below: resolution is fixed at 1080P,
with no editable size control. Saved 2K/4K app choices migrate to 1080. FPS is a
24/30/60/120/144/240 menu; other old values fall back to 60. CLI/media helpers
remain compatible with existing advanced configurations.
The sidebar now orders whole match, kill POV, kills/deaths POV, duel, highlights.
Selected rounds show kills/deaths totals. Duel totals are per player and count
only mutual encounters; totals update when rounds/players change and dedupe
repeated selections. First-person/victim replay behavior is unchanged.
Recording options show a root folder picker and per-player destination pickers.
Defaults use the first recorded in-game ID name, reuse that player's folder and
create it when the job config is written. Chosen destinations persist by Steam
identity; cancelling a picker leaves preferences intact. Existing videos are
not moved when choosing a new destination. Legacy folder rename API is retained.
Desktop >=1560px uses a side-by-side match library and recording options; smaller
windows stack them with consistent widths. Native maximized preview checked.
Help text after grouped controls has at least 12px top spacing. Unfilled slider
tracks are white, with the selected accent on the filled track and thumb.
Local regression: 340 passed in 277.80s before final small markup/directory
creation refinements; 31 affected tests passed afterward. Browser geometry and
state tests, JS syntax and 25 director assertions passed. Native fake-API preview
verified single title, mode order, full-screen layout and white slider track.
No CS2 launch or game-settings changes. Release CI verifies final state.

v0.15.6 adds selectable 1080P/1440P/2160P and integer 1-240 FPS through prefs,
job TOML, HLAE commands, plain/effected composition and exports. Only Auto fits
the screen; explicit sizes are preserved. If CS2 supplies smaller frames, the
existing compositor scales them to the selected output size. UI/README explain
that this does not add native detail. No real CS2 recording was performed.
The sidebar brand header is removed; the native caption retains the app name.
Entering a match, continuing to reel editing, switching modes and returning to
the library reset the main scroll container after Alpine updates the view.
Quality changes archive incompatible takes under the job's previous-quality/
folder while retaining analysis. Whole-match reuse checks requested quality.
Default legacy 1080p/60 takes remain compatible. No game settings changed.
ECC TDD checkpoints: 42defe6 (quality/branding RED), f6739f5 (scroll RED),
36d8486 (quality-cache RED). Relevant regression: 116 passed. Full local run:
334 passed, 2 failures in outdated test fixtures; both fixtures corrected and
11 affected tests passed. FFmpeg tests actually probe 1440p/120 and 2160p/120.
Native isolated fake-API window visually checked for a single title, rounded
quality controls and scroll reset. Coverage tooling is not installed. Release
CI runs the complete final suite plus installer and native-host checks.

v0.15.5 replaces the match-header radar thumbnail with the actual map scenery
from the existing MurkyYT/Valve asset source. It is downloaded on demand with an
8-second timeout and 8 MiB cap, atomically cached separately from radar assets.
Missing images stay hidden, and a subsequent supported map restores the image.
Recording minimap behavior is unchanged. No game launch or settings changes.

The v0.15.4 release was blocked by an existing browser-test readiness race after
reload (302 passed, 21 skipped). The test now waits for Alpine binding and fetched
preferences before clicking. v0.15.4 had no published installer.

v0.15.3 was published successfully, including native-host installed-app checks.

v0.15.3 fixes the gray titlebar confirmed in the owner's v0.15.2 screenshot.
Windows now hosts the existing page inside a native WinForms/WebView2 window,
whose caption is painted by Windows and responds to the existing DWM colors.
pywebview 6.2.1 is bundled; an installed stable WebView2 runtime and .NET 4.6.2+
are detected without changing system settings. Missing dependencies retain the
old browser fallback. Native lifetime follows the existing busy-job rules;
an updater shutdown closes the native window as well as the HTTP server.
Real isolated native UI was visually checked in light/dark themes and maximized;
the titlebar matches the page background. Alt+F4 closed the fixture normally.
No real App/game discovery was used for local visual checks. The Windows release
workflow now also requires the installed app to load its native WebView2 window.
An independent review found async WebView2 initialization could leave a blank
window. A 30-second load timeout now closes it and requests browser fallback;
intentional closure does not trigger fallback. Regression was red then green.
Local full regression: 312 passed before the three final integration/failure
cases were added; final affected-area run: 62 passed including those cases.
Local PyInstaller build, JS syntax, whitespace checks and 25 director assertions
passed. The release workflow runs the complete final suite again.

Local changes after v0.15.1: the main area now contains the searchable
Demo library. Its title follows the chosen recording mode. The sidebar has
five equal entries in the owner's exact order: Demo整场录制, Demo击杀视角,
Demo击杀和死亡视角, 高光集锦, 双人对位数据; event modes are no longer nested in the highlights selector. Upload
Demo opens the local file picker. First-use setup recommends one dedicated
Demo folder without moving or deleting files. Setup appears
on first use or when preparation needs attention and remains reachable in
Settings. Match details and reels can return to the workspace without losing
reel sources. Existing v4 inspection caches remain compatible; concurrent
inspection requests share a parse, cache writes are atomic, and the library
shows saved-analysis status. These UI/cache changes are included in v0.15.2.
Browser verification uses a fake API and a private headless browser, never
the real app/game configuration.

Settings now occupies the main area with appearance, general/storage and
about/update tabs. Recording size/fps and player-folder controls moved to the
main recording panel. Font presets and popup radius are validated and persisted.
The window-theme API uses the existing write authentication and only targets
one live explicitly owned window. Native Chromium caption appearance remains
visually unverified; DWM acceptance alone is not proof of browser rendering.
Work cleanup preserves GUI demo-info summaries but removes detailed recording
plans and raw takes. An isolated 142.8 MB Dust2 benchmark took 9.357 seconds to
prepare a plan and 0.0248 seconds to reuse it, excluding game recording. Evidence:
`.test-tmp/cache-benchmark-20261023/result.json`. Never treat this as a guarantee.

v0.15.2 pre-release verification: 306 local tests passed in 253.15 seconds,
25 director simulation assertions passed, JavaScript syntax and staged diff
whitespace checks passed. Native titlebar screenshots remain pending the
owner's post-install feedback; publication is explicitly authorized meanwhile.

The owner cancelled camera imitation and third-person recording. Highlight
reels always use the selected player's first-person view. Keep the separate
optional victim replay switch, off by default: record all main highlights,
then append victims' first-person views in the main reel's kill order. Never
interleave these replays. Style imports and preset changes preserve this choice.

Reference-video editing styles (pace, transitions, grading, effects and titles)
remain supported. Legacy follow/orbit/wide preferences are ignored. Custom
camera math, camera-style detection and map collision extraction were removed.

## Project and recording flow

Repository: https://github.com/Chester-chs/CS2-povforge

Python application with an Alpine.js UI. `pipeline.py` parses the demo, records
and publishes whole-match POVs. `reel.py` selects kill moments, records any
requested victim clips in one additional session per demo, then composes the
main moments followed by replays. `camera.py` now only normalizes legacy
preferences, plans real victim events and renders ending replays.

`hlae.py` validates all extra clips as first-person and caches them using source,
settings and director signatures. `director.js` seeks and locks the requested
player in native first person; it rejects third-person requests and stops if
the target changes during recording. Missing target information must never
silently substitute another player's view.

`effects.py` keeps kill effects on the main highlights. `style.py` handles
reference editing styles. `gui/static/app.js` owns the independent victim
checkbox and migrates saved camera preferences.

## Settings safety

Do not change the owner's persistent CS2 settings. Preserve `settings_guard`
backup/restoration, including startup failure, cancellation, temporary CFGs and
owner-process locking. Restoration must finish after CS2 exits before reporting
successful recording. Do not launch CS2 just to run the automated tests.

## Verification and historical sample

Run `python -m pytest -q` and `node tests/director_sim.js`. FFmpeg integration
tests check actual frame colours, ordering and audio timing. Recording tests
use a fake external game and real isolated settings files.

Earlier on 2026-10-20, real Dust2 round 21 recordings covered first-person-only
and first-person-plus-victims output. All 52 audited CS2 settings files matched
their pre-test bytes. Local evidence remains under
`packaging/dist/camera-real-test-final/` (ignored by Git). These tests preceded
the final removal of third-person code; the simplification was tested without
relaunching CS2. Old camera-test ZIPs are historical and are not this source
revision's build.

Version is 0.15.7. A source push does not publish an installer. The Windows
workflow builds releases on version tags or manual dispatch. After reviewing
the 2026-10-23 fixes, the owner explicitly authorized committing, pushing to
GitHub and publishing updated installers. The prohibition on launching CS2/HLAE
or accessing the owner's real game settings remains in force. The owner explicitly
requested publishing v0.15.2 before native titlebar screenshot verification;
they will install the release and supply screenshots afterward. Computer Use
could not determine the app-window browser URL and stopped that visual check.

## 2026-10-22 feature update

- All new output is capped at 1920x1080 and 60 fps. Legacy high-resolution
  preferences migrate; cached oversized clips/parts are normalized. No extra
  4K upload copy is produced.
- New content modes: deaths only, kills plus deaths, and opposing-player
  duels. Solo events always use the selected player's first person in round
  order. Duels include mutual kills only, each encounter A then B, with a swap
  control. Duel mode does not append a third victim replay. `reel_events.py`
  validates selections before recording and keeps actual kill anchors separate
  from deaths. Exit events belong to the round just played.
- Reference import now previews the source, accepts a selected time range and
  effect description, displays a supported partial proposal, then requires an
  explicit Apply. Common editing effects are template approximations. The
  supplied Bilibili example could not be downloaded in this environment;
  object-tracked knife rings are unsupported, not silently approximated by a
  full-screen filter.
- Optional music synchronization selects a continuous excerpt from the full
  song using onset strength, energy and the final Demo kill timeline. It does
  not identify a semantic chorus or guarantee every kill lands on a beat.
- Automated verification: 255 tests passed; browser UI and real Demo event
  parsing were checked; FFmpeg tests verify actual output/order. New event
  modes have not been recorded in live CS2. No persistent CS2 settings were
  changed during this update.

## 2026-10-23 review fixes and v0.15.1 release

The implementation fixed the five read-only review findings, added regression
tests and rewrote both READMEs for first-time users. The owner subsequently
authorized commit, push and installer publication. Do not launch CS2/HLAE or
touch the owner's real game settings during release work.
Recording and settings tests use a fake external game and isolated temporary
files only. The owner paused for shutdown, then explicitly resumed this task.

- GUI manual settings restoration shares the recording-start lock and rejects
  recording, cancellation, a live child or an open CS2 process.
- Ordinary raw takes require completed console markers and readable media of
  sufficient duration before reuse. Invalid material no longer poisons retries;
  output permission failures preserve the raw recording.
- Final event modes are `kill_events` (kills only), `kills_deaths` and `duel`.
  Deaths-only has been removed. Legacy `kills` still means selected-round
  highlights, and whole-match POV remains. Solo event windows are merged and
  chronological. Posthumous kills are excluded before recording because the
  attacker no longer has a living POV. Preview counts use the same filter.
  Victim appendices remain available for traditional highlights; event reels
  keep their own POV and duels already contain both views.
- Thumbnail paths resolve within the output directory, including junctions.
  GET/POST validate the bound listener's Host; POST additionally checks Origin
  and a per-server token. The frontend authenticates writes and pagehide.
- English and Chinese READMEs explain downloads, first use, mode choices and
  troubleshooting. Output playback duration is distinct from recording and
  encoding time; the fixed 28-to-16 minute claim was removed.

Final full regression: 284 passed in 115.08 seconds, plus 25 director
simulation assertions, JS syntax and diff whitespace checks. Independent review
identified two follow-ups, now fixed and rechecked: mux errors must preserve
validated raw footage, and inspection cache version 4 must replace stale event
counts. No outstanding actionable findings. Details are recorded in the
implementation plan. These results are automated checks, not a live CS2 test.
