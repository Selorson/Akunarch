// Đọc Co-Writer — Luật #6: chỉ mở readOnly + PRAGMA query_only, không bao giờ ghi.
import { DatabaseSync } from 'node:sqlite';
import { join } from 'node:path';

export const COWRITER_DB = join(process.env.LOCALAPPDATA ?? 'C:\\Users\\Admin\\AppData\\Local', 'Co-Writer', 'co_writer.db');
const COLS = 'id, subject_key, kind, name, summary, visual_anchor, mention_count';

export function openCowriterRO(path = COWRITER_DB) {
	const db = new DatabaseSync(path, { readOnly: true });
	db.exec('PRAGMA query_only = ON');
	return db;
}

/** Tìm 1 thực thể theo id (số), subject_key, hoặc tên chính xác. */
export function cowriterEntity(db, idOrKeyOrName) {
	const v = String(idOrKeyOrName).trim();
	if (/^\d+$/.test(v)) return db.prepare(`SELECT ${COLS} FROM story_entities WHERE id = ?`).get(Number(v)) ?? null;
	return (
		db.prepare(`SELECT ${COLS} FROM story_entities WHERE subject_key = ?`).get(v) ??
		db.prepare(`SELECT ${COLS} FROM story_entities WHERE name = ? ORDER BY mention_count DESC`).get(v) ??
		null
	);
}

export function cowriterSearch(db, { kind, query = '', limit = 20 } = {}) {
	const like = `%${String(query).replace(/[\\%_]/g, (c) => `\\${c}`)}%`;
	const where = [`(name LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\')`];
	const params = [like, like];
	if (kind) {
		where.push('kind = ?');
		params.push(kind);
	}
	return db
		.prepare(`SELECT ${COLS} FROM story_entities WHERE ${where.join(' AND ')} ORDER BY mention_count DESC LIMIT ?`)
		.all(...params, Math.min(Math.max(1, limit), 200));
}
