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
		bootFrames: 5, loadTimeoutFrames: 500, seekRetryFrames: 50, finishFrames: 3, quitWhenDone: true,
		clips: [{ id: 'r01', start: 1000, end: 1300 }, { id: 'r02', start: 2000, end: 2200 }],
	}, opts.job || {});

	const game = {
		tick: -1, playing: false, paused: false, lastTick: opts.lastTick || 5000,
		observed: opts.observed || 2, recording: null, takes: [], log: [], cmds: [], quit: false,
		seekWorks: opts.seekWorks !== false, stage: opts.stage === undefined ? 12 : opts.stage,
		loadFrames: 0,
		mode: opts.mode || 2, hud: 1, recordId: null, views: [], viewListener: null, cameraReadTicks: [],
	};
	// entity 7 is donk's controller; 2 and 3 are other players
	const controllers = { 2: '111', 3: '222', 7: job.steamid };
	const ent = (i) => ({
		isPlayerController: () => i in controllers,
		getSteamId: () => BigInt(controllers[i]),
		getPlayerPawnHandle: () => (i === 99 ? 100 : 1000 + i),
		getObserverTargetHandle: () => 1000 + game.observed,
		getPlayerControllerHandle: () => i - 1000,
		getObserverMode: opts.noObserverMode ? undefined : () => game.mode,
		getRenderEyeOrigin: () => {
			game.cameraReadTicks.push(game.tick);
			if (opts.failCameraAt !== undefined && game.tick >= opts.failCameraAt) throw new Error('camera unavailable');
			return opts.eye ? opts.eye(game.tick) : [game.tick / 20, i, 64];
		},
		getRenderEyeAngles: () => opts.angles || [0, 45, 0],
	});
	let listener = null;
	const mirv = {
		message: (m) => game.log.push(m.trim()),
		exec: (c) => {
			game.cmds.push(c);
			let m;
			if ((m = c.match(/^playdemo "(.*)"$/))) { game.loadFrames = 20; }
			else if ((m = c.match(/^demo_gototick (\d+)$/))) { if (game.seekWorks) game.tick = Number(m[1]); }
			else if ((m = c.match(/^spec_player (\d+)$/))) {
				if (game.tick >= (opts.rejectSpecBefore || 0)) game.observed = Number(m[1]);
			}
			else if ((m = c.match(/^spec_mode (\d+)$/))) { game.mode = Number(m[1]); }
			else if ((m = c.match(/^cl_drawhud (\d+)$/))) { game.hud = Number(m[1]); }
			else if ((m = c.match(/^mirv_streams record name ".*\/([^/]+)"$/))) { game.recordId = m[1]; }
			else if (c === 'mirv_streams record start') { game.recording = { id: game.recordId, start: game.tick, frames: 0, views: [] }; }
			else if (c === 'mirv_streams record end') { if (game.recording) game.takes.push(game.recording); game.recording = null; }
			else if (c === 'quit') { game.quit = true; }
			else if (c === 'demo_resume') { game.paused = false; }
		},
		getDemoTick: () => (game.playing ? game.tick : undefined),
		getDemoTime: () => (game.playing ? game.tick / 64 : undefined),
		isPlayingDemo: () => game.playing,
		isDemoPaused: () => game.paused,
		getHighestEntityIndex: () => 64,
		getEntityFromIndex: (i) => (i === 100 || i in controllers || i >= 1000 ? ent(i) : null),
		getEntityFromSplitScreenPlayer: () => ent(99),
		getHandleEntryIndex: (h) => h,
		events: {
			clientFrameStageNotify: { on: (n, cb) => { listener = cb; } },
			...(!opts.noViewApi ? { cViewRenderSetupView: { on: (n, cb) => { game.viewListener = cb; } } } : {}),
		},
	};

	const src = fs.readFileSync(path.join(__dirname, '..', 'povforge', 'director.js'), 'utf8')
		.replace('__POVFORGE_JOB__', JSON.stringify(job));
	new Function('mirv', src)(mirv);

	for (let f = 0; f < 20000 && !game.quit; f++) {
		if (opts.loseTargetAt !== undefined && game.tick === opts.loseTargetAt) game.observed = 2;
		// several stages per frame, like the real game
		for (const st of [0, 5, game.stage]) listener({ isBefore: true, curStage: st });
		for (const st of [0, 5, game.stage]) listener({ isBefore: false, curStage: st });
		if (game.viewListener) {
			const event = { curTime: game.tick / 64 + (opts.timeOffset || 0), result: undefined,
				gameView:{x:100,y:900,z:80,rX:0,rY:75,rZ:0,fov:90} };
			const view = game.viewListener(event);
			if (game.recording && view) game.recording.views.push(view);
		}
		if (game.loadFrames > 0 && --game.loadFrames === 0) { game.playing = true; game.tick = 1; }
		else if (game.playing && !game.paused) {
			game.tick++;
			if (game.recording) {
				game.recording.frames++;
				const clip = job.clips.find((c) => c.id === game.recording.id);
				const target = Object.keys(controllers).find((i) => controllers[i] === (clip.steamid || job.steamid));
				if (game.observed !== Number(target)) game.recording.wrongCam = (game.recording.wrongCam || 0) + 1;
				if (clip.cam && clip.cam !== 'pov' && (game.hud !== 0 || game.mode !== 3)) game.recording.wrongMode = true;
				if ((!clip.cam || clip.cam === 'pov') && (game.hud !== 1 || game.mode !== 2)) game.recording.wrongMode = true;
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

// 6. Main and victim clips use native first person with no view override.
{
    const clips = [{id:'main',start:1000,end:1100},
        {id:'victim1',start:1200,end:1280,cam:'pov',steamid:'111'},
        {id:'victim2',start:1400,end:1480,cam:'pov',steamid:'222'}];
    const {game} = runScenario('replays', {job:{clips, specMode:'3'}, noViewApi:true, failCameraAt:0});
    check('replays: all requested players recorded in first person',
        game.takes.length === 3 && game.takes.every(t => !t.wrongCam && !t.wrongMode), game.log);
    check('replays: never reads custom camera or hides HUD',
        game.cameraReadTicks.length === 0 && !game.cmds.includes('cl_drawhud 0') && !game.cmds.includes('spec_mode 3'), game.cmds);
}
for (const cam of ['follow','orbit','wide']) {
    const {game} = runScenario('legacy camera', {job:{clips:[{id:'old',start:1000,end:1100,cam}]}});
    check('legacy ' + cam + ': rejected before loading demo', game.quit && game.takes.length === 0 &&
        !game.cmds.some(c => c.startsWith('playdemo')) && game.log.some(l => l.includes('ERROR')), game.log);
}
{
    const {game} = runScenario('missing victim', {job:{clips:[{id:'victim',start:1000,end:1100,cam:'pov',steamid:'999'}]}});
    check('missing victim: never records the wrong player', game.quit && game.takes.length === 0, game.log);
}
{
    const {game} = runScenario('target changes', {loseTargetAt:1040});
    check('target change: fails instead of capturing another player',
        game.quit && game.takes.length === 1 && game.takes[0].frames === 40 &&
        game.log.some(l => l.includes('why=camera_error')), game.log);
}
{
    const {game} = runScenario('already following in chase mode', {observed:7, mode:3, noObserverMode:true});
    check('first person is requested even without observer-mode API',
        game.takes.length === 2 && game.takes.every(t => !t.wrongMode), game.log);
}
// 7. Victim replays run past the death: CS2's own death view plays untouched,
// and the camera leaving the dead victim ends the take cleanly (not an error).
{
    const victim = {id:'victim',start:1000,end:1256,cam:'pov',steamid:'222',death:1192};
    const {game} = runScenario('victim after death', {job:{clips:[victim]}, loseTargetAt:1230});
    const take = game.takes[0];
    check('after death: one take that ends when the camera leaves the victim',
        game.quit && game.takes.length === 1 && take.frames === 230 &&
        game.log.some(l => l.includes('END victim') && l.includes('why=after_death')) &&
        !game.log.some(l => l.includes('why=camera_error')), game.log);
    const lastTick = game.cmds.lastIndexOf('mirv_streams record start');
    const afterStart = game.cmds.slice(lastTick);
    check('after death: no spectator commands once recording (death view untouched)',
        !afterStart.some(c => c.startsWith('spec_')), afterStart);
}
{
    const victim = {id:'victim',start:1000,end:1256,cam:'pov',steamid:'222',death:1192};
    const {game} = runScenario('victim stays', {job:{clips:[victim]}});
    check('after death: camera that stays on the victim records to the planned end',
        game.takes.length === 1 && game.takes[0].frames === 256 &&
        game.log.some(l => l.includes('END victim') && l.includes('why=end_tick')), game.log);
}
{
    const victim = {id:'victim',start:1000,end:1256,cam:'pov',steamid:'222',death:1192};
    const {game} = runScenario('victim lost early', {job:{clips:[victim]}, loseTargetAt:1100});
    check('before death: losing the victim is still a camera error',
        game.takes.length === 1 && game.log.some(l => l.includes('why=camera_error')), game.log);
}
process.exitCode = failed ? 1 : 0;
