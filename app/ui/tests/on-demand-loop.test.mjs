/**
 * Đợt A · A3 — Vòng render theo nhu cầu phải tự ngủ (0 rAF) khi cảnh đứng yên.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { createOnDemandLoop, setAllLoopsSuspended } from '../src/lib/webgl/on-demand-loop.ts';

function fakeScheduler() {
	let nextId = 1;
	let t = 0;
	const queue = new Map();
	return {
		request: (cb) => {
			const id = nextId++;
			queue.set(id, cb);
			return id;
		},
		cancel: (id) => queue.delete(id),
		now: () => t,
		/** Chạy 1 khung: gọi các callback đang chờ. Trả về số callback đã chạy. */
		tick(ms = 16) {
			t += ms;
			const cbs = [...queue.values()];
			queue.clear();
			for (const cb of cbs) cb(t);
			return cbs.length;
		},
		get pendingCount() {
			return queue.size;
		}
	};
}

test('không có invalidate thì không có rAF nào', () => {
	const s = fakeScheduler();
	let frames = 0;
	const loop = createOnDemandLoop(() => void frames++, s);
	assert.equal(s.pendingCount, 0);
	assert.equal(loop.running, false);
	assert.equal(frames, 0);
});

test('invalidate(n) vẽ đúng n khung rồi ngủ hẳn', () => {
	const s = fakeScheduler();
	let frames = 0;
	const loop = createOnDemandLoop(() => void frames++, s);
	loop.invalidate(3);
	while (s.tick()) {
		// chạy tới khi hết rAF
	}
	assert.equal(frames, 3);
	assert.equal(loop.running, false);
	assert.equal(s.pendingCount, 0);
});

test('step trả true (damping còn quán tính) thì tiếp tục, trả false thì ngủ', () => {
	const s = fakeScheduler();
	let remainingDamping = 5;
	let frames = 0;
	const loop = createOnDemandLoop(() => {
		frames++;
		return remainingDamping-- > 0;
	}, s);
	loop.invalidate(1);
	let guard = 0;
	while (s.tick() && guard++ < 100) {
		// chạy
	}
	assert.equal(frames, 6);
	assert.equal(loop.running, false);
});

test('setContinuous giữ vòng chạy, tắt lý do cuối cùng thì ngủ; nhiều lý do độc lập', () => {
	const s = fakeScheduler();
	let frames = 0;
	const loop = createOnDemandLoop(() => void frames++, s);
	loop.setContinuous('waves', true);
	loop.setContinuous('autoRotate', true);
	for (let i = 0; i < 10; i++) s.tick();
	assert.equal(frames, 10);
	loop.setContinuous('waves', false);
	for (let i = 0; i < 5; i++) s.tick();
	assert.equal(frames, 15, 'vẫn chạy vì còn autoRotate');
	loop.setContinuous('autoRotate', false);
	s.tick();
	assert.equal(s.tick(), 0, 'hết lý do → không còn rAF');
	assert.equal(loop.running, false);
});

test('dispose hủy rAF đang chờ và chặn mọi invalidate sau đó', () => {
	const s = fakeScheduler();
	let frames = 0;
	const loop = createOnDemandLoop(() => void frames++, s);
	loop.setContinuous('wasd', true);
	loop.dispose();
	assert.equal(s.pendingCount, 0);
	loop.invalidate(5);
	assert.equal(s.tick(), 0);
	assert.equal(frames, 0);
});

test('setAllLoopsSuspended: thu nhỏ cửa sổ → dừng cả vòng liên tục; khôi phục → chạy lại đúng lý do cũ', () => {
	const s = fakeScheduler();
	let frames = 0;
	const loop = createOnDemandLoop(() => void frames++, s);
	loop.setContinuous('autoRotate', true);
	s.tick();
	s.tick();
	assert.equal(frames, 2);
	setAllLoopsSuspended(true);
	s.tick(); // khung đã xin trước khi tạm ngưng: không vẽ, không xin tiếp
	assert.equal(s.tick(), 0, 'đang tạm ngưng → không còn rAF');
	loop.invalidate(3);
	assert.equal(s.tick(), 0, 'invalidate khi tạm ngưng cũng không xin rAF');
	const framesWhileSuspended = frames;
	setAllLoopsSuspended(false);
	s.tick();
	s.tick();
	assert.ok(frames > framesWhileSuspended, 'khôi phục → autoRotate chạy tiếp');
	loop.dispose();
	setAllLoopsSuspended(true);
	setAllLoopsSuspended(false);
	assert.equal(s.tick(), 0, 'vòng đã dispose không bị đánh thức lại');
});

test('dt được kẹp tối đa 0.05s sau thời gian ngủ dài', () => {
	const s = fakeScheduler();
	const dts = [];
	const loop = createOnDemandLoop((dt) => void dts.push(dt), s);
	loop.invalidate(1);
	s.tick(5000);
	assert.ok(dts[0] <= 0.05);
});
