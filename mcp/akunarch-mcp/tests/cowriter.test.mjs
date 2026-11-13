import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { openCowriterRO, cowriterEntity, cowriterSearch } from '../src/cowriter.mjs';
import { buildPushArgs } from '../src/selorson.mjs';

let dir, path;
before(() => {
	dir = mkdtempSync(join(tmpdir(), 'cw-'));
	path = join(dir, 'co_writer.db');
	const w = new DatabaseSync(path);
	w.exec(`CREATE TABLE story_entities (id INTEGER PRIMARY KEY, subject_key TEXT, kind TEXT, name TEXT, role TEXT, summary TEXT,
		mention_count INTEGER DEFAULT 0, visual_anchor TEXT);
		INSERT INTO story_entities VALUES (13,'place:eryndor','place','Eryndor',NULL,'Thị trấn cổ phía đông Ai Cập',127,NULL);
		INSERT INTO story_entities VALUES (499,'thap dong ho thien van eryndor','place','Tháp Đồng Hồ Thiên Văn Eryndor',NULL,'Tòa tháp bazan',8,'tower');`);
	w.close();
});
after(() => rmSync(dir, { recursive: true, force: true }));

test('cowriterEntity tìm theo id, subject_key, tên', () => {
	const db = openCowriterRO(path);
	assert.equal(cowriterEntity(db, 499).name, 'Tháp Đồng Hồ Thiên Văn Eryndor');
	assert.equal(cowriterEntity(db, 'thap dong ho thien van eryndor').id, 499);
	assert.equal(cowriterEntity(db, 'Eryndor').id, 13);
	assert.equal(cowriterEntity(db, 'không có'), null);
	db.close();
});

test('cowriterSearch lọc kind, sắp theo mention_count', () => {
	const db = openCowriterRO(path);
	assert.deepEqual(cowriterSearch(db, { kind: 'place', query: 'Eryndor' }).map((e) => e.id), [13, 499]);
	db.close();
});

test('Co-Writer mở chỉ-đọc: ghi phải bị từ chối', () => {
	const db = openCowriterRO(path);
	assert.throws(() => db.exec("INSERT INTO story_entities(name) VALUES('x')"));
	db.close();
});

test('buildPushArgs luôn forceDraft = true', () => {
	assert.deepEqual(buildPushArgs('a', { forceDraft: false, baseUrl: 'http://x' }), { slug: 'a', forceDraft: true, baseUrl: null });
});
