/**
 * Kế hoạch VRAM v2 · Đợt C · C2 — Chế độ Chờ 2D (Q2: bật mặc định).
 * Cold boot / đổi tab không được tạo context WebGL cho tới khi người dùng bấm ▶; ⏹ và sự kiện nhường VRAM trả renderer.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const read = (rel) => fs.readFileSync(new URL(`../${rel}`, import.meta.url), 'utf8');

test('store phiên: mặc định 2D cho tab 01 và 02; sự kiện nhường VRAM đưa cả hai về 2D', () => {
	const src = read('src/lib/webgl/stage-mode.svelte.ts');
	assert.match(src, /pbr3d:\s*false/);
	assert.match(src, /chunk3d:\s*false/);
	assert.match(src, /RELEASE_WEBGL_VRAM_EVENT/);
});

test('tab 01: thẻ chờ 2D + nút ▶/⏹; sân khấu chỉ dựng khi stageMode.pbr3d', () => {
	const src = read('src/lib/components/RealPbrStageViewport.svelte');
	for (const id of ['pbr-2d-standby-card', 'activate-3d-stage-btn', 'deactivate-3d-stage-btn'])
		assert.ok(src.includes(`data-testid="${id}"`), `thiếu ${id}`);
	assert.match(src, /const active3d = stageMode\.pbr3d;/);
	assert.match(src, /previewRenderPath/);
});

test('tab 02: thẻ chờ 2D + nút ▶/⏹; sân khấu chỉ dựng khi stageMode.chunk3d', () => {
	const src = read('src/lib/components/OpenWorldChunkWorkbench.svelte');
	for (const id of ['chunk-2d-standby-card', 'activate-chunk-3d-btn', 'deactivate-chunk-3d-btn'])
		assert.ok(src.includes(`data-testid="${id}"`), `thiếu ${id}`);
	assert.match(src, /const active3d = stageMode\.chunk3d;/);
});

test('tab 03 rig3d về chế độ play khi có yêu cầu nhường VRAM', () => {
	const src = read('src/lib/components/VnDirectorStagePanel.svelte');
	assert.match(src, /RELEASE_WEBGL_VRAM_EVENT/);
});

test('ClockworkConfig có preview_render_path (Rust serde default + TS)', () => {
	assert.match(read('src/lib/types.ts'), /preview_render_path\?: string \| null/);
	const rs = fs.readFileSync(new URL('../../src-tauri/src/projects.rs', import.meta.url), 'utf8');
	assert.match(rs, /#\[serde\(default\)\]\s*pub preview_render_path: Option<String>/);
});
