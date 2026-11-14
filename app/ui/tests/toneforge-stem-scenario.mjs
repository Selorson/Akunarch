// Đo RAM/VRAM ToneForge quanh một lần tách stem UVR5 (đợt tối ưu tài nguyên 2026-11-14).
// Mở ToneForge kèm cổng gỡ lỗi WebView2 → invoke lệnh Tauri (nạp file thử tổng hợp, tách stem) → đo → rảnh → đóng → đo sót.
// CHỈ chạy khi anh cho phép (mở/đóng app thật). File âm thanh là tín hiệu tổng hợp, không đụng nhạc của anh.
// Chạy: node tests/toneforge-stem-scenario.mjs --tag baseline [--idle 300] [--exe <ToneForge_Studio.exe>]
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import WebSocket from 'ws';

const args = Object.fromEntries(
	process.argv.slice(2).reduce((acc, cur, i, arr) => {
		if (cur.startsWith('--')) acc.push([cur.slice(2), arr[i + 1]]);
		return acc;
	}, [])
);
const TAG = args.tag ?? 'baseline';
const IDLE = Number(args.idle ?? 300);
const EXE = args.exe ?? 'F:\\FL studio\\toneforge\\ToneForge_Studio.exe';
const PORT = 9334;
const MEASURE = 'E:\\Akunarch\\bin\\scripts\\measure_app_resources.ps1';
const WAV = 'E:\\Akunarch\\_archive\\toi-uu\\toneforge_test_30s.wav';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function measure(label, sec = 10) {
	const r = spawnSync('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MEASURE, '-App', 'toneforge', '-Label', `${TAG}_${label}`, '-Seconds', String(sec)], { encoding: 'utf8' });
	const row = JSON.parse(r.stdout.trim());
	console.log(`${label.padEnd(22)} procs=${row.process_count} priv=${row.ram_private_mb} MB ws=${row.ram_ws_mb} MB vram=${row.vram_mb_median} MB | ${row.processes}`);
	return row;
}

// WAV 48 kHz stereo 16-bit, 30 s: hợp âm + nhịp trống giả + nhiễu nhẹ — đủ để mô hình tách chạy thật.
function writeTestWav(file) {
	const sr = 48000, n = sr * 30, data = Buffer.alloc(n * 4);
	let seed = 7;
	for (let i = 0; i < n; i++) {
		const t = i / sr;
		const chord = 0.12 * (Math.sin(2 * Math.PI * 220 * t) + Math.sin(2 * Math.PI * 277.2 * t) + Math.sin(2 * Math.PI * 329.6 * t));
		const beat = (t * 2) % 1 < 0.05 ? 0.5 * Math.sin(2 * Math.PI * 60 * t) : 0;
		seed = (seed * 1103515245 + 12345) & 0x7fffffff;
		const noise = ((seed / 0x7fffffff) - 0.5) * 0.04;
		const vox = 0.15 * Math.sin(2 * Math.PI * (440 + 30 * Math.sin(2 * Math.PI * 5 * t)) * t) * ((t % 4) < 2 ? 1 : 0);
		const l = Math.max(-1, Math.min(1, chord + beat + noise + vox));
		const r = Math.max(-1, Math.min(1, chord + beat - noise + 0.8 * vox));
		data.writeInt16LE(Math.round(l * 32767), i * 4);
		data.writeInt16LE(Math.round(r * 32767), i * 4 + 2);
	}
	const h = Buffer.alloc(44);
	h.write('RIFF', 0); h.writeUInt32LE(36 + data.length, 4); h.write('WAVE', 8); h.write('fmt ', 12);
	h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(2, 22); h.writeUInt32LE(sr, 24);
	h.writeUInt32LE(sr * 4, 28); h.writeUInt16LE(4, 32); h.writeUInt16LE(16, 34); h.write('data', 36); h.writeUInt32LE(data.length, 40);
	fs.mkdirSync(path.dirname(file), { recursive: true });
	fs.writeFileSync(file, Buffer.concat([h, data]));
}

function getJson(url) {
	return new Promise((res, rej) => http.get(url, (r) => { let b = ''; r.on('data', (c) => (b += c)); r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(e); } }); }).on('error', rej));
}

async function connectPage() {
	for (let i = 0; i < 90; i++) {
		try {
			const list = await getJson(`http://127.0.0.1:${PORT}/json/list`);
			const page = list.find((t) => t.type === 'page');
			if (page) return page.webSocketDebuggerUrl;
		} catch { /* chưa lên */ }
		await sleep(1000);
	}
	throw new Error('ToneForge không mở cổng gỡ lỗi sau 90 s');
}

function cdp(wsUrl) {
	const ws = new WebSocket(wsUrl, { perMessageDeflate: false });
	let id = 0; const pending = new Map();
	ws.on('message', (m) => { const msg = JSON.parse(m); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } });
	const ready = new Promise((r) => ws.once('open', r));
	return {
		ready,
		async evaluate(expr) {
			const myId = ++id;
			const p = new Promise((r) => pending.set(myId, r));
			ws.send(JSON.stringify({ id: myId, method: 'Runtime.evaluate', params: { expression: expr, awaitPromise: true, returnByValue: true } }));
			const msg = await p;
			if (msg.result?.exceptionDetails) throw new Error(JSON.stringify(msg.result.exceptionDetails).slice(0, 800));
			return msg.result?.result?.value;
		},
		close: () => ws.close()
	};
}

const pre = measure('before', 2);
if (pre.process_count > 0) throw new Error('ToneForge đang mở sẵn — anh đang dùng? Dừng kịch bản.');
writeTestWav(WAV);

const child = spawn(EXE, [], { detached: true, stdio: 'ignore', env: { ...process.env, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${PORT}` } });
child.unref();
const page = cdp(await connectPage());
await page.ready;
await sleep(15000);
measure('open');

const wavJs = JSON.stringify(WAV);
const load = await page.evaluate(`window.__TAURI__.core.invoke('cmd_load_audio_from_path_native', { filePath: ${wavJs} }).then(r => JSON.stringify(r).slice(0, 200))`);
console.log('load:', load);
async function separate(label) {
	const t0 = Date.now();
	await page.evaluate(`window.__TAURI__.core.invoke('cmd_run_uvr5_separation', { req: { audioPath: ${wavJs}, bounceToMixer: false } }).then(() => 1)`);
	console.log(`${label}: ${((Date.now() - t0) / 1000).toFixed(1)} s`);
}
await separate('separation');
measure('after_separation');
// --warm true: tách lần 2 ngay khi bộ tách còn nạp sẵn → cái giá của việc nhả = (lần sau khi nhả) − (lần nóng)
if (args.warm === 'true') await separate('separation_warm');

if (IDLE > 0) { await sleep(IDLE * 1000); measure(`idle_${IDLE}s`); }
if (args.warm === 'true') { await separate('separation_after_release'); measure('after_separation_3'); }
page.close();

const procName = path.basename(EXE, '.exe');
spawnSync('powershell', ['-NoProfile', '-Command', `Get-Process '${procName}' -ErrorAction SilentlyContinue | ForEach-Object { [void]$_.CloseMainWindow() }`]);
await sleep(8000);
measure('after_close', 3);
