/**
 * Akunarch — Kịch bản đo VRAM Đợt A (Kế hoạch VRAM v2, mục 3 & 6).
 *
 * Chạy: node tests/vram-scenarios.mjs --exe <đường dẫn akunarch.exe> --phase <baseline|after>
 *
 * - Chế độ người dùng thật (Luật #2): đọc E:\Akunarch\projects + %LOCALAPPDATA%\Akunarch\akunarch.db,
 *   KHÔNG đặt AKUNARCH_DATA_DIR / AKUNARCH_PROJECTS_DIR / WEBVIEW2_USER_DATA_FOLDER.
 *   Chỉ thêm cổng CDP qua WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS (giữ nguyên cờ GPU của tauri.conf.json).
 * - Số đo VRAM/GPU lấy từ E:\Akunarch\bin\scripts\measure_vram.ps1 (PDH + nvidia-smi).
 * - Kịch bản điêu khắc ghi thật vào 2 ô chunk → sao lưu trước, khôi phục + so SHA-256 sau.
 */

import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { execFileSync, execSync, spawn } from 'node:child_process';
import WebSocket from 'ws';

const args = Object.fromEntries(
	process.argv.slice(2).reduce((acc, cur, i, arr) => {
		if (cur.startsWith('--')) acc.push([cur.slice(2), arr[i + 1]?.startsWith('--') ? 'true' : arr[i + 1]]);
		return acc;
	}, [])
);
const EXE = args.exe ?? 'C:\\Users\\Admin\\AppData\\Local\\Akunarch\\akunarch.exe';
const PHASE = args.phase ?? 'baseline';
const ONLY = (args.only ?? 'S0,S1,S2,SC,S3,S4').split(',');
const CDP_PORT = 9241;
const MEASURE_PS1 = 'E:\\Akunarch\\bin\\scripts\\measure_vram.ps1';
const OUT_DIR = 'E:\\Akunarch\\docs\\vram';
const SHOT_DIR = path.join(OUT_DIR, 'screenshots', PHASE);
const BACKUP_DIR = `E:\\Akunarch\\_archive\\vram_dot_A\\data_backup_${PHASE}`;
const PROJECTS_ROOT = 'E:\\Akunarch\\projects';
const DB_DIR = path.join(process.env.LOCALAPPDATA, 'Akunarch');
const SCULPT_CHUNKS = ['chunk-akunalia-0-0', 'chunk-akunalia-1-0'];
const WONDERS = args.wonders ? args.wonders.split(',') : ['temple-of-zyberon', 'singularity-samos-olympus', 'singularity-stonehenge-avalon', 'avalon-mage-sanctum'];
const SCULPT_STROKES = Number(args.strokes ?? 20);
const ROUNDS = Number(args.rounds ?? 3);
const TOGGLES = Number(args.toggles ?? 30);

fs.mkdirSync(SHOT_DIR, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = { phase: PHASE, exe: EXE, started: new Date().toISOString(), measurements: {}, probes: {}, notes: [] };

function log(...a) {
	console.log(`[${new Date().toISOString().slice(11, 19)}]`, ...a);
}

function measure(label, seconds = 10) {
	const out = execFileSync(
		'powershell',
		['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MEASURE_PS1, '-Label', `${PHASE}_${label}`, '-Seconds', String(seconds)],
		{ encoding: 'utf8', timeout: 120000 }
	);
	const line = out.trim().split(/\r?\n/).filter((l) => l.startsWith('{')).pop();
	const parsed = JSON.parse(line);
	results.measurements[label] = parsed;
	log(`MEASURE ${label}: app=${parsed.app_vram_mb_median}MB (max ${parsed.app_vram_mb_max}) app3D=${parsed.app_gpu3d_pct_avg}% gpu=${parsed.gpu_util_avg}% ${parsed.gpu_pstate_mode} ${parsed.gpu_power_w_avg}W`);
	return parsed;
}

// ---------- Sao lưu / khôi phục dữ liệu bị kịch bản điêu khắc ghi ----------
function sha256(file) {
	return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}
function listFilesRec(dir) {
	const out = [];
	for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
		const p = path.join(dir, e.name);
		if (e.isDirectory()) out.push(...listFilesRec(p));
		else out.push(p);
	}
	return out;
}
function dataFiles() {
	const files = [];
	for (const slug of SCULPT_CHUNKS) files.push(...listFilesRec(path.join(PROJECTS_ROOT, slug)));
	for (const n of ['akunarch.db', 'akunarch.db-wal', 'akunarch.db-shm']) {
		const p = path.join(DB_DIR, n);
		if (fs.existsSync(p)) files.push(p);
	}
	return files;
}
function backupData() {
	fs.rmSync(BACKUP_DIR, { recursive: true, force: true });
	const manifest = {};
	for (const f of dataFiles()) {
		const rel = f.replace(/^[A-Za-z]:\\/, '').replace(/[\\:]/g, '__');
		fs.mkdirSync(BACKUP_DIR, { recursive: true });
		fs.copyFileSync(f, path.join(BACKUP_DIR, rel));
		manifest[f] = { rel, sha: sha256(f) };
	}
	fs.writeFileSync(path.join(BACKUP_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2));
	log(`BACKUP ${Object.keys(manifest).length} files -> ${BACKUP_DIR}`);
	return manifest;
}
function restoreData(manifest, backupDir = BACKUP_DIR, filesFn = dataFiles, what = 'chunk + akunarch.db') {
	// Xóa file mới sinh ra trong vùng sao lưu (nếu có) rồi chép lại bản sao lưu
	for (const f of filesFn()) {
		if (!manifest[f]) fs.rmSync(f, { force: true });
	}
	let mismatch = 0;
	for (const [orig, { rel, sha }] of Object.entries(manifest)) {
		fs.mkdirSync(path.dirname(orig), { recursive: true });
		fs.copyFileSync(path.join(backupDir, rel), orig);
		if (sha256(orig) !== sha) mismatch++;
	}
	assert.equal(mismatch, 0, `Khôi phục dữ liệu ${what} không khớp SHA-256!`);
	log(`RESTORE OK (${what}): ${Object.keys(manifest).length} files, SHA-256 khớp 100%`);
	results.notes.push(`Dữ liệu ${what} đã khôi phục, ${Object.keys(manifest).length} file khớp SHA-256.`);
}

// B0 (Đợt B): nút Chụp Manga 2K ghi vào project.akun.json + manga_plates\ + stage_vn\ của MỌI dự án + DB
const META_BACKUP_DIR = `E:\\Akunarch\\_archive\\vram_dot_B\\data_backup_${PHASE}_meta`;
function metaFiles() {
	const files = [];
	for (const slug of fs.readdirSync(PROJECTS_ROOT)) {
		const dir = path.join(PROJECTS_ROOT, slug);
		if (!fs.statSync(dir).isDirectory()) continue;
		const pj = path.join(dir, 'project.akun.json');
		if (fs.existsSync(pj)) files.push(pj);
		for (const sub of ['manga_plates', 'stage_vn']) {
			const p = path.join(dir, sub);
			if (fs.existsSync(p)) files.push(...listFilesRec(p));
		}
	}
	for (const n of ['akunarch.db', 'akunarch.db-wal', 'akunarch.db-shm']) {
		const p = path.join(DB_DIR, n);
		if (fs.existsSync(p)) files.push(p);
	}
	return files;
}
function backupMeta() {
	fs.rmSync(META_BACKUP_DIR, { recursive: true, force: true });
	fs.mkdirSync(META_BACKUP_DIR, { recursive: true });
	const manifest = {};
	for (const f of metaFiles()) {
		const rel = f.replace(/^[A-Za-z]:\\/, '').replace(/[\\:]/g, '__');
		fs.copyFileSync(f, path.join(META_BACKUP_DIR, rel));
		manifest[f] = { rel, sha: sha256(f) };
	}
	fs.writeFileSync(path.join(META_BACKUP_DIR, 'manifest.json'), JSON.stringify(manifest, null, 2));
	log(`BACKUP META ${Object.keys(manifest).length} files -> ${META_BACKUP_DIR}`);
	return manifest;
}

// ---------- CDP ----------
function fetchJson(url) {
	return new Promise((resolve, reject) => {
		http
			.get(url, (res) => {
				let raw = '';
				res.on('data', (c) => (raw += c));
				res.on('end', () => {
					try {
						resolve(JSON.parse(raw));
					} catch (e) {
						reject(e);
					}
				});
			})
			.on('error', reject);
	});
}
async function waitForTarget(maxMs = 30000) {
	const deadline = Date.now() + maxMs;
	while (Date.now() < deadline) {
		try {
			const t = (await fetchJson(`http://127.0.0.1:${CDP_PORT}/json/list`)).find(
				(x) => x.type === 'page' && String(x.url).includes('localhost')
			);
			if (t?.webSocketDebuggerUrl) return t;
		} catch {
			// chờ cổng CDP
		}
		await sleep(400);
	}
	throw new Error('Không thấy CDP target');
}
class Cdp {
	constructor(url) {
		this.ws = new WebSocket(url);
		this.seq = 0;
		this.pending = new Map();
		this.console = [];
	}
	async connect() {
		await new Promise((res, rej) => {
			this.ws.once('open', res);
			this.ws.once('error', rej);
		});
		this.ws.on('message', (data) => {
			const msg = JSON.parse(String(data));
			if (msg.id && this.pending.has(msg.id)) {
				const { resolve, reject } = this.pending.get(msg.id);
				this.pending.delete(msg.id);
				msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
			} else if (msg.method === 'Runtime.consoleAPICalled') {
				this.console.push(msg.params.args.map((a) => a.value ?? a.description ?? '').join(' '));
			} else if (msg.method === 'Log.entryAdded') {
				this.console.push(msg.params.entry.text);
			}
		});
	}
	send(method, params = {}) {
		const id = ++this.seq;
		return new Promise((resolve, reject) => {
			const t = setTimeout(() => reject(new Error(`CDP timeout ${method}`)), 30000);
			this.pending.set(id, {
				resolve: (v) => (clearTimeout(t), resolve(v)),
				reject: (e) => (clearTimeout(t), reject(e))
			});
			this.ws.send(JSON.stringify({ id, method, params }));
		});
	}
	async eval(expression) {
		const r = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
		if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400));
		return r.result?.value;
	}
	async shot(name) {
		await sleep(400);
		const s = await this.send('Page.captureScreenshot', { format: 'png' });
		const p = path.join(SHOT_DIR, name);
		fs.writeFileSync(p, Buffer.from(s.data, 'base64'));
		log(`SHOT ${p}`);
	}
	/** Chụp đúng vùng phần tử `selector` (CSS px). Trả về Buffer PNG (null nếu không thấy phần tử). */
	async clipShot(selector, name) {
		await sleep(400);
		const r = await this.eval(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null;
			const b = e.getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
		if (!r || r.width < 2) return null;
		const s = await this.send('Page.captureScreenshot', { format: 'png', clip: { ...r, scale: 1 } });
		const buf = Buffer.from(s.data, 'base64');
		if (name) {
			const p = path.join(SHOT_DIR, name);
			fs.writeFileSync(p, buf);
			log(`SHOT ${p}`);
		}
		return buf;
	}
	async drag(x, y, dx, dy, ms) {
		const steps = Math.max(10, Math.round(ms / 16));
		await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
		await this.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
		for (let i = 1; i <= steps; i++) {
			await this.send('Input.dispatchMouseEvent', {
				type: 'mouseMoved',
				x: x + (dx * i) / steps,
				y: y + (dy * i) / steps,
				button: 'left',
				buttons: 1
			});
			await sleep(ms / steps);
		}
		await this.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: x + dx, y: y + dy, button: 'left', clickCount: 1 });
	}
	async click(x, y) {
		await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
		await this.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
		await sleep(40);
		await this.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
	}
}

// Đếm context WebGL tạo ra / bị mất (cài trước khi app chạy, qua addScriptToEvaluateOnNewDocument)
const PROBE_SCRIPT = `(() => {
	if (window.__vramProbe) return;
	const probe = { created: 0, lost: 0, restored: 0 };
	window.__vramProbe = probe;
	const orig = HTMLCanvasElement.prototype.getContext;
	const seen = new WeakSet();
	HTMLCanvasElement.prototype.getContext = function (type, attrs) {
		const ctx = orig.call(this, type, attrs);
		if (ctx && /webgl/i.test(String(type)) && !seen.has(ctx)) {
			seen.add(ctx);
			probe.created++;
			this.addEventListener('webglcontextlost', () => probe.lost++);
			this.addEventListener('webglcontextrestored', () => probe.restored++);
		}
		return ctx;
	};
})();`;

const NAV = (tab) => `document.querySelector('[data-testid="nav-${tab}"]')?.click()`;

async function waitPbrStage(cdp, maxMs = 20000) {
	const deadline = Date.now() + maxMs;
	let st = null;
	while (Date.now() < deadline) {
		st = await cdp.eval(`(() => {
			document.querySelector('[data-testid="activate-3d-stage-btn"]')?.click();
			const host = document.querySelector('.webgl-mount');
			const c = host?.querySelector('canvas');
			const loading = document.querySelector('.stage-overlay-msg');
			const r = c?.getBoundingClientRect();
			return { has: Boolean(c), loading: Boolean(loading), w: c?.width || 0, h: c?.height || 0,
				x: r ? r.left + r.width / 2 : 0, y: r ? r.top + r.height / 2 : 0 };
		})()`);
		if (st.has && !st.loading && st.w > 100) return st;
		await sleep(250);
	}
	return st;
}
async function waitCanvasIn(cdp, selector, maxMs = 15000) {
	const deadline = Date.now() + maxMs;
	let st = null;
	while (Date.now() < deadline) {
		st = await cdp.eval(`(() => {
			if ('${selector}' === '.viewport-canvas') document.querySelector('[data-testid="activate-chunk-3d-btn"]')?.click();
			const c = document.querySelector('${selector} canvas');
			const r = c?.getBoundingClientRect();
			return { has: Boolean(c), w: c?.width || 0, h: c?.height || 0, x: r ? r.left + r.width / 2 : 0, y: r ? r.top + r.height / 2 : 0 };
		})()`);
		if (st.has && st.w > 100) return st;
		await sleep(250);
	}
	return st;
}
async function probe(cdp, label) {
	const p = await cdp.eval(`JSON.parse(JSON.stringify({ ...(window.__vramProbe || {}), stage: window.__akunarchWebglStage ? window.__akunarchWebglStage() : null }))`);
	const tooMany = cdp.console.filter((l) => /too many active webgl contexts/i.test(l)).length;
	const lostLogs = cdp.console.filter((l) => /context lost|CONTEXT_LOST/i.test(l)).length;
	results.probes[label] = { ...p, consoleTooManyContexts: tooMany, consoleContextLost: lostLogs };
	log(`PROBE ${label}:`, results.probes[label]);
}

// ---------- B3 A/B: tạm thay runtime KTX2 bằng _master JPEG ----------
const KTX_BACKUP_DIR = 'E:/Akunarch/_archive/vram_dot_B/ktx_runtime_swap_backup';
function swapRuntimeWithMaster() {
	fs.mkdirSync(KTX_BACKUP_DIR, { recursive: true });
	const list = [];
	for (const slug of WONDERS) {
		const rt = path.join(PROJECTS_ROOT, slug, 'clockwork', `${slug}.glb`);
		const master = path.join(PROJECTS_ROOT, slug, 'clockwork', '_master', `${slug}.glb`);
		const bak = path.join(KTX_BACKUP_DIR, `${slug}.glb`);
		fs.copyFileSync(rt, bak);
		const sha = sha256(rt);
		assert.equal(sha256(bak), sha, 'sao lưu runtime lệch SHA');
		fs.copyFileSync(master, rt);
		list.push({ rt, bak, sha });
	}
	log(`SWAP: ${list.length} runtime .glb → bản _master (JPEG), bản KTX2 ở ${KTX_BACKUP_DIR}`);
	return list;
}
function restoreRuntimeGlbs(list) {
	for (const { rt, bak, sha } of list) {
		fs.copyFileSync(bak, rt);
		assert.equal(sha256(rt), sha, `Khôi phục ${rt} lệch SHA-256!`);
	}
	log(`RESTORE KTX2 OK: ${list.length} .glb khớp SHA-256`);
	results.notes.push(`Đã khôi phục ${list.length} .glb KTX2, SHA-256 khớp.`);
}

// ---------- B0 helpers ----------
function pngSize(file) {
	const b = fs.readFileSync(file);
	return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), bytes: b.length };
}
/** Sai khác trung bình |ΔRGB| (0–255) giữa 2 ảnh PNG cùng kích thước, giải mã ngay trong trang. */
async function imgDiff(cdp, a, b) {
	if (!a || !b) return -1;
	return cdp.eval(`(async () => {
		const load = (s) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = s; });
		const [A, B] = await Promise.all([load('data:image/png;base64,${a.toString('base64')}'), load('data:image/png;base64,${b.toString('base64')}')]);
		const w = Math.min(A.width, B.width), h = Math.min(A.height, B.height);
		const px = (img) => { const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); g.drawImage(img, 0, 0); return g.getImageData(0, 0, w, h).data; };
		const da = px(A), db = px(B);
		let s = 0; for (let i = 0; i < da.length; i += 4) s += Math.abs(da[i] - db[i]) + Math.abs(da[i + 1] - db[i + 1]) + Math.abs(da[i + 2] - db[i + 2]);
		return +(s / (w * h * 3)).toFixed(3);
	})()`);
}
function plateFiles(slug) {
	const dir = path.join(PROJECTS_ROOT, slug, 'manga_plates');
	return fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => /^plate_.*\.png$/.test(f)) : [];
}
/** Chờ cặp plate mới (beauty+depth) xuất hiện, chép sang thư mục ảnh nghiệm thu, trả kích thước + dung lượng. */
async function waitNewPlates(slug, before, tag, maxMs = 25000) {
	const deadline = Date.now() + maxMs;
	while (Date.now() < deadline) {
		const fresh = plateFiles(slug).filter((f) => !before.includes(f));
		if (fresh.some((f) => f.endsWith('_beauty.png')) && fresh.some((f) => f.endsWith('_depth.png'))) {
			await sleep(500);
			const out = {};
			for (const f of fresh) {
				const src = path.join(PROJECTS_ROOT, slug, 'manga_plates', f);
				const kind = f.endsWith('_beauty.png') ? 'beauty' : 'depth';
				fs.copyFileSync(src, path.join(SHOT_DIR, `B0_${tag}_${kind}.png`));
				out[kind] = pngSize(src);
			}
			return out;
		}
		await sleep(400);
	}
	return null;
}
async function clickButtonByText(cdp, scope, text) {
	return cdp.eval(`(() => { const b = Array.from(document.querySelectorAll('${scope} button')).find(x => x.textContent.includes(${JSON.stringify(text)}));
		if (!b || b.disabled) return false; b.click(); return true; })()`);
}

async function runB0(cdp, full) {
	const b0 = {};
	results.b0 = b0;
	if (full) {
		// --- (c) Tab 01: nút Thước / Lưới (wireframe) / Ultra ---
		await cdp.eval(NAV('projects'));
		await sleep(400);
		await cdp.eval(`document.querySelector('[data-testid="project-card-temple-of-zyberon"]')?.click()`);
		await waitPbrStage(cdp);
		await cdp.eval(`document.querySelector('[data-testid="explode-0-btn"]')?.click()`);
		await sleep(5000);
		const base = await cdp.clipShot('.webgl-mount', 'B0_tab01_base.png');
		await clickButtonByText(cdp, '.pbr-stage-shell', 'Thước');
		const noGrid = await cdp.clipShot('.webgl-mount', 'B0_tab01_grid_off.png');
		await clickButtonByText(cdp, '.pbr-stage-shell', 'Thước');
		const gridBack = await cdp.clipShot('.webgl-mount');
		await clickButtonByText(cdp, '.pbr-stage-shell', 'Lưới');
		const wire = await cdp.clipShot('.webgl-mount', 'B0_tab01_wireframe_on.png');
		await clickButtonByText(cdp, '.pbr-stage-shell', 'Lưới');
		const wireBack = await cdp.clipShot('.webgl-mount');
		b0.grid = { diffOff: await imgDiff(cdp, base, noGrid), diffBack: await imgDiff(cdp, base, gridBack) };
		b0.wireframe = { diffOn: await imgDiff(cdp, base, wire), diffBack: await imgDiff(cdp, base, wireBack) };
		const sizeOf = () =>
			cdp.eval(`(() => { const c = document.querySelector('.webgl-mount canvas'); const s = window.__akunarchWebglStage?.();
				return { w: c?.width || 0, h: c?.height || 0, cssW: c?.clientWidth || 0, dpr: window.devicePixelRatio, stage: s ? JSON.parse(JSON.stringify(s)) : null }; })()`);
		const hd = await sizeOf();
		await cdp.eval(`document.querySelector('[data-testid="pbr-quality-toggle"]')?.click()`);
		await sleep(800);
		await waitPbrStage(cdp);
		await sleep(5000);
		const ultra = await sizeOf();
		const ultraLabel = await cdp.eval(`document.querySelector('[data-testid="pbr-quality-toggle"]')?.textContent.trim()`);
		const ultraShot = await cdp.clipShot('.webgl-mount', 'B0_tab01_ultra.png');
		await cdp.eval(`document.querySelector('[data-testid="pbr-quality-toggle"]')?.click()`);
		await sleep(800);
		await waitPbrStage(cdp);
		await sleep(4000);
		b0.ultra = { hd, ultra, ultraLabel, diffVsHd: await imgDiff(cdp, base, ultraShot) };
		log('B0 grid/wire/ultra', JSON.stringify({ grid: b0.grid, wireframe: b0.wireframe, ultra: b0.ultra }));

		// --- (a1) Tab 01: 📸 Chụp Phông Nền Manga 2K ---
		const before01 = plateFiles('temple-of-zyberon');
		await cdp.eval(`document.querySelector('[data-testid="export-manga-2k-btn"]')?.click()`);
		b0.manga_tab01 = await waitNewPlates('temple-of-zyberon', before01, 'tab01_temple');
		await cdp.shot('B0_tab01_after_manga.png');
		log('B0 manga tab01', JSON.stringify(b0.manga_tab01));

		// --- (a2) Tab 02: 📸 Chụp Đại Cảnh Manga 2K ---
		await cdp.eval(NAV('chunks'));
		await sleep(500);
		await cdp.eval(`Array.from(document.querySelectorAll('.chunk-item')).find(b => b.textContent.includes('[0, 0]'))?.click()`);
		await waitCanvasIn(cdp, '.viewport-canvas');
		await sleep(6000);
		await cdp.clipShot('.viewport-canvas', 'B0_tab02_view.png');
		const before02 = plateFiles('chunk-akunalia-0-0');
		await clickButtonByText(cdp, '', 'Chụp Đại Cảnh Manga 2K');
		b0.manga_tab02 = await waitNewPlates('chunk-akunalia-0-0', before02, 'tab02_chunk00');
		log('B0 manga tab02', JSON.stringify(b0.manga_tab02));
	}

	// --- (b) Tab 03 Camera Rig 3D: chụp so sánh (dự án VN) ---
	await cdp.eval(NAV('projects'));
	await sleep(400);
	await cdp.eval(`document.querySelector('[data-testid="project-card-vn-zyberon-sanctum-prelude"]')?.click()`);
	await sleep(800);
	await cdp.eval(NAV('vn'));
	await sleep(1500);
	await clickButtonByText(cdp, '', 'Camera Rig 3D');
	b0.rig = await waitCanvasIn(cdp, '.rig-canvas', 15000);
	await sleep(8000);
	await cdp.clipShot('.rig-canvas', 'B0_tab03_rig3d.png');
	await cdp.shot('B0_tab03_rig3d_full.png');

	if (full) {
		// --- (a3) Tab 03: 📸 Chụp Góc Máy 2K → gắn vào cảnh ---
		const vnSlug = 'vn-zyberon-sanctum-prelude';
		const before03 = plateFiles(vnSlug);
		await clickButtonByText(cdp, '.rig-controls-bar', 'Chụp Góc Máy 2K');
		b0.manga_tab03 = await waitNewPlates(vnSlug, before03, 'tab03_rig');
		await sleep(1500);
		await cdp.shot('B0_tab03_after_capture.png');
		log('B0 manga tab03', JSON.stringify(b0.manga_tab03));
	}
	b0.consoleErrors = cdp.console.filter((l) => /error|lỗi|failed/i.test(l)).slice(0, 30);
	await probe(cdp, 'B0_end');
}

async function main() {
	assert.ok(fs.existsSync(EXE), `Thiếu exe: ${EXE}`);
	try {
		execSync('taskkill /F /IM akunarch.exe /T', { stdio: 'ignore' });
		await sleep(1500);
	} catch {
		// chưa chạy
	}

	if (ONLY.includes('S0')) measure('S0_machine_idle_app_off');

	const backup = ONLY.includes('SC') ? backupData() : null;
	const metaBackup = ONLY.includes('B0') || ONLY.includes('B0R') ? backupMeta() : null;
	// B3 A/B Luật #7: cùng build, tạm đặt bản _master (JPEG) vào chỗ runtime KTX2 → khôi phục + so SHA ở finally
	const swapped = args['swap-master'] === 'true' ? swapRuntimeWithMaster() : null;

	const env = { ...process.env };
	delete env.AKUNARCH_DATA_DIR;
	delete env.AKUNARCH_PROJECTS_DIR;
	delete env.WEBVIEW2_USER_DATA_FOLDER;
	env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = `--remote-debugging-port=${CDP_PORT} --remote-allow-origins=* --ignore-gpu-blocklist --enable-webgl --enable-gpu-rasterization`;

	let proc = null;
	let cdp = null;
	try {
		proc = spawn(EXE, [], { env, stdio: 'ignore' });
		const target = await waitForTarget();
		cdp = new Cdp(target.webSocketDebuggerUrl);
		await cdp.connect();
		await cdp.send('Page.enable');
		await cdp.send('Runtime.enable');
		await cdp.send('Log.enable');
		await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: PROBE_SCRIPT });
		await cdp.send('Page.reload', { ignoreCache: false });
		await sleep(1500);

		// Xác nhận chế độ người dùng thật (Luật #2)
		let boot = null;
		for (let i = 0; i < 40 && !boot; i++) {
			boot = await cdp.eval(`(async () => {
				if (!window.__TAURI_INTERNALS__) return null;
				const b = await window.__TAURI_INTERNALS__.invoke('projects_list');
				return { n: b.length };
			})()`).catch(() => null);
			if (!boot) await sleep(400);
		}
		const paths = await cdp.eval(`window.__TAURI_INTERNALS__.invoke('studio_bootstrap').then(b => ({ db: b.db_path, root: b.projects_root }))`);
		assert.equal(paths.root, PROJECTS_ROOT);
		assert.ok(!/temp/i.test(paths.db), `DB không được nằm trong TEMP: ${paths.db}`);
		results.notes.push(`DB: ${paths.db} · projects_root: ${paths.root} · ${boot?.n} dự án`);

		// ---------- B0 (Đợt B): kiểm thật 3 việc còn treo của Đợt A ----------
		// B0R = chỉ chụp so sánh tab 03 Camera Rig 3D (không ghi dữ liệu) · B0 = đủ (Ultra/Thước/Lưới + Chụp Manga 2K 3 tab)
		if (ONLY.includes('B0') || ONLY.includes('B0R')) await runB0(cdp, ONLY.includes('B0'));

		// ---------- SK (Đợt B · B3): 4 kỳ quan cùng góc máy — ảnh + texture + VRAM App trước/sau KTX2 ----------
		if (ONLY.includes('SK')) {
			results.sk = {};
			for (const slug of WONDERS) {
				await cdp.eval(NAV('vault'));
				await sleep(600);
				await cdp.eval(NAV('projects'));
				await sleep(400);
				await cdp.eval(`document.querySelector('[data-testid="project-card-${slug}"]')?.click()`);
				const t0 = Date.now();
				await waitPbrStage(cdp, 30000);
				let parts = 0;
				for (let i = 0; i < 120 && !parts; i++) {
					parts = await cdp.eval(`Number(document.querySelector('[data-testid="real-pbr-stage"]')?.dataset.partsCount || 0)`);
					if (!parts) await sleep(250);
				}
				const loadMs = Date.now() - t0;
				await cdp.eval(`document.querySelector('[data-testid="explode-0-btn"]')?.click()`);
				await sleep(3000);
				// Ẩn lớp phủ UI để so ảnh thuần 3D; cận cảnh = 6 nấc cuộn tại tâm (cùng chuỗi thao tác trước/sau)
				await cdp.eval(`(() => { let st = document.getElementById('__sk_hide'); if (!st) { st = document.createElement('style'); st.id = '__sk_hide';
					st.textContent = '.parts-floating-drawer, .manga-preview-card { display: none !important; }'; document.head.appendChild(st); } })()`);
				await sleep(500);
				await cdp.clipShot('.webgl-mount', `SK_${slug}.png`);
				const c = await waitPbrStage(cdp, 5000);
				for (let i = 0; i < 6; i++) {
					await cdp.send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: c.x, y: c.y, deltaX: 0, deltaY: -120 });
					await sleep(60);
				}
				await sleep(2500);
				await cdp.clipShot('.webgl-mount', `SK_${slug}_close.png`);
				await cdp.eval(`document.getElementById('__sk_hide')?.remove()`);
				const stage = await cdp.eval(`JSON.parse(JSON.stringify(window.__akunarchWebglStage?.() ?? null))`);
				const m = measure(`SK_${slug}`, 6);
				results.sk[slug] = { parts, loadMs, textures: stage?.memory?.textures ?? null, app_vram_mb: m.app_vram_mb_median };
				log(`SK ${slug}`, JSON.stringify(results.sk[slug]));
			}
		}

		// ---------- TB (Đợt B · B4): VRAM App trên Topbar (PDH trong app) vs measure_vram.ps1 cùng thời điểm ----------
		if (ONLY.includes('TB')) {
			results.tb = [];
			const states = [
				['2d_standby', async () => { await cdp.eval(NAV('projects')); await sleep(1500); }],
				['3d_temple', async () => {
					await cdp.eval(`document.querySelector('[data-testid="project-card-temple-of-zyberon"]')?.click()`);
					await waitPbrStage(cdp, 30000);
					await sleep(5000);
				}]
			];
			for (const [label, enter] of states) {
				await enter();
				const child = spawn('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MEASURE_PS1, '-Label', `${PHASE}_TB_${label}`, '-Seconds', '8'], { stdio: ['ignore', 'pipe', 'ignore'] });
				let out = '';
				child.stdout.on('data', (d) => (out += d));
				const done = new Promise((r) => child.on('close', r));
				const pill = [];
				await sleep(2500);
				for (let i = 0; i < 5; i++) {
					const hw = await cdp.eval(`window.__TAURI_INTERNALS__.invoke('gpu_hardware_report')`);
					pill.push({ app: hw.vram.app_used_mb, web: hw.vram.webview_used_mb, other: hw.vram.other_system_mb, used: hw.vram.used_mb, ok: hw.vram.app_vram_available });
					await sleep(1000);
				}
				await done;
				const m = JSON.parse(out.trim().split(/\r?\n/).filter((l) => l.startsWith('{')).pop());
				const med = [...pill.map((p) => p.app)].sort((a, b) => a - b)[2];
				const diff = med - m.app_vram_mb_median;
				const pass = Math.abs(diff) <= 10 || Math.abs(diff) <= 0.05 * m.app_vram_mb_median;
				const pillText = await cdp.eval(`document.querySelector('[data-testid="topbar-vram-pill"]')?.innerText ?? null`);
				const row = { label, topbar_app_mb_median: med, measure_app_mb_median: m.app_vram_mb_median, diff_mb: +diff.toFixed(1), pass, samples: pill, pillText };
				results.tb.push(row);
				log('TB', JSON.stringify({ label, topbar: med, ps1: m.app_vram_mb_median, diff: row.diff_mb, pass, pillText }));
			}
			await cdp.shot('TB_topbar.png');
		}

		// ---------- S1: Cold boot ----------
		if (ONLY.includes('S1')) {
			await sleep(10000);
			await probe(cdp, 'S1_cold_boot');
			results.probes.S1_cold_boot.standby2d = await cdp.eval(`({
				pbrStandby: Boolean(document.querySelector('[data-testid="pbr-2d-standby-card"]')),
				canvasesInDom: document.querySelectorAll('canvas').length,
				stageRendererCreated: Boolean(window.__akunarchWebglStage?.()?.contextsCreated)
			})`);
			log('S1 standby', JSON.stringify(results.probes.S1_cold_boot.standby2d));
			await cdp.shot('S1_cold_boot.png');
			measure('S1_cold_boot');
		}

		// ---------- S2: 3D temple, xoay 3s rồi đứng yên ----------
		if (ONLY.includes('S2')) {
			await cdp.eval(NAV('projects'));
			await sleep(400);
			await cdp.eval(`document.querySelector('[data-testid="project-card-temple-of-zyberon"]')?.click()`);
			await sleep(600);
			const st = await waitPbrStage(cdp);
			results.notes.push(`S2 canvas temple: ${st.w}×${st.h} (backing store)`);
			await cdp.eval(`document.querySelector('[data-testid="explode-0-btn"]')?.click()`);
			await sleep(1500);
			await cdp.shot('S2_temple_default_view.png');
			await cdp.drag(st.x - 120, st.y, 240, 40, 3000);
			await sleep(2000);
			measure('S2_3d_idle_after_orbit');
			await probe(cdp, 'S2_3d_idle');
		}

		// ---------- SM: autoRotate (hoạt ảnh liên tục) rồi thu nhỏ cửa sổ → GPU của app phải về ~0 ----------
		if (ONLY.includes('SM')) {
			const showWindow = (cmd) =>
				execFileSync('powershell', [
					'-NoProfile',
					'-Command',
					`Add-Type -Name W -Namespace U -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int c);'; $h=(Get-Process akunarch | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1).MainWindowHandle; [U.W]::ShowWindow($h, ${cmd}) | Out-Null`
				]);
			await cdp.eval(NAV('projects'));
			await waitPbrStage(cdp);
			const clickRotate = `Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim().endsWith('Xoay'))?.click()`;
			await cdp.eval(clickRotate);
			await sleep(1500);
			measure('SM_autorotate_visible', 6);
			showWindow(6); // SW_MINIMIZE
			await sleep(2500);
			measure('SM_autorotate_minimized', 6);
			showWindow(9); // SW_RESTORE
			await sleep(1500);
			await cdp.eval(clickRotate);
			await sleep(1000);
		}

		// ---------- SC: 20 nét điêu khắc trên ô chunk ----------
		if (ONLY.includes('SC')) {
			await cdp.eval(NAV('chunks'));
			await sleep(500);
			await cdp.eval(`Array.from(document.querySelectorAll('.chunk-item')).find(b => b.textContent.includes('[0, 0]'))?.click()`);
			let st = await waitCanvasIn(cdp, '.viewport-canvas');
			await sleep(5000);
			await cdp.shot('SC_chunk_0_0_before_sculpt.png');
			measure('SC_sculpt_0');
			await cdp.eval(`Array.from(document.querySelectorAll('.stage-toolbar button')).find(b => b.textContent.includes('Điêu khắc'))?.click()`);
			await sleep(300);
			for (let i = 1; i <= SCULPT_STROKES; i++) {
				st = await waitCanvasIn(cdp, '.viewport-canvas');
				await cdp.click(st.x, st.y);
				await sleep(2200);
				if (i === 1) {
					await sleep(2000);
					measure('SC_sculpt_1');
					await probe(cdp, 'SC_sculpt_1');
				}
			}
			await sleep(3000);
			measure(`SC_sculpt_${SCULPT_STROKES}`);
			await probe(cdp, `SC_sculpt_${SCULPT_STROKES}`);
			await cdp.eval(`Array.from(document.querySelectorAll('.stage-toolbar button')).find(b => b.textContent.includes('Xoay'))?.click()`);
		}

		// ---------- S3: 10 dự án × tab 01 → 02 → 03 → 01, lặp ROUNDS vòng ----------
		if (ONLY.includes('S3')) {
			const slugs = await cdp.eval(`window.__TAURI_INTERNALS__.invoke('projects_list').then(ps => ps.map(p => p.slug))`);
			for (let round = 1; round <= ROUNDS; round++) {
				for (const slug of slugs) {
					await cdp.eval(NAV('projects'));
					await sleep(300);
					await cdp.eval(`document.querySelector('[data-testid="project-card-${slug}"]')?.click()`);
					await waitPbrStage(cdp, 6000);
					await cdp.eval(NAV('chunks'));
					await waitCanvasIn(cdp, '.viewport-canvas', 6000);
					await sleep(1200);
					await cdp.eval(NAV('vn'));
					await sleep(500);
					await cdp.eval(`Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Camera Rig 3D'))?.click()`);
					await waitCanvasIn(cdp, '.rig-canvas', 6000);
					await sleep(1200);
					await cdp.eval(NAV('projects'));
					await sleep(800);
				}
				if (round === 1 || round === ROUNDS) {
					await waitPbrStage(cdp, 8000);
					await sleep(3000);
					measure(`S3_round_${round}`);
					await probe(cdp, `S3_round_${round}`);
				}
			}
		}

		// ---------- S4 (Đợt C): ⏹ Ngắt 3D + 300 ms → đo · 🧹 → đo · ▶/⏹ TOGGLES lần ----------
		const hasStopBtn = ONLY.includes('S4')
			? await cdp.eval(`(async () => { document.querySelector('[data-testid="nav-projects"]')?.click(); await new Promise(r => setTimeout(r, 600));
				return Boolean(document.querySelector('[data-testid="activate-3d-stage-btn"], [data-testid="deactivate-3d-stage-btn"]')); })()`)
			: false;
		if (ONLY.includes('S4') && hasStopBtn) {
			await cdp.eval(`document.querySelector('[data-testid="project-card-temple-of-zyberon"]')?.click()`);
			await waitPbrStage(cdp, 30000);
			await sleep(4000);
			measure('S4_3d_on');
			await cdp.eval(`document.querySelector('[data-testid="deactivate-3d-stage-btn"]')?.click()`);
			await sleep(300);
			measure('S4_after_stop_300ms', 6);
			await probe(cdp, 'S4_after_stop');
			await cdp.eval(`Array.from(document.querySelectorAll('.topbar button')).find(b => b.textContent.includes('🧹'))?.click()`);
			await sleep(1500);
			measure('S4_after_stop_and_sweep', 6);
			let lastShowMs = 0;
			let lastPartsMs = 0;
			for (let i = 1; i <= TOGGLES; i++) {
				const t0 = Date.now();
				await cdp.eval(`document.querySelector('[data-testid="activate-3d-stage-btn"]')?.click()`);
				const st = await waitPbrStage(cdp, 15000);
				lastShowMs = Date.now() - t0;
				for (let k = 0; k < 120; k++) {
					const parts = await cdp.eval(`Number(document.querySelector('[data-testid="real-pbr-stage"]')?.dataset.partsCount || 0)`);
					if (parts) break;
					await sleep(50);
				}
				lastPartsMs = Date.now() - t0;
				if (!st?.has) results.notes.push(`S4 toggle ${i}: sân khấu 3D KHÔNG lên hình`);
				await cdp.eval(`document.querySelector('[data-testid="deactivate-3d-stage-btn"]')?.click()`);
				await sleep(250);
			}
			results.notes.push(`S4 lần bật 3D thứ ${TOGGLES}: canvas lên hình sau ${lastShowMs} ms, .glb nạp xong (có cụm) sau ${lastPartsMs} ms`);
			await probe(cdp, 'S4_final');
			measure('S4_after_toggles_stopped', 6);
		}

		// ---------- S4 (bản Đợt A/B, chưa có nút ⏹): bật/tắt sân khấu 3D TOGGLES lần + 🧹 ----------
		if (ONLY.includes('S4') && !hasStopBtn) {
			await cdp.eval(NAV('projects'));
			await cdp.eval(`document.querySelector('[data-testid="project-card-temple-of-zyberon"]')?.click()`);
			await waitPbrStage(cdp);
			let lastShowMs = 0;
			for (let i = 1; i <= TOGGLES; i++) {
				await cdp.eval(NAV('vault'));
				await sleep(400);
				const t0 = Date.now();
				await cdp.eval(NAV('projects'));
				const st = await waitPbrStage(cdp, 15000);
				lastShowMs = Date.now() - t0;
				if (!st?.has) results.notes.push(`S4 toggle ${i}: sân khấu 3D KHÔNG lên hình`);
			}
			results.notes.push(`S4 lần bật 3D thứ ${TOGGLES}: lên hình sau ${lastShowMs} ms`);
			await probe(cdp, 'S4_after_toggles');
			measure('S4_3d_on_after_toggles');
			await cdp.eval(`Array.from(document.querySelectorAll('.topbar button')).find(b => b.textContent.includes('🧹'))?.click()`);
			await sleep(1000);
			await cdp.eval(NAV('vault'));
			await sleep(3000);
			measure('S4_vault_tab_after_release');
			await probe(cdp, 'S4_final');
		}
	} finally {
		results.consoleWebglLines = cdp ? cdp.console.filter((l) => /webgl|context/i.test(l)).slice(0, 60) : [];
		if (cdp) {
			try {
				cdp.ws.close();
			} catch {
				// bỏ qua
			}
		}
		try {
			execSync('taskkill /F /IM akunarch.exe /T', { stdio: 'ignore' });
		} catch {
			// bỏ qua
		}
		if (proc) proc.kill();
		await sleep(2500);
		if (backup) restoreData(backup);
		if (swapped) restoreRuntimeGlbs(swapped);
		if (metaBackup)
			restoreData(metaBackup, META_BACKUP_DIR, metaFiles, 'project.akun.json + manga_plates + stage_vn + akunarch.db');
		results.finished = new Date().toISOString();
		const outFile = path.join(OUT_DIR, `scenarios_${PHASE}.json`);
		fs.writeFileSync(outFile, JSON.stringify(results, null, 2));
		log(`WROTE ${outFile}`);
	}
}

main().catch((e) => {
	console.error(e);
	process.exitCode = 1;
});
