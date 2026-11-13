/**
 * Đợt B · B3 — .glb kỳ quan dùng texture KTX2 (KHR_texture_basisu): cả 3 sân khấu phải nạp được,
 * transcoder Basis chạy offline từ static/basis (không CDN), một KTX2Loader dùng chung theo renderer chung.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const read = (rel) => fs.readFileSync(new URL(`../${rel}`, import.meta.url), 'utf8');

test('Basis transcoder offline nằm trong static/basis', () => {
	for (const f of ['basis_transcoder.js', 'basis_transcoder.wasm']) {
		const p = new URL(`../static/basis/${f}`, import.meta.url);
		assert.ok(fs.existsSync(p), `thiếu static/basis/${f}`);
		assert.ok(fs.statSync(p).size > 10_000, `${f} rỗng`);
	}
});

test('KTX2Loader dùng chung: transcoder /basis/, detectSupport trên renderer chung', () => {
	const src = read('src/lib/webgl/ktx2.ts');
	assert.match(src, /setTranscoderPath\(\s*'\/basis\/'\s*\)/);
	assert.match(src, /detectSupport\(/);
	assert.ok(!/https?:\/\//.test(src), 'không được nạp transcoder từ mạng');
});

test('Cả 3 sân khấu gắn KTX2Loader vào GLTFLoader', () => {
	for (const f of ['RealPbrStageViewport', 'OpenWorldChunkWorkbench', 'VnDirectorStagePanel']) {
		const src = read(`src/lib/components/${f}.svelte`);
		assert.match(src, /getSharedKtx2Loader\(renderer\)/, `${f} chưa lấy KTX2Loader dùng chung`);
		assert.match(src, /\.setKTX2Loader\(/, `${f} chưa setKTX2Loader`);
	}
});
