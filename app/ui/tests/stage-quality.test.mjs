/**
 * Đợt B · B0 — 2 lỗi phát hiện khi bấm thật trên bản Đợt A:
 *  1. Nút Ultra không có tác dụng trên màn DPR 1.0 (canvas giữ nguyên 569×454 vì Ultra = min(dpr, 1.5) = 1.0).
 *  2. Tab 03 Camera Rig 3D: nền tối đi (RGB 12,21,34 → 2,6,16) vì chuyển sang composer MSAA nên clear color
 *     bị OutputPass tone-map ACES (vẽ thẳng ra canvas trước đây thì clear color không bị tone-map).
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import { acesFilmic, inverseAcesFilmic, pbrPixelRatio } from '../src/lib/webgl/stage-quality.ts';

test('HD: DPR màn hình, tối đa 1.0', () => {
	assert.equal(pbrPixelRatio('hd', 1), 1);
	assert.equal(pbrPixelRatio('hd', 1.25), 1);
	assert.equal(pbrPixelRatio('hd', 2), 1);
	assert.equal(pbrPixelRatio('hd', 0), 1);
});

test('Ultra: siêu lấy mẫu 1.5 kể cả trên màn DPR 1.0 (khác HD thật)', () => {
	assert.equal(pbrPixelRatio('ultra', 1), 1.5);
	assert.equal(pbrPixelRatio('ultra', 1.25), 1.5);
	assert.equal(pbrPixelRatio('ultra', 2), 1.5);
	assert.notEqual(pbrPixelRatio('ultra', 1), pbrPixelRatio('hd', 1));
});

test('acesFilmic khớp công thức shader three r178 (điểm đen, giá trị trung bình, bão hòa)', () => {
	assert.deepEqual(acesFilmic([0, 0, 0], 1), [0, 0, 0]);
	const mid = acesFilmic([0.18, 0.18, 0.18], 1);
	for (const c of mid) assert.ok(c > 0.15 && c < 0.3, `xám 18% → ${c}`);
	assert.deepEqual(acesFilmic([100, 100, 100], 1), [1, 1, 1]);
});

test('inverseAcesFilmic: tone-map lại ra đúng màu nền gốc (sai số < 1/255 sau sRGB)', () => {
	const srgbToLinear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
	const linearToSrgb = (c) => (c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055);
	const bgs = [
		[12, 21, 34], // #0c1522 (mist / clear)
		[28, 20, 32], // #1c1420 (sunset)
		[11, 16, 25], // #0b1019 (tab 01 earth)
		[120, 140, 160]
	];
	for (const exposure of [1.0, 1.08, 1.4]) {
		for (const bg of bgs) {
			const lin = bg.map((v) => srgbToLinear(v / 255));
			const out = acesFilmic(inverseAcesFilmic(lin, exposure), exposure).map((v) => linearToSrgb(v) * 255);
			for (let i = 0; i < 3; i++) assert.ok(Math.abs(out[i] - bg[i]) < 1, `exp ${exposure} ${bg} → ${out}`);
		}
	}
});

test('Tab 03 Camera Rig dùng bù ACES cho màu nền; tab 01 dùng pbrPixelRatio', () => {
	const vn = fs.readFileSync(new URL('../src/lib/components/VnDirectorStagePanel.svelte', import.meta.url), 'utf8');
	assert.match(vn, /inverseAcesFilmic\(/);
	const pbr = fs.readFileSync(new URL('../src/lib/components/RealPbrStageViewport.svelte', import.meta.url), 'utf8');
	assert.match(pbr, /pbrPixelRatio\(/);
});
