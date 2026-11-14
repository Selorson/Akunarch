import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildLaunchEnv, buildInvokeExpression, connectApp, AppNotDebuggableError } from '../src/app.mjs';

test('buildLaunchEnv chỉ thêm cổng CDP, gỡ biến dữ liệu tạm', () => {
	const env = buildLaunchEnv({ AKUNARCH_DATA_DIR: 'C:\\Temp\\x', AKUNARCH_PROJECTS_DIR: 'y', WEBVIEW2_USER_DATA_FOLDER: 'z', PATH: 'p' });
	assert.equal(env.AKUNARCH_DATA_DIR, undefined);
	assert.equal(env.AKUNARCH_PROJECTS_DIR, undefined);
	assert.equal(env.WEBVIEW2_USER_DATA_FOLDER, undefined);
	assert.match(env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, /--remote-debugging-port=9241/);
	assert.match(env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, /--ignore-gpu-blocklist --enable-webgl --enable-gpu-rasterization/);
	assert.doesNotMatch(env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, /remote-allow-origins/);
	assert.equal(env.PATH, 'p');
});

test('buildInvokeExpression giữ nguyên chuỗi có dấu và khoảng trắng', async () => {
	const args = { sourcePath: 'F:\\FL studio\\toneforge\\Tháp đồng hồ "x".wav' };
	const expr = buildInvokeExpression('projects_import_external_file', args);
	let seen;
	globalThis.window = { __TAURI__: { core: { invoke: async (c, a) => { seen = [c, a]; return 1; } } } };
	await eval(expr);
	delete globalThis.window;
	assert.deepEqual(seen, ['projects_import_external_file', args]);
});

test('app anh mở không có CDP → (được anh cho phép 2026-11-13) đóng app rồi mở lại kèm cổng', async () => {
	const closed = [];
	let probes = 0;
	await assert.rejects(
		connectApp({
			probe: async () => (probes++ === 0 ? { running: true, cdp: false, pids: [42] } : { running: false, cdp: false, pids: [] }),
			closeApp: async (pids) => closed.push(...pids),
			busyJobs: () => [],
			launch: () => {},
			port: 1, // cổng không ai nghe — để test không vớ phải app thật đang mở kèm cổng 9241
			timeoutMs: 50
		}),
		/Không thấy cổng điều khiển CDP/ // không có app thật → hết hạn chờ cổng, nhưng đã đóng đúng PID
	);
	assert.deepEqual(closed, [42]);
});

test('app không có CDP nhưng hàng đợi đang có job chạy/chờ → KHÔNG tắt app (tắt là giết job, vd KTX2 2026-11-14)', async () => {
	const closed = [];
	await assert.rejects(
		connectApp({
			probe: async () => ({ running: true, cdp: false, pids: [42] }),
			closeApp: async (pids) => closed.push(...pids),
			busyJobs: () => [{ id: 62, status: 'running', mode: 'optimize_glb_runtime' }],
			launch: () => {},
			port: 1,
			timeoutMs: 50
		}),
		/job GPU #62/
	);
	assert.deepEqual(closed, []);
});

test('allowClose=false → giữ hành vi cũ: báo lỗi, không đóng app', async () => {
	const closed = [];
	await assert.rejects(
		connectApp({ probe: async () => ({ running: true, cdp: false, pids: [42] }), closeApp: async (p) => closed.push(...p), allowClose: false }),
		(e) => e instanceof AppNotDebuggableError
	);
	assert.deepEqual(closed, []);
});
