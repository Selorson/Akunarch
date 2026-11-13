/**
 * Kế hoạch VRAM v2 · C2 — xếp render_preview_card cho các kỳ quan QUA GpuJobQueue của app thật
 * (projects_ensure_preview_card), chờ xong, in kết quả. Chạy: node tests/run-preview-cards.mjs <exe> <slug...>
 */
import { execSync, spawn } from 'node:child_process';
import http from 'node:http';
import WebSocket from 'ws';
const [EXE, ...SLUGS] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
try { execSync('taskkill /F /IM akunarch.exe /T', { stdio: 'ignore' }); } catch {}
await sleep(1000);
const env = { ...process.env, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: '--remote-debugging-port=9241 --remote-allow-origins=*' };
delete env.AKUNARCH_DATA_DIR; delete env.AKUNARCH_PROJECTS_DIR; delete env.WEBVIEW2_USER_DATA_FOLDER;
const proc = spawn(EXE, [], { env, stdio: 'ignore' });
const get = (u) => new Promise((res, rej) => http.get(u, (r) => { let d = ''; r.on('data', (c) => (d += c)); r.on('end', () => res(JSON.parse(d))); }).on('error', rej));
let t = null;
for (let i = 0; i < 80 && !t; i++) { try { t = (await get('http://127.0.0.1:9241/json/list')).find((x) => x.type === 'page'); } catch {} if (!t) await sleep(400); }
const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => ws.once('open', r));
let id = 0; const pend = new Map();
ws.on('message', (d) => { const m = JSON.parse(String(d)); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
const ev = async (expression) => { const i = ++id; const r = await new Promise((res) => { pend.set(i, res); ws.send(JSON.stringify({ id: i, method: 'Runtime.evaluate', params: { expression, awaitPromise: true, returnByValue: true } })); }); return r.result?.result?.value; };
for (let i = 0; i < 40; i++) { if (await ev(`Boolean(window.__TAURI_INTERNALS__)`)) break; await sleep(400); }
const ids = [];
for (const slug of SLUGS) {
	const job = await ev(`window.__TAURI_INTERNALS__.invoke('projects_ensure_preview_card', { slug: ${JSON.stringify(slug)} })`);
	console.log('ENQUEUE', slug, job ? `#${job.id}` : 'không cần (ảnh còn mới)');
	if (job) ids.push(job.id);
}
const deadline = Date.now() + 20 * 60 * 1000;
while (ids.length && Date.now() < deadline) {
	const jobs = await ev(`window.__TAURI_INTERNALS__.invoke('gpu_list_jobs', { limit: 60 })`);
	const mine = jobs.filter((j) => ids.includes(j.id));
	if (mine.every((j) => j.status === 'completed' || j.status === 'failed')) {
		for (const j of mine) console.log('JOB', j.id, j.status, j.output_path, `peak ${j.vram_peak_mb} MB · worker ${j.payload?.worker_vram_peak_mb ?? '-'} MB`, j.error_log?.slice(0, 300) ?? '');
		break;
	}
	await sleep(3000);
}
const ps = await ev(`window.__TAURI_INTERNALS__.invoke('projects_list').then(ps => ps.filter(p => ${JSON.stringify(SLUGS)}.includes(p.slug)).map(p => [p.slug, p.manifest.clockwork.preview_render_path]))`);
console.log('MANIFEST', JSON.stringify(ps));
ws.close(); try { execSync('taskkill /F /IM akunarch.exe /T', { stdio: 'ignore' }); } catch {}
proc.kill(); process.exit(0);
