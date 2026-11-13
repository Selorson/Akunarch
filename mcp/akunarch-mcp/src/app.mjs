// Kết nối akunarch.exe đã cài (dữ liệu thật) qua cổng CDP, gọi lệnh IPC bằng window.__TAURI__.core.invoke.
import { spawn, execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import http from 'node:http';
import { Cdp } from './cdp.mjs';

export const EXE = 'C:\\Users\\Admin\\AppData\\Local\\Akunarch\\akunarch.exe';
export const CDP_PORT = 9241;
// Giữ đúng cờ GPU của tauri.conf.json (app.windows[0].additionalBrowserArgs)
const GPU_FLAGS = '--ignore-gpu-blocklist --enable-webgl --enable-gpu-rasterization';
// Luật #2: không bao giờ trỏ dữ liệu sang chỗ khác
const DATA_REDIRECT_VARS = ['AKUNARCH_DATA_DIR', 'AKUNARCH_PROJECTS_DIR', 'WEBVIEW2_USER_DATA_FOLDER'];

export class AppNotDebuggableError extends Error {
	constructor() {
		super(
			'Akunarch đang mở nhưng không có cổng điều khiển. Anh đóng app giúp em để em mở lại kèm cổng điều khiển (dữ liệu không đổi).'
		);
		this.name = 'AppNotDebuggableError';
	}
}

export function buildLaunchEnv(baseEnv, port = CDP_PORT) {
	const env = { ...baseEnv };
	for (const k of DATA_REDIRECT_VARS) delete env[k];
	env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = `--remote-debugging-port=${port} ${GPU_FLAGS}`;
	return env;
}

export function buildInvokeExpression(cmd, args) {
	return `window.__TAURI__.core.invoke(${JSON.stringify(cmd)}, ${JSON.stringify(args ?? {})})`;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function fetchJson(url, timeoutMs = 2000) {
	return new Promise((resolve, reject) => {
		const req = http.get(url, (res) => {
			let raw = '';
			res.on('data', (c) => (raw += c));
			res.on('end', () => {
				try {
					resolve(JSON.parse(raw));
				} catch (e) {
					reject(e);
				}
			});
		});
		req.setTimeout(timeoutMs, () => req.destroy(new Error('timeout')));
		req.on('error', reject);
	});
}

export async function findTarget(port = CDP_PORT) {
	try {
		const list = await fetchJson(`http://127.0.0.1:${port}/json/list`);
		return list.find((x) => x.type === 'page' && String(x.url).includes('localhost') && x.webSocketDebuggerUrl) ?? null;
	} catch {
		return null;
	}
}

export function listAppPids() {
	return new Promise((resolve) => {
		execFile('tasklist', ['/FI', 'IMAGENAME eq akunarch.exe', '/NH', '/FO', 'CSV'], { windowsHide: true }, (err, out) => {
			if (err) return resolve([]);
			const pids = [...String(out).matchAll(/^"akunarch\.exe","(\d+)"/gim)].map((m) => Number(m[1]));
			resolve(pids);
		});
	});
}

/** Bung / thu nhỏ cửa sổ Akunarch từ phía Windows (ACL Tauri không cho frontend tự unminimize). */
export function setAppWindowState(state) {
	const cmd = state === 'minimize' ? 6 : 9; // SW_MINIMIZE / SW_RESTORE
	const ps = `Add-Type -Name W -Namespace U -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindowAsync(System.IntPtr h, int n);';
		Get-Process akunarch -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | ForEach-Object { [U.W]::ShowWindowAsync($_.MainWindowHandle, ${cmd}) | Out-Null }`;
	return new Promise((resolve) => {
		execFile('C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe', ['-NoProfile', '-Command', ps], { windowsHide: true }, () => resolve());
	});
}

export const osWindowControl = { restore: () => setAppWindowState('restore'), minimize: () => setAppWindowState('minimize') };

async function defaultProbe(port = CDP_PORT) {
	const [pids, target] = await Promise.all([listAppPids(), findTarget(port)]);
	return { running: pids.length > 0, cdp: Boolean(target), pids, target };
}

function sha256File(path) {
	return new Promise((resolve) => {
		const h = createHash('sha256');
		createReadStream(path)
			.on('data', (c) => h.update(c))
			.on('end', () => resolve(h.digest('hex')))
			.on('error', () => resolve(''));
	});
}

export async function appStatus({ exe = EXE, port = CDP_PORT } = {}) {
	const p = await defaultProbe(port);
	return { running: p.running, cdp: p.cdp, pids: p.pids, exePath: exe, exeSha256: await sha256File(exe) };
}

class AppSession {
	constructor(cdp) {
		this.cdp = cdp;
	}
	get open() {
		return this.cdp.open;
	}
	evaluate(expression, timeoutMs) {
		return this.cdp.eval(expression, timeoutMs);
	}
	invoke(cmd, args = {}, timeoutMs = 120000) {
		return this.cdp.eval(buildInvokeExpression(cmd, args), timeoutMs);
	}
	async screenshot({ clip } = {}) {
		const params = { format: 'png' };
		if (clip) params.clip = { ...clip, scale: 1 };
		const s = await this.cdp.send('Page.captureScreenshot', params, 60000);
		return Buffer.from(s.data, 'base64');
	}
	close() {
		this.cdp.close();
	}
}

/** Đóng app nhẹ nhàng (WM_CLOSE qua taskkill không /F), sau 5 s còn sống thì ép tắt. */
export async function closeAppGracefully(pids) {
	const tk = (args) => new Promise((r) => execFile('C:\\Windows\\System32\\taskkill.exe', args, { windowsHide: true }, () => r()));
	for (const pid of pids) await tk(['/PID', String(pid)]);
	for (let i = 0; i < 10 && (await listAppPids()).length > 0; i++) await sleep(500);
	for (const pid of await listAppPids()) await tk(['/PID', String(pid), '/T', '/F']);
	await sleep(800);
}

function launchApp(exe, port) {
	const child = spawn(exe, [], { env: buildLaunchEnv(process.env, port), detached: true, stdio: 'ignore', windowsHide: false });
	child.unref();
}

/**
 * Mở (nếu cần) và kết nối app. App anh mở sẵn mà không có cổng CDP → (anh cho phép 2026-11-13) đóng rồi mở lại
 * kèm cổng; `allowClose: false` thì giữ hành vi cũ: ném AppNotDebuggableError, không đụng app.
 */
export async function connectApp({
	launchIfClosed = true,
	allowClose = true,
	probe,
	closeApp = closeAppGracefully,
	launch = launchApp,
	exe = EXE,
	port = CDP_PORT,
	timeoutMs = 45000
} = {}) {
	const doProbe = probe ?? (() => defaultProbe(port));
	let p = await doProbe();
	if (p.running && !p.cdp) {
		if (!allowClose) throw new AppNotDebuggableError();
		await closeApp(p.pids ?? []);
		p = await doProbe();
		if (p.running) throw new AppNotDebuggableError();
	}
	if (!p.running) {
		if (!launchIfClosed) throw new Error('Akunarch chưa mở.');
		launch(exe, port);
	}
	const deadline = Date.now() + timeoutMs;
	let target = p.target ?? null;
	while (!target && Date.now() < deadline) {
		await sleep(400);
		target = await findTarget(port);
	}
	if (!target) throw new Error(`Không thấy cổng điều khiển CDP ${port} sau ${timeoutMs / 1000} s.`);
	const cdp = await new Cdp(target.webSocketDebuggerUrl).connect();
	// Chờ frontend nạp xong cầu IPC của Tauri
	while (Date.now() < deadline) {
		const ok = await cdp.eval(`typeof window.__TAURI__?.core?.invoke === 'function'`).catch(() => false);
		if (ok) return new AppSession(cdp);
		await sleep(300);
	}
	cdp.close();
	throw new Error('App đã mở nhưng cầu IPC Tauri chưa sẵn sàng.');
}
