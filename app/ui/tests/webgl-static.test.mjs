/**
 * Đợt A · A8 — Kiểm tra tĩnh các nguyên tắc của Kế hoạch VRAM v2 (mục 2) trên toàn bộ app/ui/src.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const UI_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = path.join(UI_ROOT, 'src');

function walk(dir) {
	const out = [];
	for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
		const p = path.join(dir, e.name);
		if (e.isDirectory()) out.push(...walk(p));
		else if (/\.(svelte|ts|js)$/.test(e.name)) out.push(p);
	}
	return out;
}
const files = walk(SRC).map((f) => ({ f, rel: path.relative(SRC, f).replace(/\\/g, '/'), code: fs.readFileSync(f, 'utf8') }));

test('Cấm mất context nhân tạo: không có .forceContextLoss( / .loseContext( / getExtension("WEBGL_lose_context")', () => {
	const forbidden = [/\.forceContextLoss\s*\(/, /\.loseContext\s*\(/, /getExtension\(\s*['"`]WEBGL_lose_context/];
	for (const { rel, code } of files) {
		for (const re of forbidden) assert.ok(!re.test(code), `${rel} vi phạm ${re}`);
	}
});

test('Chỉ đúng 1 nơi tạo WebGLRenderer: lib/webgl/webgl-stage.ts (renderer dùng chung cho cả app)', () => {
	const hits = [];
	for (const { rel, code } of files) {
		const n = (code.match(/new\s+(?:THREE\.|T\.)?WebGLRenderer\s*\(/g) ?? []).length;
		if (n) hits.push(`${rel}×${n}`);
	}
	assert.deepEqual(hits, ['lib/webgl/webgl-stage.ts×1']);
});

test('Không còn preserveDrawingBuffer: true (chụp ảnh render rồi toDataURL trong cùng tác vụ)', () => {
	for (const { rel, code } of files) {
		assert.ok(!/preserveDrawingBuffer\s*:\s*true/.test(code), `${rel} còn preserveDrawingBuffer: true`);
	}
});

test('3 sân khấu 3D mượn renderer dùng chung + vòng render theo nhu cầu + bộ dọn tài nguyên', () => {
	for (const name of ['RealPbrStageViewport.svelte', 'OpenWorldChunkWorkbench.svelte', 'VnDirectorStagePanel.svelte']) {
		const code = files.find((x) => x.rel === `lib/components/${name}`)?.code ?? '';
		assert.ok(code.includes('acquireStage('), `${name} phải dùng acquireStage`);
		assert.ok(code.includes('createOnDemandLoop('), `${name} phải dùng createOnDemandLoop`);
		assert.ok(/disposeObject3DDeep\(/.test(code), `${name} phải dọn cây scene bằng disposeObject3DDeep`);
		assert.ok(!/requestAnimationFrame\(/.test(code), `${name} không được tự quay requestAnimationFrame`);
	}
});

test('Tab 02 & 03 không import tĩnh three / Spark (chỉ import type) — nạp động khi bật 3D', () => {
	for (const name of ['OpenWorldChunkWorkbench.svelte', 'VnDirectorStagePanel.svelte']) {
		const code = files.find((x) => x.rel === `lib/components/${name}`)?.code ?? '';
		const staticValueImports = code.match(/^\s*import\s+(?!type\b)[^;]*from\s+['"](three|three\/examples[^'"]*|@sparkjsdev\/spark)['"]/gm) ?? [];
		assert.deepEqual(staticValueImports, [], `${name} còn import tĩnh: ${staticValueImports.join(' | ')}`);
	}
});
