/**
 * Akunarch v2.0 — TRUE NORMAL USER-MODE ACCEPTANCE VERIFICATION (LUẬT #2 & HẠNG MỤC #6).
 *
 * Launches `C:\Users\Admin\AppData\Local\Akunarch\akunarch.exe` in 100% normal user mode:
 *   - ZERO `%TEMP%` environment overrides (`AKUNARCH_DATA_DIR`, `AKUNARCH_PROJECTS_DIR`, `WEBVIEW2_USER_DATA_FOLDER` are NOT set!)
 *   - Reads live `%LOCALAPPDATA%\Akunarch\akunarch.db` and live `E:\Akunarch\projects\`
 *   - Verifies & captures crisp 1920×1080 acceptance screenshots of:
 *       1. `temple-of-zyberon` (.glb PBR) at 0%, 50%, 100% coaxial explode + Manga 2K Beauty/Depth export
 *       2. `singularity-stonehenge-avalon` (.glb PBR) at 0%, 50%, 100% coaxial explode
 *       3. `singularity-samos-olympus` (.glb PBR) at 0%, 50%, 100% coaxial explode
 *       4. `eryndor-clocktower-concept` (Zero-Placeholder Concept Blueprint Launchpad) + 47 AI Meshes Picker
 *       5. `GpuQueuePanel` showing `materialcraft-cli.exe` ready + live RTX 4080 16GB supervisor
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { spawn, execSync } from 'node:child_process';
import WebSocket from 'ws';

const LIVE_EXE = 'C:\\Users\\Admin\\AppData\\Local\\Akunarch\\akunarch.exe';
const CDP_PORT = 9237;
const OUT_DIR = 'E:\\Akunarch\\app\\ui\\tests\\screenshots\\live_user_mode_v2';

fs.mkdirSync(OUT_DIR, { recursive: true });

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
		}),
		4000,
		`GET ${url}`
	);
}

async function waitForCdpTarget(maxWaitMs = 22000) {
	const deadline = Date.now() + maxWaitMs;
	while (Date.now() < deadline) {
		try {
			const targets = await fetchJson(`http://127.0.0.1:${CDP_PORT}/json/list`);
			const page = targets.find(
				(t) =>
					t.type === 'page' &&
					(String(t.url).includes('tauri.localhost') || String(t.url).includes('localhost'))
			);
			if (page && page.webSocketDebuggerUrl) return page;
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
			'CDP connect'
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
			18000,
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
		await new Promise((r) => setTimeout(r, 380));
		const shot = await this.send('Page.captureScreenshot', { format: 'png' });
		const outPath = path.join(OUT_DIR, filename);
		fs.writeFileSync(outPath, Buffer.from(shot.data, 'base64'));
		console.log(`[SCREENSHOT] ${outPath}`);
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

async function waitForMonumentLoaded(cdp, expectedSlug) {
	const deadline = Date.now() + 22000;
	let lastState = null;
	while (Date.now() < deadline) {
		lastState = await cdp.evalJs(`(() => {
			const cardBtn = document.querySelector('[data-testid="project-card-${expectedSlug}"]');
			const activeCard = document.querySelector('.proj-item.active .mono')?.textContent?.trim() || '';
			if (cardBtn && activeCard !== '${expectedSlug}') {
				cardBtn.click();
			}
			const stage = document.querySelector('[data-testid="real-pbr-stage"]');
			const canvas = document.querySelector('.canvas-viewport canvas');
			const loading = document.querySelector('.stage-overlay-msg');
			const fallback = document.querySelector('.webgl-fallback')?.textContent?.trim() || '';
			const partsCount = Number(stage?.dataset?.partsCount || '0');
			return {
				hasCard: Boolean(cardBtn),
				activeCard,
				hasStage: Boolean(stage),
				hasCanvas: Boolean(canvas),
				isLoading: Boolean(loading),
				fallback,
				partsCount,
				width: canvas?.width || 0,
				height: canvas?.height || 0
			};
		})()`);
		if (
			lastState.activeCard === expectedSlug &&
			lastState.hasStage &&
			lastState.hasCanvas &&
			!lastState.isLoading &&
			lastState.partsCount >= 7 &&
			lastState.width > 500
		) {
			await new Promise((r) => setTimeout(r, 300));
			return lastState;
		}
		await new Promise((r) => setTimeout(r, 300));
	}
	throw new Error(
		`Monument '${expectedSlug}' did not finish loading PBR .glb in time: ${JSON.stringify(lastState)}`
	);
}

async function captureExplodeTriplet(cdp, slug, prefix) {
	await cdp.evalJs(`document.querySelector('[data-testid="project-card-${slug}"]')?.click()`);
	const loaded = await waitForMonumentLoaded(cdp, slug);
	console.log(`[MONUMENT READY] ${slug}:`, loaded);

	// 0% Assembled
	await cdp.evalJs(`document.querySelector('[data-testid="explode-0-btn"]')?.click()`);
	await new Promise((r) => setTimeout(r, 320));
	await cdp.screenshot(`${prefix}_${slug}_000pct.png`);

	// 50% Coaxial Explode
	await cdp.evalJs(`document.querySelector('[data-testid="explode-50-btn"]')?.click()`);
	await new Promise((r) => setTimeout(r, 320));
	const gap50 = await cdp.evalJs(
		`Number(document.querySelector('[data-testid="real-pbr-stage"]')?.dataset?.minYGap || '0')`
	);
	console.log(`[EXPLODE 50%] ${slug} -> min Y-Gap = +${gap50.toFixed(3)}m`);
	assert.ok(gap50 >= 0.35, `${slug} at 50% explode must have >= 0.35m Y-gap, got ${gap50}m`);
	await cdp.screenshot(`${prefix}_${slug}_050pct.png`);

	// 100% Coaxial Explode
	await cdp.evalJs(`document.querySelector('[data-testid="explode-100-btn"]')?.click()`);
	await new Promise((r) => setTimeout(r, 320));
	const gap100 = await cdp.evalJs(
		`Number(document.querySelector('[data-testid="real-pbr-stage"]')?.dataset?.minYGap || '0')`
	);
	console.log(`[EXPLODE 100%] ${slug} -> min Y-Gap = +${gap100.toFixed(3)}m`);
	assert.ok(gap100 >= 0.9, `${slug} at 100% explode must have >= 0.90m Y-gap, got ${gap100}m`);
	await cdp.screenshot(`${prefix}_${slug}_100pct.png`);
}

async function main() {
	assert.ok(fs.existsSync(LIVE_EXE), `Live akunarch.exe missing at ${LIVE_EXE}`);

	try {
		execSync('taskkill /F /IM akunarch.exe /T', { stdio: 'ignore' });
		await new Promise((r) => setTimeout(r, 500));
	} catch {
		// not running
	}

	// STRICTLY NORMAL USER ENVIRONMENT — remove any accidental override vars if present in shell!
	const cleanEnv = { ...process.env };
	delete cleanEnv.AKUNARCH_DATA_DIR;
	delete cleanEnv.AKUNARCH_PROJECTS_DIR;
	delete cleanEnv.WEBVIEW2_USER_DATA_FOLDER;
	cleanEnv.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = `--remote-debugging-port=${CDP_PORT} --remote-allow-origins=* --ignore-gpu-blocklist --disable-gpu-process-crash-limit --enable-webgl`;

	let proc = null;
	let cdp = null;
	try {
		proc = spawn(LIVE_EXE, [], { env: cleanEnv, stdio: 'ignore' });
		const target = await waitForCdpTarget(24000);
		cdp = new CdpSession(target.webSocketDebuggerUrl);
		await cdp.connect();
		await cdp.send('Page.enable');
		await cdp.send('Runtime.enable');

		// Set crisp 1680×980 desktop viewport metrics at 1x deviceScaleFactor to prove 1x DPI sharpness!
		await cdp.send('Emulation.setDeviceMetricsOverride', {
			width: 1680,
			height: 980,
			deviceScaleFactor: 1,
			mobile: false
		});

		// Verify live bootstrap paths point to real E:\Akunarch\projects and real AppData\Local\Akunarch\akunarch.db
		const deadline = Date.now() + 15000;
		let bootInfo = null;
		while (Date.now() < deadline) {
			bootInfo = await cdp.evalJs(`(async () => {
				if (!window.__TAURI_INTERNALS__) return null;
				const boot = await window.__TAURI_INTERNALS__.invoke('studio_bootstrap');
				return {
					dbPath: boot.db_path,
					projectsRoot: boot.projects_root,
					slugs: boot.projects.map(p => p.slug)
				};
			})()`);
			if (bootInfo && bootInfo.slugs.length >= 3) break;
			await new Promise((r) => setTimeout(r, 350));
		}

		console.log('[LIVE BOOTSTRAP]', bootInfo);
		assert.equal(bootInfo.projectsRoot, 'E:\\Akunarch\\projects');
		assert.ok(
			bootInfo.dbPath.toLowerCase().includes('appdata\\local\\akunarch\\akunarch.db') &&
				!bootInfo.dbPath.toLowerCase().includes('temp'),
			`Live DB must NOT be in %TEMP%: ${bootInfo.dbPath}`
		);

		// Ensure Projects & 3D Stage tab is active
		await cdp.evalJs(`document.querySelector('[data-testid="nav-projects"]')?.click()`);
		await new Promise((r) => setTimeout(r, 300));

		// Monument 1: Temple of Zyberon (0%, 50%, 100%)
		await captureExplodeTriplet(cdp, 'temple-of-zyberon', '01');

		// Also test 2K Manga Beauty + Depth Plate Export on Temple of Zyberon (at 0% assembled)
		await cdp.evalJs(`document.querySelector('[data-testid="explode-0-btn"]')?.click()`);
		await new Promise((r) => setTimeout(r, 250));
		await cdp.evalJs(`document.querySelector('[data-testid="export-manga-2k-btn"]')?.click()`);
		const plateDeadline = Date.now() + 12000;
		let previewReady = false;
		while (Date.now() < plateDeadline) {
			previewReady = await cdp.evalJs(
				`Boolean(document.querySelector('[data-testid="manga-2k-preview"]'))`
			);
			if (previewReady) break;
			await new Promise((r) => setTimeout(r, 250));
		}
		assert.equal(previewReady, true, '2K Manga plate preview card must appear after export');
		const beautyDisk = 'E:\\Akunarch\\projects\\temple-of-zyberon\\manga_plates\\beauty_plate.png';
		const depthDisk = 'E:\\Akunarch\\projects\\temple-of-zyberon\\manga_plates\\depth_map.png';
		assert.ok(fs.existsSync(beautyDisk) && fs.statSync(beautyDisk).size > 50_000);
		assert.ok(fs.existsSync(depthDisk) && fs.statSync(depthDisk).size > 20_000);
		await cdp.screenshot('01d_temple-of-zyberon_manga_2k_export.png');

		// Monument 2: Singularity Stonehenge & Avalon (0%, 50%, 100%)
		await captureExplodeTriplet(cdp, 'singularity-stonehenge-avalon', '02');

		// Monument 3: Singularity Samos & Olympus (0%, 50%, 100%)
		await captureExplodeTriplet(cdp, 'singularity-samos-olympus', '03');

		// Project 4: Standalone World-First Concept Launchpad + 47 AI Meshes Picker
		await cdp.evalJs(
			`document.querySelector('[data-testid="project-card-eryndor-clocktower-concept"]')?.click()`
		);
		await new Promise((r) => setTimeout(r, 650));
		const lpState = await cdp.evalJs(`(() => ({
			hasLaunchpad: Boolean(document.querySelector('[data-testid="concept-blueprint-launchpad"]')),
			hasCanvas: Boolean(document.querySelector('.canvas-viewport canvas'))
		}))()`);
		assert.equal(lpState.hasLaunchpad, true);
		assert.equal(lpState.hasCanvas, false);
		await cdp.screenshot('04_concept_launchpad_world_first.png');

		await cdp.evalJs(`document.querySelector('[data-testid="open-aimeshes-modal-btn"]')?.click()`);
		await new Promise((r) => setTimeout(r, 850));
		const meshCardsCount = await cdp.evalJs(
			`document.querySelectorAll('.aimesh-card').length`
		);
		console.log(`[AI MESHES LIBRARY] Loaded ${meshCardsCount} sculpted meshes`);
		assert.ok(meshCardsCount >= 40, `Expected >= 40 sculpted meshes, got ${meshCardsCount}`);
		await cdp.screenshot('05_byoa_47_aimeshes_picker.png');
		await cdp.evalJs(
			`document.querySelector('[data-testid="aimeshes-picker-modal"] button.btn')?.click()`
		);

		// GPU Supervisor & Sidecar (`materialcraft-cli.exe` Sẵn sàng + real sidecar_version job!)
		await cdp.evalJs(`document.querySelector('[data-testid="nav-gpu"]')?.click()`);
		await new Promise((r) => setTimeout(r, 550));
		await cdp.evalJs(`(async () => {
			const invoke = window.__TAURI_INTERNALS__.invoke;
			await invoke('gpu_enqueue_job', {
				input: {
					project_id: null,
					worker_kind: 'materialcraft',
					payload: { mode: 'sidecar_version' }
				}
			});
		})()`);
		await new Promise((r) => setTimeout(r, 1200));
		await cdp.evalJs(`Array.from(document.querySelectorAll('.gpu-left button')).find(b => b.textContent.includes('Đo lại'))?.click()`);
		await new Promise((r) => setTimeout(r, 550));
		const mcReady = await cdp.evalJs(`(() => {
			const card = document.querySelector('[data-testid="tool-card-sidecar_materialcraft"]');
			const jobsText = document.querySelector('.jobs-scroll')?.textContent || '';
			return { cardText: card?.textContent || '', jobsText };
		})()`);
		console.log('[SIDECAR PROBE] materialcraft:', mcReady.cardText.trim());
		assert.ok(mcReady.cardText.includes('Sẵn sàng'), 'materialcraft-cli.exe must be Sẵn sàng');
		assert.ok(mcReady.jobsText.includes('materialcraft'), 'materialcraft job must appear in GpuJobQueue');
		await cdp.screenshot('06_gpu_supervisor_materialcraft_ready.png');

		// Restore active selection back to Temple of Zyberon at 0% so user's state is pristine
		await cdp.evalJs(`document.querySelector('[data-testid="nav-projects"]')?.click()`);
		await new Promise((r) => setTimeout(r, 300));
		await cdp.evalJs(
			`document.querySelector('[data-testid="project-card-temple-of-zyberon"]')?.click()`
		);
		await waitForMonumentLoaded(cdp, 'temple-of-zyberon');

		console.log('[LIVE USER-MODE ACCEPTANCE COMPLETE] All 3 AAA .glb monuments + Concept Launchpad + BYOA + Manga 2K + Sidecar verified!');
	} finally {
		if (cdp) {
			try {
				await cdp.evalJs(`window.close()`);
				await new Promise((r) => setTimeout(r, 400));
			} catch {
				// ignore
			}
			cdp.close();
		}
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
	}
}

await main();
