import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mergeManifest, projectPatch, projectGet } from '../src/projects.mjs';

test('mergeManifest giữ mọi trường không có trong patch', () => {
	const cur = { slug: 'a', planet: 'akunalia', clockwork: { glb_path: 'g', preview_render_path: 'p', parts: [1, 2] }, stage_vn: { episode_title: 't' } };
	const out = mergeManifest(cur, { planet: 'earth', clockwork: { glb_path: 'g2' } });
	assert.equal(out.planet, 'earth');
	assert.equal(out.clockwork.glb_path, 'g2');
	assert.equal(out.clockwork.preview_render_path, 'p');
	assert.deepEqual(out.clockwork.parts, [1, 2]);
	assert.deepEqual(out.stage_vn, { episode_title: 't' });
	assert.equal(cur.planet, 'akunalia', 'không sửa object gốc');
});

test('mảng bị thay thế, null đặt về null', () => {
	const out = mergeManifest({ concept_paths: ['a', 'b'], lat: 1 }, { concept_paths: ['c'], lat: null });
	assert.deepEqual(out.concept_paths, ['c']);
	assert.equal(out.lat, null);
});

test('projectPatch gửi manifest đầy đủ và originalSlug', async () => {
	const calls = [];
	const s = {
		invoke: async (c, a) => {
			calls.push([c, a]);
			return c === 'projects_list' ? [{ id: 7, manifest: { slug: 'x', title: 'T', era: '' } }] : { id: 7 };
		}
	};
	await projectPatch(s, 'x', { era: 'Thế kỷ XIV' });
	assert.deepEqual(calls[1], ['projects_update', { manifest: { slug: 'x', title: 'T', era: 'Thế kỷ XIV' }, originalSlug: 'x' }]);
});

test('projectGet báo lỗi rõ khi không có slug', async () => {
	const s = { invoke: async () => [] };
	await assert.rejects(projectGet(s, 'khong-co'), /Không có dự án 'khong-co'/);
});
