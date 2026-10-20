// CS2 POVForge director, run inside CS2 by HLAE's mirv_script_load.
//
// It drives the whole recording session on its own, frame by frame:
//   load the demo -> for each clip: jump close to it, lock the camera on the
//   followed player, record from the start tick to the end tick -> quit.
//
// A clip can also name another player (the victim of a kill, for a replay from
// their eyes) and a camera other than first person, worked out every frame from
// where the player is: "follow" (behind and above them), "orbit" (circling them
// around the moment of a kill), "wide" (a fixed spot further back and higher up
// that keeps them in view). These are shown in third-person spectating, so the
// player's model is drawn, with the HUD hidden.
//
// The Python side fills in the JOB constant below with the job as
// JSON before loading this file. Everything it logs starts with "[povforge]"
// so the launcher can read results back from CS2's console.log.
//
// API reference: HLAE mirv-script types (misc/mirv-script/src/types in
// https://github.com/advancedfx/advancedfx).
{
	const JOB = __POVFORGE_JOB__;
	const NAME = 'povforge-director';

	const S = { BOOT: 'boot', LOADING: 'loading', SEEK: 'seek', PREROLL: 'preroll', REC: 'rec', FINISH: 'finish', DONE: 'done' };

	let state = S.BOOT;
	let frame = 0;          // counts processed frames
	let stateFrame = 0;     // frame when the current state started
	let clip = 0;           // index into JOB.clips
	let seekTries = 0;
	let controllerIndex = null;
	let observedOk = false;
	let lastCam = 'pov';     // the camera of the clip before (to switch back to first person)
	let view = null;         // camera of the current clip: smoothed position and angles
	let clipT0 = null;       // demo time (s) when the current clip began

	function log(msg) {
		mirv.message('[povforge] ' + msg + '\n');
	}

	function setState(s) {
		state = s;
		stateFrame = frame;
	}

	function tickNow() {
		const t = mirv.getDemoTick();
		return typeof t === 'number' ? t : -1;
	}

	function exactTick() {
		const time = mirv.getDemoTime();
		return typeof time === 'number' ? time * JOB.tickrate : tickNow();
	}

	function clipSteamid(c) {
		return (c && c.steamid) || JOB.steamid;
	}

	function camOf(c) {
		return (c && c.cam) || 'pov';
	}

	function findController(steamid) {
		const highest = Math.min(mirv.getHighestEntityIndex(), 128);
		for (let i = 1; i <= highest; i++) {
			const e = mirv.getEntityFromIndex(i);
			if (e !== null && e.isPlayerController() && e.getSteamId().toString() === steamid) {
				return i;
			}
		}
		return null;
	}

	// Which controller the demo camera is following right now (or null).
	function observedController() {
		try {
			const local = mirv.getEntityFromSplitScreenPlayer(0);
			if (local === null) return null;
			const pawn = mirv.getEntityFromIndex(mirv.getHandleEntryIndex(local.getPlayerPawnHandle()));
			if (pawn === null) return null;
			const target = mirv.getEntityFromIndex(mirv.getHandleEntryIndex(pawn.getObserverTargetHandle()));
			if (target === null) return null;
			return mirv.getHandleEntryIndex(target.getPlayerControllerHandle());
		} catch (err) {
			return null;
		}
	}

	function localObserverMode() {
		try {
			const local = mirv.getEntityFromSplitScreenPlayer(0);
			if (local === null) return null;
			const pawn = mirv.getEntityFromIndex(mirv.getHandleEntryIndex(local.getPlayerPawnHandle()));
			return pawn === null ? null : pawn.getObserverMode();
		} catch (err) {
			return null;
		}
	}

	function lockCamera(c) {
		if (controllerIndex === null) {
			controllerIndex = findController(clipSteamid(c));
			if (controllerIndex === null) return;
		}
		const cam = camOf(c);
		if (observedController() !== controllerIndex) {
			mirv.exec('spec_player ' + controllerIndex);
			if (cam === 'pov' && JOB.specMode !== '') mirv.exec('spec_mode ' + JOB.specMode);
		} else if (!observedOk) {
			observedOk = true;
			log('camera locked on ' + (c && c.player ? c.player : JOB.player) + ' (entity ' + controllerIndex + ', ' + cam + ')');
		}
		// first person (2) for "pov", third person (3, the model is drawn) for the others
		const want = cam === 'pov' ? (lastCam === 'pov' ? null : 2) : 3;
		if (want !== null) {
			const mode = localObserverMode();
			if (mode !== null && mode !== want) mirv.exec('spec_mode ' + want);
		}
	}

	// --- cameras other than first person ---------------------------------------------

	const RAD = Math.PI / 180;

	function forward(pitch, yaw) {
		return [Math.cos(pitch * RAD) * Math.cos(yaw * RAD), Math.cos(pitch * RAD) * Math.sin(yaw * RAD), -Math.sin(pitch * RAD)];
	}

	function lookAt(from, to) {
		const dx = to[0] - from[0], dy = to[1] - from[1], dz = to[2] - from[2];
		return [-Math.atan2(dz, Math.hypot(dx, dy)) / RAD, Math.atan2(dy, dx) / RAD];
	}

	function lerp(a, b, k) {
		return a + (b - a) * k;
	}

	function lerpAngle(a, b, k) {
		let d = ((b - a) % 360 + 540) % 360 - 180;
		return a + d * k;
	}

	function targetPawn() {
		if (controllerIndex === null) return null;
		const ctl = mirv.getEntityFromIndex(controllerIndex);
		if (ctl === null) return null;
		return mirv.getEntityFromIndex(mirv.getHandleEntryIndex(ctl.getPlayerPawnHandle()));
	}

	// Where the camera should be this frame for clip c (null: leave the game's view).
	function cameraView(c, now) {
		const pawn = targetPawn();
		if (pawn === null) return null;
		const eye = pawn.getRenderEyeOrigin(), ang = pawn.getRenderEyeAngles();
		if (!eye || !ang) return null;
		const cam = camOf(c);
		const t = clipT0 === null ? 0 : Math.max(0, now - clipT0);
		let pos, look, fov = 90, smooth = 0.25;
		if (cam === 'follow') {
			// behind and a little above, looking where they look
			const f = forward(ang[0] * 0.4 + 6, ang[1]);
			pos = [eye[0] - f[0] * 105, eye[1] - f[1] * 105, eye[2] - f[2] * 105 + 16];
			const g = forward(ang[0], ang[1]);
			look = lookAt(pos, [eye[0] + g[0] * 300, eye[1] + g[1] * 300, eye[2] + g[2] * 300]);
			smooth = 0.2;
		} else if (cam === 'orbit') {
			// circle them: a third of a turn over the clip, a little closer at the kill
			if (view === null || view.yaw0 === undefined) view = Object.assign(view || {}, { yaw0: ang[1] + 120 });
			const len = Math.max(0.5, (c.end - c.start) / JOB.tickrate);
			const a = view.yaw0 + 120 * Math.min(1, t / len);
			const focus = (c.focus !== undefined ? (c.focus - c.start) / JOB.tickrate : len / 2);
			const r = 135 - 25 * Math.exp(-Math.pow((t - focus) / 0.5, 2));
			const centre = [eye[0], eye[1], eye[2] - 10];
			pos = [centre[0] + Math.cos(a * RAD) * r, centre[1] + Math.sin(a * RAD) * r, centre[2] + 14];
			look = lookAt(pos, centre);
			fov = 75;
			smooth = 1;
		} else if (cam === 'wide') {
			// one spot further back and higher up, chosen when the clip starts, keeping them in view
			if (view === null || view.spot === undefined) {
				const f = forward(0, ang[1]);
				view = Object.assign(view || {}, { spot: [eye[0] - f[0] * 380, eye[1] - f[1] * 380, eye[2] + 230] });
			}
			pos = view.spot;
			look = lookAt(pos, [eye[0], eye[1], eye[2] - 20]);
			fov = 80;
			smooth = 0.15;
		} else {
			return null;
		}
		if (view === null || view.pos === undefined) {
			view = Object.assign(view || {}, { pos: pos.slice(), pitch: look[0], yaw: look[1] });
		} else {
			view.pos = [lerp(view.pos[0], pos[0], smooth), lerp(view.pos[1], pos[1], smooth), lerp(view.pos[2], pos[2], smooth)];
			view.pitch = lerp(view.pitch, look[0], Math.min(1, smooth * 1.5));
			view.yaw = lerpAngle(view.yaw, look[1], Math.min(1, smooth * 1.5));
		}
		return { x: view.pos[0], y: view.pos[1], z: view.pos[2], rX: view.pitch, rY: view.yaw, rZ: 0, fov: fov };
	}

	function beginClipCamera(c) {
		view = null;
		const t = mirv.getDemoTime();
		clipT0 = typeof t === 'number' ? t : null;
		const cam = camOf(c);
		if (cam !== 'pov' && lastCam === 'pov') mirv.exec('cl_drawhud 0');
		if (cam === 'pov' && lastCam !== 'pov') mirv.exec('cl_drawhud 1');
	}

	function endClipCamera(c) {
		lastCam = camOf(c);
	}

	function seekTo(c) {
		const target = Math.max(1, c.start - JOB.prerollTicks);
		mirv.exec('demo_gototick ' + target);
		seekTries++;
		log('seek clip ' + c.id + ' to tick ' + target + ' (try ' + seekTries + ')');
	}

	function startRecording(c) {
		beginClipCamera(c);
		mirv.exec('mirv_streams record name "' + JOB.outDir + '/' + c.id + '"');
		mirv.exec('mirv_streams record start');
		log('START ' + c.id + ' tick=' + exactTick().toFixed(3));
	}

	function stopRecording(c, why) {
		mirv.exec('mirv_streams record end');
		endClipCamera(c);
		log('END ' + c.id + ' tick=' + exactTick().toFixed(3) + ' why=' + why);
	}

	function nextClip() {
		clip++;
		seekTries = 0;
		observedOk = false;
		if (clip >= JOB.clips.length) {
			setState(S.FINISH);
		} else {
			setState(S.SEEK);
		}
	}

	function step() {
		frame++;
		const playing = mirv.isPlayingDemo();
		const tick = playing ? tickNow() : -1;
		const c = clip < JOB.clips.length ? JOB.clips[clip] : null;

		switch (state) {
			case S.BOOT:
				// Give the main menu a moment, then set up and load the demo.
				if (frame - stateFrame < JOB.bootFrames) return;
				for (const cmd of JOB.setup) mirv.exec(cmd);
				mirv.exec('playdemo "' + JOB.demo + '"');
				log('loading ' + JOB.demo);
				setState(S.LOADING);
				return;

			case S.LOADING:
				if (playing && tick > 0) {
					log('demo playing at tick ' + tick + ', ' + JOB.clips.length + ' clips to record');
					setState(JOB.clips.length ? S.SEEK : S.FINISH);
				} else if (frame - stateFrame > JOB.loadTimeoutFrames) {
					log('ERROR demo did not start');
					setState(S.FINISH);
				}
				return;

			case S.SEEK: {
				if (!playing) { log('ERROR demo stopped while seeking'); setState(S.FINISH); return; }
				const waited = frame - stateFrame;
				if (seekTries === 0 || waited > JOB.seekRetryFrames) {
					if (seekTries < 3) {
						seekTo(c);
						stateFrame = frame;
						return;
					}
					if (tick >= c.start && tick < c.end) {
						// Couldn't land before the clip: record what's left of it.
						log('WARNING clip ' + c.id + ' starts late at tick ' + tick);
						controllerIndex = null;
						startRecording(c);
						setState(S.REC);
					} else {
						log('ERROR could not reach clip ' + c.id + ', skipping it');
						nextClip();
					}
					return;
				}
				if (mirv.isDemoPaused()) mirv.exec('demo_resume');
				// Arrived shortly before the clip start: wait there for it.
				if (tick >= c.start - JOB.prerollTicks - JOB.tickrate && tick < c.start) {
					controllerIndex = null;  // entity indices can change across a seek
					setState(S.PREROLL);
				}
				return;
			}

			case S.PREROLL:
				if (mirv.isDemoPaused()) mirv.exec('demo_resume');
				lockCamera(c);
				if (tick >= c.start) {
					startRecording(c);
					setState(S.REC);
				} else if (!playing) {
					log('ERROR demo stopped before clip ' + c.id);
					setState(S.FINISH);
				}
				return;

			case S.REC:
				if (!playing || mirv.isDemoPaused()) {
					stopRecording(c, 'demo_end');
					nextClip();
					return;
				}
				lockCamera(c);
				if (tick >= c.end) {
					stopRecording(c, 'end_tick');
					nextClip();
				}
				return;

			case S.FINISH:
				// Let the encoder finish writing, then close the game.
				if (lastCam !== 'pov') { mirv.exec('cl_drawhud 1'); lastCam = 'pov'; }
				if (frame - stateFrame >= JOB.finishFrames) {
					log('ALL DONE');
					setState(S.DONE);
					if (JOB.quitWhenDone) mirv.exec('quit');
				}
				return;

			default:
				return;
		}
	}

	// Run once per rendered frame. The render-pass stage number comes from
	// HLAE's docs; if a game update changes it, fall back to the stage that
	// fires most often so the director still runs.
	let activeStage = JOB.frameStage;
	let events = 0;
	const stageCounts = {};
	mirv.events.clientFrameStageNotify.on(NAME, (e) => {
		if (e.isBefore) return;
		events++;
		if (frame === 0 && e.curStage !== activeStage) {
			stageCounts[e.curStage] = (stageCounts[e.curStage] || 0) + 1;
			if (events === 2000) {
				let best = activeStage, n = -1;
				for (const k in stageCounts) if (stageCounts[k] > n) { n = stageCounts[k]; best = Number(k); }
				log('WARNING frame stage ' + activeStage + ' never seen, using ' + best);
				activeStage = best;
			}
		}
		if (e.curStage !== activeStage) return;
		try {
			step();
		} catch (err) {
			log('ERROR ' + err);
		}
	});

	// Cameras other than first person: replace the game's view every frame.
	if (mirv.events.cViewRenderSetupView && JOB.clips.some((c) => camOf(c) !== 'pov')) {
		mirv.events.cViewRenderSetupView.on(NAME, (e) => {
			const c = clip < JOB.clips.length ? JOB.clips[clip] : null;
			if (c === null || camOf(c) === 'pov' || (state !== S.REC && state !== S.PREROLL)) return undefined;
			try {
				const v = cameraView(c, typeof e.curTime === 'number' ? e.curTime : mirv.getDemoTime());
				if (v !== null) e.result = v;
				return v === null ? undefined : v;
			} catch (err) {
				log('ERROR camera ' + err);
				return undefined;
			}
		});
	}

	log('director loaded for ' + JOB.player + ' (' + JOB.clips.length + ' clips)');
}
