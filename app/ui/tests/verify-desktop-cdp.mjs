import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, execSync } from 'node:child_process';
import WebSocket from 'ws';

const APP_EXE =
	process.env.AKUNARCH_EXE_PATH ||
	'C:\\Users\\Admin\\AppData\\Local\\Akunarch\\akunarch.exe';
const CDP_PORT = 9236;
const MOCK_SELORSON_PORT = 18091;
const SCREENSHOT_DIR = 'E:\\Akunarch\\app\\ui\\tests\\screenshots\\isolated_regression';
const ISOLATED_ROOT = path.join(os.tmpdir(), `akunarch-cdp-e2e-${process.pid}`);
const ISOLATED_DATA_DIR = path.join(ISOLATED_ROOT, 'data');
const ISOLATED_PROJECTS_DIR = path.join(ISOLATED_ROOT, 'projects');
const ISOLATED_WEBVIEW_DIR = path.join(ISOLATED_ROOT, 'webview2');

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
fs.rmSync(ISOLATED_ROOT, { recursive: true, force: true });
fs.mkdirSync(ISOLATED_DATA_DIR, { recursive: true });
fs.mkdirSync(ISOLATED_PROJECTS_DIR, { recursive: true });
fs.mkdirSync(ISOLATED_WEBVIEW_DIR, { recursive: true });

function withTimeout(promise, ms, label) {
	return Promise.race([
		promise,
		new Promise((_, reject) =>
			setTimeout(() => reject(new Error(`Timeout (${ms}ms): ${label}`)), ms)
		)
	]);
}

async function fetchJson(url) {
	return withTimeout(
		new Promise((resolve, reject) => {
			http
				.get(url, (res) => {
					let raw = '';
					res.on('data', (chunk) => (raw += chunk));
					res.on('end', () => {
						try {
							resolve(JSON.parse(raw));
						} catch (e) {
							reject(e);
						}
					});
				})
				.on('error', reject);
		}),
		4000,
		`GET ${url}`
	);
}

async function waitForCdpTarget(maxWaitMs = 20000) {
	const deadline = Date.now() + maxWaitMs;
	while (Date.now() < deadline) {
		try {
			const targets = await fetchJson(`http://127.0.0.1:${CDP_PORT}/json/list`);
			const page = targets.find(
				(t) =>
					t.type === 'page' &&
					(String(t.url).includes('tauri.localhost') || String(t.url).includes('localhost'))
			);
			if (page && page.webSocketDebuggerUrl) {
				return page;
			}
		} catch {
			// wait for WebView2 debug port
		}
		await new Promise((r) => setTimeout(r, 400));
	}
	throw new Error(`CDP target did not appear on port ${CDP_PORT}`);
}

class CdpSession {
	constructor(wsUrl) {
		this.ws = new WebSocket(wsUrl);
		this.seq = 0;
		this.pending = new Map();
	}

	async connect() {
		await withTimeout(
			new Promise((resolve, reject) => {
				this.ws.once('open', resolve);
				this.ws.once('error', reject);
			}),
			8000,
			'CDP WebSocket connect'
		);
		this.ws.on('message', (data) => {
			const msg = JSON.parse(String(data));
			if (msg.id && this.pending.has(msg.id)) {
				const { resolve, reject } = this.pending.get(msg.id);
				this.pending.delete(msg.id);
				if (msg.error) reject(new Error(JSON.stringify(msg.error)));
				else resolve(msg.result);
			}
		});
	}

	send(method, params = {}) {
		const id = ++this.seq;
		return withTimeout(
			new Promise((resolve, reject) => {
				this.pending.set(id, { resolve, reject });
				this.ws.send(JSON.stringify({ id, method, params }));
			}),
			14000,
			`CDP ${method}`
		);
	}

	async evalJs(expression) {
		const res = await this.send('Runtime.evaluate', {
			expression,
			awaitPromise: true,
			returnByValue: true
		});
		if (res.exceptionDetails) {
			throw new Error(`JS Exception: ${JSON.stringify(res.exceptionDetails)}`);
		}
		return res.result?.value;
	}

	async screenshot(filename) {
		await this.send('Page.bringToFront');
		await new Promise((r) => setTimeout(r, 250));
		const shot = await this.send('Page.captureScreenshot', { format: 'png' });
		const outPath = path.join(SCREENSHOT_DIR, filename);
		fs.writeFileSync(outPath, Buffer.from(shot.data, 'base64'));
		return outPath;
	}

	close() {
		try {
			this.ws.close();
		} catch {
			// ignore
		}
	}
}

async function startMockSelorsonGateway() {
	const receivedPayloads = [];
	const server = http.createServer((req, res) => {
		let body = '';
		req.on('data', (c) => (body += c));
		req.on('end', () => {
			res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
			if (req.url?.startsWith('/api/v1/admin/world/overview')) {
				res.end(
					JSON.stringify({
						success: true,
						data: {
							storage_mode: 'local',
							summary: {
								total_places: 13 + receivedPayloads.length,
								published_places: 13,
								pending_places: receivedPayloads.length,
								total_chunks: 0,
								published_chunks: 0,
								pending_chunks: 0,
								with_intro_video: 2,
								with_desktop_pack: 13,
								with_vn_episode: 0,
								total_videos: 4
							},
							items: [
								...receivedPayloads.map((p, i) => ({
									id: 100 + i,
									slug: p.locations?.[0]?.slug || 'draft-item',
									name: p.locations?.[0]?.name || 'Draft Item',
									category: 'location',
									is_active: false,
									en_translation: p.locations?.[0]?.en || null
								})),
								{
									id: 1,
									slug: 'temple-of-zyberon',
									name: 'Đại Đền Ngũ Giác Zyberon',
									category: 'location',
									is_active: true,
									en_translation: { name: 'Pentagonal Temple of Zyberon' }
								}
							]
						}
					})
				);
			} else if (req.url?.startsWith('/api/v1/admin/sync/world-studio') && req.method === 'POST') {
				const parsed = JSON.parse(body || '{}');
				receivedPayloads.push(parsed);
				res.end(
					JSON.stringify({
						success: true,
						message: 'Đã nhận tài nguyên từ Akunarch vào hàng chờ kiểm duyệt (Nháp)!',
						data: {
							source_app: parsed.source_app,
							created_locations: parsed.locations?.length || 0,
							updated_locations: 0,
							created_chunks: parsed.chunks?.length || 0,
							updated_chunks: 0,
							synced_videos: parsed.videos?.length || 0,
							synced_translations: 1
						}
					})
				);
			} else {
				res.end(JSON.stringify({ success: false, message: 'Not found' }));
			}
		});
	});
	await new Promise((resolve) => server.listen(MOCK_SELORSON_PORT, '127.0.0.1', resolve));
	return { server, receivedPayloads };
}

async function runE2e() {
	assert.ok(fs.existsSync(APP_EXE), `akunarch.exe not found at ${APP_EXE}`);
	const { server, receivedPayloads } = await startMockSelorsonGateway();

	let proc = null;
	let cdp = null;
	try {
		proc = spawn(APP_EXE, [], {
			env: {
				...process.env,
				AKUNARCH_DATA_DIR: ISOLATED_DATA_DIR,
				AKUNARCH_PROJECTS_DIR: ISOLATED_PROJECTS_DIR,
				WEBVIEW2_USER_DATA_FOLDER: ISOLATED_WEBVIEW_DIR,
				WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${CDP_PORT} --remote-allow-origins=* --ignore-gpu-blocklist --enable-webgl --use-angle=d3d11`
			},
			stdio: 'ignore'
		});

		const target = await waitForCdpTarget(22000);
		console.log('[CDP] Connected to:', target.url);
		cdp = new CdpSession(target.webSocketDebuggerUrl);
		await cdp.connect();
		await cdp.send('Page.enable');
		await cdp.send('Runtime.enable');

		// 1. Wait for Vault Snapshot KPIs from live co_writer.db (RO) + Tools-3D\concepts
		const deadline = Date.now() + 15000;
		let vaultKpis = null;
		while (Date.now() < deadline) {
			vaultKpis = await cdp.evalJs(`(() => {
				const ent = document.querySelector('[data-testid="kpi-entities"]')?.textContent?.trim();
				const ac = document.querySelector('[data-testid="kpi-arcs-chapters"]')?.textContent?.trim();
				const sk = document.querySelector('[data-testid="kpi-sketches"]')?.textContent?.trim();
				const mg = document.querySelector('[data-testid="kpi-manga"]')?.textContent?.trim();
				const cp = document.querySelector('[data-testid="kpi-concepts"]')?.textContent?.trim();
				const ro = document.querySelector('[data-testid="cowriter-ro-badge"]')?.textContent?.trim();
				if (!ent) return null;
				return { origin: location.origin, ent, ac, sk, mg, cp, ro };
			})()`);
			if (vaultKpis) break;
			await new Promise((r) => setTimeout(r, 350));
		}

		console.log('[VERIFY] Vault KPIs:', vaultKpis);
		assert.ok(vaultKpis, 'Vault KPIs did not render');
		assert.equal(vaultKpis.origin, 'http://tauri.localhost');
		assert.equal(vaultKpis.ent, '163');
		assert.ok(vaultKpis.ac.includes('7') && vaultKpis.ac.includes('12'));
		assert.equal(vaultKpis.sk, '46');
		assert.ok(vaultKpis.mg.includes('13') && vaultKpis.mg.includes('273'));
		assert.ok(vaultKpis.cp.includes('15') && vaultKpis.cp.includes('70'));
		assert.ok(vaultKpis.ro.includes('SQLITE_OPEN_READ_ONLY'));

		await cdp.screenshot('01_vault_entities.png');

		// 2. Click Concepts KPI pill and verify images load via akunmedia.localhost + arbitrary system file & akunarch.db are 403 blocked + Range 206 works
		const sampleVideoFile = path.join(ISOLATED_PROJECTS_DIR, 'Đền_Ngũ_Giác+v1&2#preview.mp4');
		fs.writeFileSync(sampleVideoFile, Buffer.from('0123456789ABCDEF', 'utf8'));
		const isolatedDbFile = path.join(ISOLATED_DATA_DIR, 'akunarch.db');

		await cdp.evalJs(`document.querySelector('[data-testid="kpi-concepts"]').closest('button').click()`);
		await new Promise((r) => setTimeout(r, 900));
		const imgCheck = await cdp.evalJs(`(async () => {
			const imgs = Array.from(document.querySelectorAll('.concept-img-btn img'));
			const forbiddenRes = await fetch('http://akunmedia.localhost/file?path=' + encodeURIComponent('C:\\\\Windows\\\\win.ini'));
			const dbBlockRes = await fetch('http://akunmedia.localhost/file?path=' + encodeURIComponent(${JSON.stringify(isolatedDbFile)}));
			const rangeRes = await fetch(
				'http://akunmedia.localhost/file?path=' + encodeURIComponent(${JSON.stringify(sampleVideoFile)}),
				{ headers: { Range: 'bytes=0-3' } }
			);
			const rangeBody = await rangeRes.text();
			return {
				totalCards: imgs.length,
				loadedCount: imgs.filter(i => i.complete && i.naturalWidth > 64).length,
				firstSrc: imgs[0]?.src || '',
				forbiddenStatus: forbiddenRes.status,
				dbBlockStatus: dbBlockRes.status,
				rangeStatus: rangeRes.status,
				rangeBody
			};
		})()`);
		console.log('[VERIFY] Concepts gallery & media security:', imgCheck);
		assert.equal(imgCheck.totalCards, 15, 'Default Canon-15 filter must show 15 cards');
		assert.ok(imgCheck.loadedCount >= 1, 'Concept images must load via akunmedia.localhost');
		assert.equal(imgCheck.forbiddenStatus, 403, 'akunmedia protocol must block C:\\Windows\\win.ini with 403');
		assert.equal(imgCheck.dbBlockStatus, 403, 'akunmedia protocol must block akunarch.db with 403');
		assert.equal(imgCheck.rangeStatus, 206, 'akunmedia protocol must support HTTP 206 Range streaming');
		assert.equal(imgCheck.rangeBody, '0123');
		fs.rmSync(sampleVideoFile, { force: true });
		await cdp.screenshot('02_vault_concepts_15.png');

		// 3. Scaffold project directly from first Concept card -> must show Zero-Placeholder Concept Blueprint Launchpad (NO fake 3D!)
		await cdp.evalJs(`document.querySelector('.concept-card .btn').click()`);
		let launchpadCheck = null;
		const lpDeadline = Date.now() + 8000;
		while (Date.now() < lpDeadline) {
			launchpadCheck = await cdp.evalJs(`(() => {
				const lp = document.querySelector('[data-testid="concept-blueprint-launchpad"]');
				const fakeCanvas = document.querySelector('.canvas-viewport canvas');
				return {
					activeNav: document.querySelector('.nav-btn.active strong')?.textContent?.trim() || '',
					hasLaunchpad: Boolean(lp),
					hasFakeCanvas: Boolean(fakeCanvas)
				};
			})()`);
			if (launchpadCheck.hasLaunchpad) break;
			await new Promise((r) => setTimeout(r, 250));
		}
		console.log('[VERIFY] Zero-Placeholder Concept Launchpad:', launchpadCheck);
		assert.equal(launchpadCheck.hasLaunchpad, true, 'Concept-only project must show Concept Launchpad');
		assert.equal(launchpadCheck.hasFakeCanvas, false, 'Concept-only project must NEVER render fake 3D primitives');
		await cdp.screenshot('03a_concept_launchpad_zero_placeholder.png');

		// Import real AAA .glb (`temple-of-zyberon.glb`) via BYOA `projects_import_external_file` and verify real Draco WebGL2 stage!
		const realGlbSrc = 'E:\\Akunarch\\projects\\temple-of-zyberon\\clockwork\\temple-of-zyberon.glb';
		await cdp.evalJs(`(async () => {
			const invoke = window.__TAURI_INTERNALS__.invoke;
			const projs = await invoke('projects_list');
			await invoke('projects_import_external_file', {
				slug: projs[0].slug,
				assetKind: 'glb',
				sourcePath: ${JSON.stringify(realGlbSrc)},
				setPrimary: true
			});
			const vibeBtn = Array.from(document.querySelectorAll('.projects-sidebar button')).find(b => b.textContent.includes('Vibecode'));
			vibeBtn?.click();
		})()`);

		let stageCheck = null;
		const stageDeadline = Date.now() + 12000;
		while (Date.now() < stageDeadline) {
			stageCheck = await cdp.evalJs(`(() => {
				const stage = document.querySelector('[data-testid="real-pbr-stage"]');
				const canvas = document.querySelector('.canvas-viewport canvas');
				if (canvas) window.__stageCanvasRef = canvas;
				const partsCount = Number(stage?.dataset?.partsCount || '0');
				return {
					hasStage: Boolean(stage),
					hasCanvas: Boolean(canvas),
					partsCount,
					width: canvas?.width || 0,
					height: canvas?.height || 0
				};
			})()`);
			if (stageCheck.hasCanvas && stageCheck.partsCount >= 7 && stageCheck.width > 300) break;
			await new Promise((r) => setTimeout(r, 300));
		}
		console.log('[VERIFY] Real PBR Draco Stage:', stageCheck);
		assert.ok(stageCheck.hasCanvas && stageCheck.partsCount >= 7 && stageCheck.width > 300);
		await cdp.screenshot('03_projects_3d_stage.png');

		// Set explode slider 0% -> 100% (verify >= 0.35m Y-band air gap!) -> 50% and verify WebGL canvas is NOT recreated!
		const canvasStability = await cdp.evalJs(`(async () => {
			document.querySelector('[data-testid="explode-100-btn"]')?.click();
			await new Promise(r => setTimeout(r, 220));
			const minGapAt100 = Number(document.querySelector('[data-testid="real-pbr-stage"]')?.dataset?.minYGap || '0');
			document.querySelector('[data-testid="explode-50-btn"]')?.click();
			await new Promise(r => setTimeout(r, 220));
			const currentCanvas = document.querySelector('.canvas-viewport canvas');
			const projs = await window.__TAURI_INTERNALS__.invoke('projects_list');
			return {
				sameCanvasInstance: currentCanvas === window.__stageCanvasRef,
				minGapAt100,
				initialSlug: projs[0].slug,
				initialFolder: projs[0].folder_path
			};
		})()`);
		console.log('[VERIFY] WebGL stability & Y-Band Gap:', canvasStability);
		assert.equal(
			canvasStability.sameCanvasInstance,
			true,
			'Three.js WebGL2 canvas must NOT be recreated when explodePct changes'
		);
		assert.ok(
			canvasStability.minGapAt100 >= 0.35,
			`Expected coaxial 100% explode Y-band gap >= 0.35m, got ${canvasStability.minGapAt100}m`
		);

		// Test Vibecode disk-first edit: edit manifest.slug with Vietnamese diacritics on disk and click 🔄 Vibecode in UI
		const manifestDiskPath = path.join(canvasStability.initialFolder, 'project.akun.json');
		const editedManifest = JSON.parse(fs.readFileSync(manifestDiskPath, 'utf8'));
		editedManifest.slug = 'Đền Mặt Trời Vibecode!';
		fs.writeFileSync(manifestDiskPath, JSON.stringify(editedManifest, null, 2), 'utf8');

		const vibecodeCheck = await cdp.evalJs(`(async () => {
			const vibeBtn = Array.from(document.querySelectorAll('.projects-sidebar button')).find(b => b.textContent.includes('Vibecode'));
			vibeBtn?.click();
			await new Promise(r => setTimeout(r, 450));
			const projs = await window.__TAURI_INTERNALS__.invoke('projects_list');
			const bundlePath = await window.__TAURI_INTERNALS__.invoke('projects_export_bundle', {
				slug: projs[0].slug
			});
			return {
				count: projs.length,
				renamedSlug: projs[0].slug,
				renamedFolder: projs[0].folder_path,
				bundlePath
			};
		})()`);
		console.log('[VERIFY] Vibecode Disk Rescan & .akunbundle.zip:', vibecodeCheck);
		assert.equal(vibecodeCheck.count, 1, 'Vibecode slug rename must update row in-place without duplicates');
		assert.equal(vibecodeCheck.renamedSlug, 'den-mat-troi-vibecode');
		assert.ok(fs.existsSync(vibecodeCheck.renamedFolder), 'Renamed project folder must exist');
		assert.ok(!fs.existsSync(canvasStability.initialFolder), 'Old slug folder must be atomically moved');
		assert.ok(fs.existsSync(vibecodeCheck.bundlePath), '.akunbundle.zip must exist on disk');
		await cdp.screenshot('03b_projects_3d_stage_50pct.png');

		// 4. Switch to GpuJobQueue tab, enqueue a real RTX 4080 probe job, verify completion
		await cdp.evalJs(`document.querySelector('[data-testid="nav-gpu"]').click()`);
		await new Promise((r) => setTimeout(r, 600));
		await cdp.evalJs(`document.querySelector('[data-testid="enqueue-gpu-job-btn"]').click()`);
		await new Promise((r) => setTimeout(r, 1200));
		const gpuCheck = await cdp.evalJs(`(() => {
			const badges = Array.from(document.querySelectorAll('.job-row .badge')).map(b => b.textContent.trim());
			const vramHeader = document.querySelector('.gpu-left h2')?.textContent?.trim() || '';
			return { vramHeader, badges };
		})()`);
		console.log('[VERIFY] GPU Supervisor:', gpuCheck);
		assert.ok(gpuCheck.vramHeader.includes('RTX 4080') || gpuCheck.vramHeader.includes('NVIDIA'));
		assert.ok(gpuCheck.badges.includes('completed'));
		await cdp.screenshot('04_gpu_queue_rtx4080.png');

		// 5. Switch to Sync Hub, test UTF-8 token safety + Bearer prefix stripping + UI Push using UI baseUrl directly
		await cdp.evalJs(`document.querySelector('[data-testid="nav-sync"]').click()`);
		await new Promise((r) => setTimeout(r, 600));
		const tokenSafety = await cdp.evalJs(`(async () => {
			const invoke = window.__TAURI_INTERNALS__.invoke;
			let rejectedUnicode = false;
			try {
				await invoke('sync_save_config', {
					baseUrl: 'http://127.0.0.1:8001',
					token: 'Đền_Thờ_Chuỗi_Tiếng_Việt_Dài_Hơn_16_Ký_Tự'
				});
			} catch (err) {
				rejectedUnicode = String(err).includes('Bearer Token');
			}
			// Save token with "Bearer " prefix while keeping old port 8001 in DB so UI Push must override baseUrl!
			const cfg = await invoke('sync_save_config', {
				baseUrl: 'http://127.0.0.1:8001',
				token: 'Bearer e2e-local-admin-token-long-preview'
			});
			return { rejectedUnicode, cfg };
		})()`);
		console.log('[VERIFY] Token UTF-8 safety & Bearer strip:', tokenSafety);
		assert.equal(tokenSafety.rejectedUnicode, true, 'Non-ASCII token must be rejected without panic');
		assert.ok(!tokenSafety.cfg.token_preview.startsWith('Bearer'), 'Bearer prefix must be stripped');

		// Type mock gateway URL into UI input ONLY (without clicking Save/Connect first) and click Đẩy Gói Nháp!
		await cdp.evalJs(`(() => {
			const urlInput = document.querySelector('.sync-left input.input');
			urlInput.value = 'http://127.0.0.1:${MOCK_SELORSON_PORT}';
			urlInput.dispatchEvent(new Event('input', { bubbles: true }));
			const pushBtn = Array.from(document.querySelectorAll('.sync-right button')).find(b => b.textContent.includes('Đẩy Gói Nháp'));
			pushBtn?.click();
		})()`);
		await new Promise((r) => setTimeout(r, 1300));

		assert.equal(receivedPayloads.length, 1, 'Clicking Push in UI must send payload to edited baseUrl');
		assert.equal(receivedPayloads[0].source_app, 'Akunarch');
		assert.equal(receivedPayloads[0].force_draft, true);
		assert.equal(receivedPayloads[0].locations[0].slug, 'den-mat-troi-vibecode');

		const syncDomCheck = await cdp.evalJs(`(() => {
			const ovStats = Array.from(document.querySelectorAll('.overview-kpis .ov-num')).map(n => n.textContent.trim());
			const qaPasses = document.querySelectorAll('.qa-findings .qa-row').length;
			const logRows = document.querySelectorAll('.sync-right .ov-item-row').length;
			return { ovStats, qaPasses, logRows };
		})()`);
		console.log('[VERIFY] Sync Hub DOM:', syncDomCheck);
		assert.ok(syncDomCheck.ovStats.length === 4, 'Overview KPIs must display 4 cards');
		assert.ok(syncDomCheck.qaPasses >= 2, 'QA Audit findings must render');
		assert.ok(syncDomCheck.logRows >= 1, 'sync_logs rows must render in UI');

		await cdp.screenshot('05_sync_hub_selorson.png');
		console.log('[SUCCESS] All 5 desktop E2E stages & screenshots verified cleanly!');
	} finally {
		if (cdp) cdp.close();
		server.close();
		if (proc) {
			try {
				proc.kill();
			} catch {
				// ignore
			}
		}
		try {
			execSync('taskkill /F /IM akunarch.exe /T', { stdio: 'ignore' });
		} catch {
			// ignore
		}
		await new Promise((r) => setTimeout(r, 450));
		try {
			fs.rmSync(ISOLATED_ROOT, {
				recursive: true,
				force: true,
				maxRetries: 10,
				retryDelay: 250
			});
		} catch {
			// ignore
		}
	}
}

let exitCode = 0;
try {
	await runE2e();
} catch (err) {
	console.error('[FATAL E2E ERROR]', err);
	exitCode = 1;
}
process.exit(exitCode);
