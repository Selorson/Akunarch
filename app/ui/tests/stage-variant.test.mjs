import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pickStageGlb, pickClockworkClips } from '../src/lib/webgl/stage-variant.ts';

test('pickStageGlb: bản thật / bản cơ khí', () => {
	const cw = { glb_path: 'E:\\a\\real.glb', mechanism_glb_path: 'E:\\a\\real_mechanism.glb' };
	assert.equal(pickStageGlb(cw, 'real'), 'E:\\a\\real.glb');
	assert.equal(pickStageGlb(cw, 'mechanism'), 'E:\\a\\real_mechanism.glb');
	assert.equal(pickStageGlb({ glb_path: 'a', mechanism_glb_path: null }, 'mechanism'), null);
	assert.equal(pickStageGlb({ glb_path: '  ', mechanism_glb_path: '' }, 'real'), null);
	assert.equal(pickStageGlb(null, 'real'), null);
});

test('pickClockworkClips: assemble 1 lần rồi lặp idle', () => {
	assert.deepEqual(pickClockworkClips(['idle', 'assemble']), { intro: 'assemble', loop: 'idle' });
	assert.deepEqual(pickClockworkClips(['assemble']), { intro: 'assemble', loop: null });
	assert.deepEqual(pickClockworkClips(['Turntable']), { intro: null, loop: null });
	assert.deepEqual(pickClockworkClips([]), { intro: null, loop: null });
});
