// CS2 POVForge director, run inside CS2 by HLAE's mirv_script_load.
//
// It drives the whole recording session on its own, frame by frame:
//   load the demo -> for each clip: jump close to it, lock the camera on the
//   followed player, record from the start tick to the end tick -> quit.
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

	function findController() {
		const highest = Math.min(mirv.getHighestEntityIndex(), 128);
		for (let i = 1; i <= highest; i++) {
			const e = mirv.getEntityFromIndex(i);
			if (e !== null && e.isPlayerController() && e.getSteamId().toString() === JOB.steamid) {
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

	function lockCamera() {
		if (controllerIndex === null) {
			controllerIndex = findController();
			if (controllerIndex === null) return;
		}
		if (observedController() !== controllerIndex) {
			mirv.exec('spec_player ' + controllerIndex);
			if (JOB.specMode !== '') mirv.exec('spec_mode ' + JOB.specMode);
		} else if (!observedOk) {
			observedOk = true;
			log('camera locked on ' + JOB.player + ' (entity ' + controllerIndex + ')');
		}
	}

	function seekTo(c) {
		const target = Math.max(1, c.start - JOB.prerollTicks);
		mirv.exec('demo_gototick ' + target);
		seekTries++;
		log('seek clip ' + c.id + ' to tick ' + target + ' (try ' + seekTries + ')');
	}

	function startRecording(c) {
		mirv.exec('mirv_streams record name "' + JOB.outDir + '/' + c.id + '"');
		mirv.exec('mirv_streams record start');
		log('START ' + c.id + ' tick=' + exactTick().toFixed(3));
	}

	function stopRecording(c, why) {
		mirv.exec('mirv_streams record end');
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
				lockCamera();
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
				lockCamera();
				if (tick >= c.end) {
					stopRecording(c, 'end_tick');
					nextClip();
				}
				return;

			case S.FINISH:
				// Let the encoder finish writing, then close the game.
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

	log('director loaded for ' + JOB.player + ' (' + JOB.clips.length + ' clips)');
}
