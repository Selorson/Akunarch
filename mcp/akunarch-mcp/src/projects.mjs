// Công cụ dự án — đi qua đúng lệnh IPC projects_* của app (DB + project.akun.json luôn khớp).

const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

/** Gộp sâu patch vào manifest: object gộp đệ quy; mảng / giá trị nguyên thủy / null thay thế. Không sửa đầu vào. */
export function mergeManifest(current, patch) {
	const out = structuredClone(current ?? {});
	for (const [k, v] of Object.entries(patch ?? {})) {
		out[k] = isPlainObject(v) && isPlainObject(out[k]) ? mergeManifest(out[k], v) : structuredClone(v);
	}
	return out;
}

export function projectList(s) {
	return s.invoke('projects_list', {});
}

export async function projectGet(s, slug) {
	const rec = (await projectList(s)).find((p) => p.slug === slug || p.manifest?.slug === slug);
	if (!rec) throw new Error(`Không có dự án '${slug}'.`);
	return rec;
}

export async function projectPatch(s, slug, patch) {
	const rec = await projectGet(s, slug);
	const manifest = mergeManifest(rec.manifest, patch);
	return s.invoke('projects_update', { manifest, originalSlug: slug });
}

export function projectCreate(s, input) {
	return s.invoke('projects_create', { input });
}

export const ASSET_KINDS = ['concept', 'image', 'glb', 'model', 'clockwork', 'audio', 'bgm'];

export function projectImportFile(s, slug, assetKind, sourcePath, setPrimary = false) {
	return s.invoke('projects_import_external_file', { slug, assetKind, sourcePath, setPrimary });
}
