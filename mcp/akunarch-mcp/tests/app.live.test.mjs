// Kiểm sống trên akunarch.exe đã cài. Chạy: $env:AKUNARCH_LIVE=1; node --test tests/app.live.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { appStatus, connectApp, EXE } from '../src/app.mjs';

const live = { skip: process.env.AKUNARCH_LIVE !== '1' && 'đặt AKUNARCH_LIVE=1 để chạy' };

test('connectApp → projects_list có Eryndor; SHA exe khớp', live, async () => {
	const s = await connectApp();
	try {
		const list = await s.invoke('projects_list', {});
		assert.ok(Array.isArray(list));
		assert.ok(list.some((p) => p.manifest?.slug === 'eryndor-clocktower-concept' || p.slug === 'eryndor-clocktower-concept'));
	} finally {
		s.close();
	}
	const st = await appStatus();
	assert.equal(st.running, true);
	assert.equal(st.cdp, true);
	assert.equal(st.exeSha256, createHash('sha256').update(readFileSync(EXE)).digest('hex'));
});
