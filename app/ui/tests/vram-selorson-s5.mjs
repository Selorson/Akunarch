/**
 * Kế hoạch VRAM v2 · mục 6 · Kịch bản 5 — Selorson Admin (app.exe đã hot-swap, chế độ người dùng thật).
 * /stories (đo trước) → /world?space=open → "Bước vào Thế giới mở 3D" → đi WASD 30 s (đo giữa chừng)
 * → về /stories, chờ 3 s → đo sau. PASS: VRAM cây app.exe sau khi rời ≤ trước khi vào /world + 20 MB.
 *
 * Chạy: node tests/vram-selorson-s5.mjs --phase c3_s5_r1 [--exe <app.exe>]
 * Chỉ đọc dữ liệu (không ghi gì vào Selorson); CDP qua WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS.
 */
import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import WebSocket from 'ws';

const args = Object.fromEntries(
	process.argv.slice(2).reduce((acc, cur, i, arr) => {
		if (cur.startsWith('--')) acc.push([cur.slice(2), arr[i + 1]]);
		return acc;
	}, [])
);
const EXE = args.exe ?? path.join(process.env.LOCALAPPDATA, 'Selorson Admin', 'app.exe');
const PHASE = args.phase ?? 'c3_s5';
const PORT = 9242;
const MEASURE_PS1 = 'E:\\Akunarch\\bin\\scripts\\measure_vram.ps1';
const OUT_DIR = 'E:\\Akunarch\\docs\\vram';
const SHOT_DIR = path.join(OUT_DIR, 'screenshots', PHASE);
fs.mkdirSync(SHOT_DIR, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(`[${new Date().toISOString().slice(11, 19)}]`, ...a);
const results = { phase: PHASE, exe: EXE, started: new Date().toISOString(), measurements: {}, notes: [] };

function measure(label, seconds = 8) {
	const out = execFileSync(
		'powershell',
		['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MEASURE_PS1, '-Label', `${PHASE}_${label}`, '-Seconds', String(seconds), '-ProcessName', 'app'],
		{ encoding: 'utf8', timeout: 120000 }
	);
	const m = JSON.parse(out.trim().split(/\r?\n/).filter((l) => l.startsWith('{')).pop());
	results.measurements[label] = m;
	log(`MEASURE ${label}: app=${m.app_vram_mb_median}MB (max ${m.app_vram_mb_max}) app3D=${m.app_gpu3d_pct_avg}% gpu=${m.gpu_util_avg}%`);
	return m;
}
function measureAsync(label, seconds) {
	return new Promise((resolve) => {
		const child = spawn('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MEASURE_PS1, '-Label', `${PHASE}_${label}`, '-Seconds', String(seconds), '-ProcessName', 'app'], { stdio: ['ignore', 'pipe', 'ignore'] });
		let out = '';
		child.stdout.on('data', (d) => (out += d));
		child.on('close', () => {
			const m = JSON.parse(out.trim().split(/\r?\n/).filter((l) => l.startsWith('{')).pop());
			results.measurements[label] = m;
			log(`MEASURE ${label}: app=${m.app_vram_mb_median}MB (max ${m.app_vram_mb_max}) app3D=${m.app_gpu3d_pct_avg}%`);
			resolve(m);
		});
	});
}

const getJson = (u) =>
	new Promise((res, rej) =>
		http.get(u, (r) => { let d = ''; r.on('data', (c) => (d += c)); r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { rej(e); } }); }).on('error', rej)
	);

const PROBE = `(() => { if (window.__vramProbe) return; const probe = { created: 0, lost: 0 }; window.__vramProbe = probe;
	const orig = HTMLCanvasElement.prototype.getContext; const seen = new WeakSet();
	HTMLCanvasElement.prototype.getContext = function (t, a) { const ctx = orig.call(this, t, a);
		if (ctx && /webgl/i.test(String(t)) && !seen.has(ctx)) { seen.add(ctx); probe.created++; this.addEventListener('webglcontextlost', () => probe.lost++); }
		return ctx; }; })();`;

// Chỉ diệt đúng Selorson Admin (theo đường dẫn exe) — "app.exe" là tên chung, không dùng taskkill /IM
function killSelorson() {
	try {
		execFileSync('powershell', ['-NoProfile', '-Command',
			`Get-Process app -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq '${EXE.replace(/'/g, "''")}' } | ForEach-Object { taskkill /F /T /PID $_.Id | Out-Null }`], { stdio: 'ignore' });
	} catch { /* chưa chạy */ }
}

async function main() {
	killSelorson();
	await sleep(1500);
	const env = { ...process.env, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${PORT} --remote-allow-origins=*` };
	delete env.WEBVIEW2_USER_DATA_FOLDER;
	const proc = spawn(EXE, [], { env, stdio: 'ignore' });
	let ws = null;
	try {
		let target = null;
		for (let i = 0; i < 120 && !target; i++) {
			try { target = (await getJson(`http://127.0.0.1:${PORT}/json/list`)).find((t) => t.type === 'page'); } catch { /* chờ */ }
			if (!target) await sleep(500);
		}
		if (!target) throw new Error('Không thấy CDP target của Selorson Admin');
		ws = new WebSocket(target.webSocketDebuggerUrl);
		await new Promise((r) => ws.once('open', r));
		let seq = 0;
		const pend = new Map();
		const consoleLines = [];
		ws.on('message', (d) => {
			const m = JSON.parse(String(d));
			if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
			else if (m.method === 'Runtime.consoleAPICalled') consoleLines.push(m.params.args.map((a) => a.value ?? a.description ?? '').join(' '));
		});
		const send = (method, params = {}) => new Promise((r) => { const id = ++seq; pend.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
		const ev = async (expression) => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result?.result?.value;
		const shot = async (name) => { const s = await send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(path.join(SHOT_DIR, name), Buffer.from(s.result.data, 'base64')); log('SHOT', name); };
		const go = (href) => ev(`(() => { const a = document.createElement('a'); a.href = ${JSON.stringify(href)}; document.body.appendChild(a); a.click(); a.remove(); return location.pathname; })()`);
		const key = (type, code, k) => send('Input.dispatchKeyEvent', { type, code, key: k, windowsVirtualKeyCode: k.toUpperCase().charCodeAt(0) });

		await send('Page.enable');
		await send('Runtime.enable');
		await send('Page.addScriptToEvaluateOnNewDocument', { source: PROBE });
		await send('Page.reload', {});
		await sleep(6000);

		await go('/stories');
		await sleep(4000);
		results.notes.push(`Trang trước: ${await ev('location.pathname')}`);
		const before = measure('S5_before_world');

		await go('/world?space=open');
		let ready = false;
		for (let i = 0; i < 60 && !ready; i++) {
			ready = await ev(`Boolean(Array.from(document.querySelectorAll('button')).find(b => /Thế Giới Mở 3D|Walk 3D Open World/.test(b.textContent)))`);
			if (!ready) await sleep(500);
		}
		let chunks = await ev(`document.querySelectorAll('.chunk-card').length`);
		if (!ready) {
			// Thử hành tinh còn lại (Trái Đất)
			await ev(`Array.from(document.querySelectorAll('button')).find(b => /Trái Đất|Earth/.test(b.textContent) && b.closest('.ow-workspace, main, section'))?.click()`);
			await sleep(2000);
			ready = await ev(`Boolean(Array.from(document.querySelectorAll('button')).find(b => /Thế Giới Mở 3D|Walk 3D Open World/.test(b.textContent)))`);
			chunks = await ev(`document.querySelectorAll('.chunk-card').length`);
		}
		results.notes.push(`/world?space=open: ${chunks} ô chunk; nút Bước vào 3D: ${ready}`);
		await shot('S5_world_open.png');
		let inWorld;
		if (ready) {
			results.mode = 'open_world_wasd';
			await ev(`Array.from(document.querySelectorAll('button')).find(b => /Thế Giới Mở 3D|Walk 3D Open World/.test(b.textContent))?.click()`);
			await sleep(6000);
			results.notes.push(`Canvas Thế giới mở: ${await ev(`Boolean(document.querySelector('.ow-webgl-shell canvas'))`)}`);
			// WASD 30 s (giữ phím; tick đọc tập pressedKeys) + đo giữa chừng
			const walk = (async () => {
				for (const [code, k, ms] of [['KeyW', 'w', 12000], ['KeyD', 'd', 6000], ['KeyS', 's', 6000], ['KeyA', 'a', 6000]]) {
					await key('keyDown', code, k);
					await sleep(ms);
					await key('keyUp', code, k);
				}
			})();
			await sleep(8000);
			inWorld = await measureAsync('S5_in_world_wasd', 8);
			await shot('S5_world_walking.png');
			await walk;
		} else {
			// Chưa có chunk nào → đo Bản đồ 3D Sa bàn (WorldCanvas/Threlte — nơi C1 thêm purge cache): xoay quả cầu 30 s
			results.mode = 'globe_sa_ban_fallback';
			results.notes.push('CHƯA KIỂM phần Thế giới mở WASD: Selorson local chưa có ô chunk (0). Đo thay bằng Bản đồ 3D Sa bàn (Threlte).');
			await ev(`Array.from(document.querySelectorAll('button')).find(b => /^\s*(Sa bàn|Clockwork)\s*$/.test(b.textContent))?.click()`);
			let canvasOk = false;
			for (let i = 0; i < 40 && !canvasOk; i++) {
				canvasOk = await ev(`Boolean(document.querySelector('canvas'))`);
				if (!canvasOk) await sleep(500);
			}
			results.notes.push(`Canvas Sa bàn 3D: ${canvasOk}`);
			await sleep(4000);
			const spin = (async () => {
				const r = await ev(`(() => { const c = document.querySelector('canvas'); const b = c?.getBoundingClientRect(); return b ? { x: b.left + b.width / 2, y: b.top + b.height / 2 } : { x: 600, y: 400 }; })()`);
				const t0 = Date.now();
				while (Date.now() - t0 < 30000) {
					await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: r.x - 150, y: r.y, button: 'left', clickCount: 1 });
					for (let i = 1; i <= 30; i++) {
						await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: r.x - 150 + i * 10, y: r.y + Math.sin(i / 5) * 20, button: 'left', buttons: 1 });
						await sleep(33);
					}
					await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: r.x + 150, y: r.y, button: 'left', clickCount: 1 });
					await sleep(300);
				}
			})();
			await sleep(8000);
			inWorld = await measureAsync('S5_in_world_globe', 8);
			await shot('S5_world_globe.png');
			await spin;
		}

		await go('/stories');
		await sleep(3000);
		const after = measure('S5_after_leave_3s');
		await shot('S5_after_leave.png');
		// Kiểm cộng dồn: vào/ra Sa bàn 3D thêm (visits − 1) lần, đo sau mỗi lần rời
		const visits = Number(args.visits ?? 1);
		results.leak_curve = [after.app_vram_mb_median];
		for (let v = 2; v <= visits; v++) {
			await go('/world');
			await sleep(1500);
			await ev(`Array.from(document.querySelectorAll('button')).find(b => /^\s*(Sa bàn|Clockwork)\s*$/.test(b.textContent))?.click()`);
			for (let i = 0; i < 40; i++) { if (await ev(`Boolean(document.querySelector('canvas'))`)) break; await sleep(500); }
			await sleep(8000);
			await go('/stories');
			await sleep(3000);
			results.leak_curve.push(measure(`S5_after_leave_visit${v}`, 6).app_vram_mb_median);
		}
		if (visits > 1) log('LEAK CURVE', JSON.stringify(results.leak_curve));
		if (args.gc === 'true') {
			// Chẩn đoán: VRAM còn giữ có phải context WebGL chờ GC không?
			await send('HeapProfiler.enable');
			await send('HeapProfiler.collectGarbage');
			await sleep(4000);
			results.after_gc = measure('S5_after_leave_gc', 6);
			const proto = await send('Runtime.evaluate', { expression: 'HTMLCanvasElement.prototype' });
			const q = await send('Runtime.queryObjects', { prototypeObjectId: proto.result.result.objectId });
			const cnt = await send('Runtime.callFunctionOn', { objectId: q.result.objects.objectId, functionDeclaration: 'function () { return this.map(c => ({ w: c.width, h: c.height, inDom: c.isConnected, gl: Boolean(c.__probeGl) })); }', returnByValue: true });
			results.live_canvases = cnt.result.result.value;
			log('LIVE CANVASES', JSON.stringify(results.live_canvases));
			if (args.snapshot) {
				// Chẩn đoán: chụp heap snapshot để tìm chuỗi giữ tham chiếu (retainer) của canvas bị tách khỏi DOM
				const chunks = [];
				const onMsg = (d) => { const m = JSON.parse(String(d)); if (m.method === 'HeapProfiler.addHeapSnapshotChunk') chunks.push(m.params.chunk); };
				ws.on('message', onMsg);
				await send('HeapProfiler.takeHeapSnapshot', { reportProgress: false });
				ws.off('message', onMsg);
				fs.writeFileSync(args.snapshot, chunks.join(''));
				log('SNAPSHOT', args.snapshot, chunks.join('').length);
			}
		}
		const probe = await ev(`JSON.parse(JSON.stringify(window.__vramProbe || {}))`);
		results.probe = probe;
		const delta = +(after.app_vram_mb_median - before.app_vram_mb_median).toFixed(1);
		results.summary = {
			before_mb: before.app_vram_mb_median,
			in_world_mb: inWorld.app_vram_mb_median,
			after_mb: after.app_vram_mb_median,
			delta_mb: delta,
			pass: delta <= 20,
			webgl_created: probe.created,
			webgl_lost: probe.lost
		};
		results.consoleErrors = consoleLines.filter((l) => /error|lỗi/i.test(l)).slice(0, 20);
		log('S5', JSON.stringify(results.summary));
	} catch (e) {
		results.error = String(e?.message ?? e);
		log('LỖI', results.error);
	} finally {
		try { ws?.close(); } catch { /* bỏ qua */ }
		killSelorson();
		proc.kill();
		results.finished = new Date().toISOString();
		fs.writeFileSync(path.join(OUT_DIR, `scenarios_${PHASE}.json`), JSON.stringify(results, null, 2));
	}
}
main();
