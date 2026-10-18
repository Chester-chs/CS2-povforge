// Simulates CS2 + HLAE's mirv API in Node to test director.js.
// Usage: node tests/director_sim.js  (exits non-zero on failure)
//
// The fake game advances one demo tick per rendered frame (with recording
// enabled it's 64 tick / 60 fps, close enough), honours demo_gototick, and
// has a spectator camera that only follows a player after spec_player.

const fs = require('fs');
const path = require('path');

function runScenario(name, opts) {
	const job = Object.assign({
		player: 'donk666', steamid: '76561198386265483', demo: 'D:/demos/x.dem', outDir: 'D:/out',
		tickrate: 64, prerollTicks: 128, specMode: '', setup: ['sv_cheats 1'], frameStage: 12,
		bootFrames: 5, loadTimeoutFrames: 500, hideDemoUi: true, seekRetryFrames: 50, finishFrames: 3, quitWhenDone: true,
		clips: [{ id: 'r01', start: 1000, end: 1300 }, { id: 'r02', start: 2000, end: 2200 }],
	}, opts.job || {});

	const game = {
		tick: -1, playing: false, paused: false, lastTick: opts.lastTick || 5000,
		observed: 2, recording: null, takes: [], log: [], cmds: [], quit: false,
		seekWorks: opts.seekWorks !== false, stage: opts.stage === undefined ? 12 : opts.stage,
		loadFrames: 0,
	};
	// entity 7 is donk's controller; 2 and 3 are other players
	const controllers = { 2: '111', 3: '222', 7: job.steamid };
	const ent = (i) => ({
		isPlayerController: () => i in controllers,
		getSteamId: () => BigInt(controllers[i]),
		getPlayerPawnHandle: () => (i === 99 ? 100 : 1000 + i),
		getObserverTargetHandle: () => 1000 + game.observed,
		getPlayerControllerHandle: () => i - 1000,
	});
	let listener = null;
	const mirv = {
		message: (m) => game.log.push(m.trim()),
		exec: (c) => {
			game.cmds.push(c);
			let m;
			if ((m = c.match(/^playdemo "(.*)"$/))) { game.loadFrames = 20; }
			else if ((m = c.match(/^demo_gototick (\d+)$/))) { if (game.seekWorks) game.tick = Number(m[1]); }
			else if ((m = c.match(/^spec_player (\d+)$/))) { game.observed = Number(m[1]); }
			else if (c === 'mirv_streams record start') { game.recording = { start: game.tick, frames: 0 }; }
			else if (c === 'mirv_streams record end') { if (game.recording) game.takes.push(game.recording); game.recording = null; }
			else if (c === 'quit') { game.quit = true; }
			else if (c === 'demo_resume') { game.paused = false; }
		},
		getDemoTick: () => (game.playing ? game.tick : undefined),
		getDemoTime: () => (game.playing ? game.tick / 64 : undefined),
		isPlayingDemo: () => game.playing,
		isDemoPaused: () => game.paused,
		getHighestEntityIndex: () => 64,
		getEntityFromIndex: (i) => (i in controllers || i >= 1000 ? ent(i) : null),
		getEntityFromSplitScreenPlayer: () => ent(99),
		getHandleEntryIndex: (h) => h,
		events: { clientFrameStageNotify: { on: (n, cb) => { listener = cb; } } },
	};

	const src = fs.readFileSync(path.join(__dirname, '..', 'povforge', 'director.js'), 'utf8')
		.replace('__POVFORGE_JOB__', JSON.stringify(job));
	new Function('mirv', src)(mirv);

	for (let f = 0; f < 20000 && !game.quit; f++) {
		// several stages per frame, like the real game
		for (const st of [0, 5, game.stage]) listener({ isBefore: true, curStage: st });
		for (const st of [0, 5, game.stage]) listener({ isBefore: false, curStage: st });
		if (game.loadFrames > 0 && --game.loadFrames === 0) { game.playing = true; game.tick = 1; }
		else if (game.playing && !game.paused) {
			game.tick++;
			if (game.recording) {
				game.recording.frames++;
				if (game.observed !== 7) game.recording.wrongCam = (game.recording.wrongCam || 0) + 1;
			}
			if (game.tick >= game.lastTick) { game.tick = game.lastTick; game.paused = true; }
		}
	}
	return { game, job };
}

let failed = 0;
function check(name, cond, info) {
	console.log(`${cond ? 'ok  ' : 'FAIL'} ${name}${cond ? '' : '  ' + JSON.stringify(info)}`);
	if (!cond) failed++;
}

// 1. normal run
{
	const { game } = runScenario('normal', {});
	check('normal: quits', game.quit, game.log);
	check('normal: two takes', game.takes.length === 2, game.takes);
	check('normal: take 1 starts at its tick', game.takes[0] && game.takes[0].start === 1000, game.takes[0]);
	check('normal: take 1 length', game.takes[0] && game.takes[0].frames === 300, game.takes[0]);
	check('normal: take 2 starts at its tick', game.takes[1] && game.takes[1].start === 2000, game.takes[1]);
	check('normal: camera on player while recording', game.takes.every((t) => !t.wrongCam), game.takes);
	check('normal: setup and demo loaded', game.cmds.includes('sv_cheats 1') && game.cmds.some((c) => c.startsWith('playdemo')), game.cmds.slice(0, 5));
	check('normal: START/END logged', game.log.filter((l) => /START|END/.test(l)).length === 4, game.log);
	check('normal: demo bar hidden once', game.cmds.filter((c) => c === 'demoui').length === 1, game.cmds);
	check('normal: record name per clip', game.cmds.includes('mirv_streams record name "D:/out/r02"'), game.cmds);
}

// 2. demo ends during the last clip
{
	const { game } = runScenario('demo end', { lastTick: 2100 });
	check('demo end: last take cut at demo end', game.takes.length === 2 && game.takes[1].frames === 100, game.takes);
	check('demo end: logged why', game.log.some((l) => l.includes('why=demo_end')), game.log);
	check('demo end: still quits', game.quit, game.log);
}

// 3. seeking doesn't work: retries, then skips without hanging
{
	const { game } = runScenario('no seek', { seekWorks: false });
	const seeks = game.cmds.filter((c) => c.startsWith('demo_gototick')).length;
	check('no seek: retried 3 times per clip', seeks === 6, seeks);
	check('no seek: still quits', game.quit, game.log.slice(-5));
}

// 4. render-pass stage number changed in a game update
{
	const { game } = runScenario('stage', { stage: 9 });
	check('stage fallback: still records', game.takes.length === 2, game.log.slice(0, 5));
	check('stage fallback: warned', game.log.some((l) => l.includes('frame stage')), game.log.slice(0, 5));
}

// 5. nothing to record
{
	const { game } = runScenario('empty', { job: { clips: [] } });
	check('empty: quits', game.quit, game.log);
}

process.exit(failed ? 1 : 0);
