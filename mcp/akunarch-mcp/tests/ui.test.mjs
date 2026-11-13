import { test } from 'node:test';
import assert from 'node:assert/strict';
import { screenshotPath, uiOpenProject, uiScreenshot } from '../src/ui.mjs';

test('uiScreenshot: cửa sổ đang thu nhỏ → tạm bung ra để chụp (GPU không vẽ khi thu nhỏ) rồi thu nhỏ lại', async () => {
	const evals = [];
	let minimized = true;
	const s = {
		evaluate: async (e) => {
			evals.push(e);
			if (e.includes('isMinimized')) return minimized;
			return true;
		},
		screenshot: async () => {
			assert.equal(minimized, false, 'chụp lúc cửa sổ còn thu nhỏ → ảnh đen');
			return Buffer.from('png');
		}
	};
	const win = { restore: async () => { minimized = false; }, minimize: async () => { minimized = true; } };
	const r = await uiScreenshot(s, 'x', { dir: (await import('node:os')).tmpdir(), settleMs: 0, win });
	assert.equal(r.bytes, 3);
	assert.equal(minimized, true, 'trả cửa sổ về trạng thái thu nhỏ như anh để');
});

test('screenshotPath bỏ ký tự cấm, giữ chữ có dấu', () => {
	assert.equal(screenshotPath('CMP: Tháp/thật?'), 'E:\\Akunarch\\docs\\p0\\screenshots\\CMP_ Tháp_thật_.png');
	assert.equal(screenshotPath('a.png', 'D:\\x'), 'D:\\x\\a.png');
});

test('uiOpenProject bấm nav-projects rồi thẻ dự án đúng slug', async () => {
	const evals = [];
	const s = {
		evaluate: async (e) => {
			evals.push(e);
			if (e.includes('__probeState')) return { cardFound: true, standby: true, partsCount: 0, canvas: false };
			return true;
		}
	};
	const r = await uiOpenProject(s, 'eryndor-clocktower-concept', { settleMs: 0 });
	const iNav = evals.findIndex((e) => e.includes('[data-testid="nav-projects"]'));
	const iCard = evals.findIndex((e) => e.includes('[data-testid="project-card-eryndor-clocktower-concept"]'));
	assert.ok(iNav >= 0 && iCard > iNav);
	assert.equal(r.standby, true);
});

test('uiOpenProject báo lỗi khi không thấy thẻ dự án', async () => {
	const s = { evaluate: async (e) => (e.includes('__probeState') ? { cardFound: false } : true) };
	await assert.rejects(uiOpenProject(s, 'khong-co', { settleMs: 0 }), /Không thấy thẻ dự án 'khong-co'/);
});
