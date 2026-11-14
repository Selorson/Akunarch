#!/usr/bin/env node
// MCP server `akunarch` (stdio) — cổng điều khiển AI cho Akunarch. Xem README.md.
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { appStatus, connectApp } from './app.mjs';
import { projectList, projectGet, projectPatch, projectCreate, projectImportFile, ASSET_KINDS } from './projects.mjs';
import { gpuEnqueue, gpuJobs, gpuWait, gpuCancel } from './gpu.mjs';
import { uiOpenProject, uiScreenshot } from './ui.mjs';
import { openCowriterRO, cowriterEntity, cowriterSearch } from './cowriter.mjs';
import { selorsonAudit, selorsonPushDraft } from './selorson.mjs';

const WORKER_KINDS = ['blender', 'comfyui', 'worldgen', 'hunyuan3d', 'tts', 'materialcraft', 'effectcraft', 'filmcraft', 'toneforge'];
const Obj = z.record(z.string(), z.unknown());

let session = null;
async function app() {
	if (!session?.open) session = await connectApp();
	return session;
}

const text = (v) => ({ content: [{ type: 'text', text: typeof v === 'string' ? v : JSON.stringify(v, null, 2) }] });
const run = (fn) => async (args) => {
	try {
		return await fn(args ?? {});
	} catch (e) {
		return { isError: true, content: [{ type: 'text', text: String(e?.message ?? e) }] };
	}
};
function withCowriter(fn) {
	const db = openCowriterRO();
	try {
		return fn(db);
	} finally {
		db.close();
	}
}

const server = new McpServer({ name: 'akunarch', version: '0.1.0' });
const tool = (name, description, inputSchema, fn) => server.registerTool(name, { description, inputSchema }, run(fn));

tool('app_status', 'Trạng thái akunarch.exe đã cài: đang chạy?, có cổng điều khiển CDP?, SHA-256 của exe.', {}, async () =>
	text(await appStatus())
);

tool('project_list', 'Danh sách dự án (tóm tắt: id, slug, title, kind, planet, status).', {}, async () =>
	text((await projectList(await app())).map(({ id, slug, title, kind, planet, status }) => ({ id, slug, title, kind, planet, status })))
);
tool('project_get', 'Toàn bộ bản ghi + manifest (project.akun.json) của một dự án.', { slug: z.string() }, async ({ slug }) =>
	text(await projectGet(await app(), slug))
);
tool(
	'project_patch',
	'Sửa manifest dự án bằng patch gộp sâu (trường không nhắc tới giữ nguyên; mảng/null thay thế). Đi qua projects_update nên DB và file luôn khớp.',
	{ slug: z.string(), patch: Obj },
	async ({ slug, patch }) => text(await projectPatch(await app(), slug, patch))
);
tool('project_create', 'Tạo dự án mới (CreateProjectInput của app: slug, title, kind, planet...).', { input: Obj }, async ({ input }) =>
	text(await projectCreate(await app(), input))
);
tool(
	'project_import_file',
	'Nhập tệp ngoài (BYOA) vào dự án: concept/image → concepts, glb/model/clockwork → clockwork, audio/bgm → audio.',
	{ slug: z.string(), asset_kind: z.enum(ASSET_KINDS), source_path: z.string(), set_primary: z.boolean().optional() },
	async ({ slug, asset_kind, source_path, set_primary }) =>
		text(await projectImportFile(await app(), slug, asset_kind, source_path, set_primary ?? false))
);

tool(
	'gpu_enqueue',
	'Xếp job vào GpuJobQueue của app (một model một lúc). payload.mode chọn việc (vd assemble_glb, optimize_glb_runtime, render_intro_mp4, sculpt_hero_parts, probe).',
	{ slug: z.string().nullable().optional(), worker_kind: z.enum(WORKER_KINDS), payload: Obj },
	async ({ slug, worker_kind, payload }) => text(await gpuEnqueue(await app(), slug ?? null, worker_kind, payload))
);
tool('gpu_jobs', 'Các job GPU gần nhất.', { limit: z.number().int().min(1).max(200).optional() }, async ({ limit }) =>
	text(await gpuJobs(await app(), limit ?? 20))
);
tool(
	'gpu_wait',
	'Chờ job kết thúc. Trả completed/failed/cancelled (kèm output_path, error_log, vram_peak_mb) hoặc timeout — gọi lại để chờ tiếp.',
	{ job_id: z.number().int(), timeout_sec: z.number().int().min(5).max(3600).optional() },
	async ({ job_id, timeout_sec }) => text(await gpuWait(await app(), job_id, timeout_sec ?? 600))
);
tool('gpu_cancel', 'Huỷ job còn ở trạng thái queued.', { job_id: z.number().int() }, async ({ job_id }) =>
	text(await gpuCancel(await app(), job_id))
);

tool(
	'ui_open_project',
	'Mở tab Dự án và chọn dự án; stage3d=true thì bật sân khấu 3D và chờ lên hình. variant="mechanism" chuyển sang bản cơ khí; seekSec dừng animation ở giây đó (assemble 0–24 s).',
	{ slug: z.string(), stage3d: z.boolean().optional(), variant: z.enum(['real', 'mechanism']).optional(), seekSec: z.number().optional() },
	async ({ slug, stage3d, variant, seekSec }) =>
		text(await uiOpenProject(await app(), slug, { stage3d: stage3d ?? false, variant, seekSec }))
);
tool(
	'ui_screenshot',
	'Chụp cửa sổ app (hoặc riêng phần tử selector) → PNG trong E:\\Akunarch\\docs\\p0\\screenshots, trả kèm ảnh để xem ngay.',
	{ name: z.string(), selector: z.string().optional(), dir: z.string().optional() },
	async ({ name, selector, dir }) => {
		const r = await uiScreenshot(await app(), name, { selector, dir });
		return {
			content: [
				{ type: 'text', text: `${r.path} (${r.bytes} byte)` },
				{ type: 'image', data: r.buffer.toString('base64'), mimeType: 'image/png' }
			]
		};
	}
);

tool('cowriter_entity', 'Đọc 1 thực thể Co-Writer (chỉ đọc) theo id, subject_key hoặc tên chính xác.', { key: z.union([z.string(), z.number()]) }, async ({ key }) =>
	text(withCowriter((db) => cowriterEntity(db, key)) ?? 'Không tìm thấy.')
);
tool(
	'cowriter_search',
	'Tìm thực thể Co-Writer (chỉ đọc) theo chữ trong tên/tóm tắt; kind: character, place, item, faction, concept, lore.',
	{ query: z.string(), kind: z.string().optional(), limit: z.number().int().min(1).max(200).optional() },
	async ({ query, kind, limit }) => text(withCowriter((db) => cowriterSearch(db, { query, kind, limit })))
);

tool('selorson_audit', 'Kiểm định dự án trước khi đẩy sang Selorson (không gửi gì).', { slug: z.string() }, async ({ slug }) =>
	text(await selorsonAudit(await app(), slug))
);
tool(
	'selorson_push_draft',
	'Đẩy dự án sang Selorson ở trạng thái Nháp (is_active=false). CHỈ gọi sau khi anh đồng ý trong chat cho đúng lần đẩy này.',
	{ slug: z.string() },
	async ({ slug }) => text(await selorsonPushDraft(await app(), slug))
);

await server.connect(new StdioServerTransport());
