import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pollUntilDone, gpuEnqueue } from '../src/gpu.mjs';

const mk = (seq) => {
	let i = 0;
	return async () => seq[Math.min(i++, seq.length - 1)];
};
const fake = () => {
	let t = 0;
	return { now: () => t, sleep: async (ms) => { t += ms; } };
};

test('completed trả output_path', async () => {
	const r = await pollUntilDone(
		mk([{ status: 'queued' }, { status: 'running' }, { status: 'completed', output_path: 'E:\\o.glb', error_log: '', vram_peak_mb: 9000 }]),
		fake()
	);
	assert.equal(r.status, 'completed');
	assert.equal(r.output_path, 'E:\\o.glb');
	assert.equal(r.vram_peak_mb, 9000);
});

test('failed trả error_log', async () => {
	const r = await pollUntilDone(mk([{ status: 'failed', error_log: 'Blender hết 900 s' }]), fake());
	assert.equal(r.status, 'failed');
	assert.match(r.error_log, /900 s/);
});

test('quá hạn trả timeout, không ném lỗi', async () => {
	const r = await pollUntilDone(mk([{ status: 'running' }]), { ...fake(), timeoutMs: 10_000 });
	assert.equal(r.status, 'timeout');
});

test('cancelled là trạng thái kết thúc', async () => {
	const r = await pollUntilDone(mk([{ status: 'cancelled' }]), fake());
	assert.equal(r.status, 'cancelled');
});

test('gpuEnqueue tra project_id theo slug và thêm project_slug vào payload', async () => {
	const calls = [];
	const s = {
		invoke: async (c, a) => {
			calls.push([c, a]);
			return c === 'projects_list' ? [{ id: 42, slug: 'eryndor-clocktower-concept', manifest: {} }] : { id: 1, status: 'queued' };
		}
	};
	await gpuEnqueue(s, 'eryndor-clocktower-concept', 'blender', { mode: 'assemble_glb' });
	assert.deepEqual(calls.at(-1), [
		'gpu_enqueue_job',
		{ input: { project_id: 42, worker_kind: 'blender', payload: { mode: 'assemble_glb', project_slug: 'eryndor-clocktower-concept' } } }
	]);
});
