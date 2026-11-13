import { invoke } from '@tauri-apps/api/core';
import { openPath } from '@tauri-apps/plugin-opener';
import type {
	AiMeshEntry,
	AssetLibraryRow,
	ChunkPackResult,
	ChunkStitchReport,
	CreateProjectInput,
	GpuJobRow,
	HardwareStackReport,
	MangaPageItem,
	MangaPlateExportResult,
	ProjectManifest,
	ProjectRecord,
	QaAuditReport,
	SelorsonConnectionConfig,
	StudioBootstrapPayload,
	SyncLogRow,
	VaultSnapshot,
	VnEpisodeDocument,
	VnPackResult,
	VnSaveResult,
	VramReleaseResult
} from './types';

export function isTauriRuntime(): boolean {
	return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

/**
 * Resolves a local file path into Akunarch's allowlisted custom URI scheme (`http://akunmedia.localhost/file?path=...`)
 * inside Tauri v2 WebView2 on Windows.
 */
export function mediaUrl(fullPath: string | null | undefined): string {
	if (!fullPath || !fullPath.trim()) return '';
	const encoded = encodeURIComponent(fullPath.trim());
	return `http://akunmedia.localhost/file?path=${encoded}`;
}

export async function openFolderOnDisk(folderPath: string): Promise<void> {
	if (!isTauriRuntime()) return;
	await openPath(folderPath);
}

export async function fileToBase64(file: File): Promise<string> {
	const buf = await file.arrayBuffer();
	const bytes = new Uint8Array(buf);
	const chunkSize = 0x8000;
	const parts: string[] = [];
	for (let i = 0; i < bytes.length; i += chunkSize) {
		parts.push(String.fromCharCode(...bytes.subarray(i, i + chunkSize)));
	}
	return btoa(parts.join(''));
}

export const api = {
	bootstrap: () => invoke<StudioBootstrapPayload>('studio_bootstrap'),
	vaultSnapshot: () => invoke<VaultSnapshot>('vault_get_snapshot'),
	vaultMangaPages: (episodeId: number) =>
		invoke<MangaPageItem[]>('vault_get_manga_pages', { episodeId }),
	vaultScanAssets: () => invoke<AssetLibraryRow[]>('vault_scan_local_assets'),

	projectsList: () => invoke<ProjectRecord[]>('projects_list'),
	projectsRescan: () => invoke<ProjectRecord[]>('projects_rescan'),
	projectsCreate: (input: CreateProjectInput) =>
		invoke<ProjectRecord>('projects_create', { input }),
	projectsUpdate: (manifest: ProjectManifest, originalSlug?: string) =>
		invoke<ProjectRecord>('projects_update', {
			manifest,
			originalSlug: originalSlug ?? null
		}),
	projectsExportBundle: (slug: string) =>
		invoke<string>('projects_export_bundle', { slug }),
	projectsImportExternalFile: (
		slug: string,
		assetKind: 'concept' | 'glb' | 'splat' | 'audio' | 'voice' | 'video',
		sourcePath: string,
		setPrimary = true
	) =>
		invoke<ProjectRecord>('projects_import_external_file', {
			slug,
			assetKind,
			sourcePath,
			setPrimary
		}),
	projectsUploadAssetBytes: (
		slug: string,
		assetKind: 'concept' | 'glb' | 'splat' | 'audio' | 'voice' | 'video',
		fileName: string,
		bytesBase64: string,
		setPrimary = true
	) =>
		invoke<ProjectRecord>('projects_upload_asset_bytes', {
			slug,
			assetKind,
			fileName,
			bytesBase64,
			setPrimary
		}),
	projectsSaveMangaPlates: (
		slug: string,
		width: number,
		height: number,
		beautyPngBase64: string,
		depthPngBase64: string,
		label?: string
	) =>
		invoke<MangaPlateExportResult>('projects_save_manga_plates', {
			slug,
			label: label ?? null,
			width,
			height,
			beautyPngBase64,
			depthPngBase64
		}),
	projectsListAiMeshes: () => invoke<AiMeshEntry[]>('projects_list_ai_meshes'),
	projectsOpenFolder: async (slug: string, subfolder?: string) => {
		const resolved = await invoke<string>('projects_open_folder', {
			slug,
			subfolder: subfolder ?? null
		});
		if (isTauriRuntime() && resolved) {
			await openPath(resolved);
		}
		return resolved;
	},

	gpuHardware: () => invoke<HardwareStackReport>('gpu_hardware_report'),
	gpuListJobs: (limit = 40) => invoke<GpuJobRow[]>('gpu_list_jobs', { limit }),
	gpuEnqueueJob: (projectId: number | null, workerKind: string, payload: Record<string, unknown>) =>
		invoke<GpuJobRow>('gpu_enqueue_job', {
			input: { project_id: projectId, worker_kind: workerKind, payload }
		}),
	gpuCancelJob: (jobId: number) => invoke<GpuJobRow>('gpu_cancel_job', { jobId }),
	/** C2: ảnh xem trước thiếu/cũ hơn .glb → xếp render_preview_card chạy nền (null nếu không cần). */
	projectsEnsurePreviewCard: (slug: string) =>
		invoke<GpuJobRow | null>('projects_ensure_preview_card', { slug }),
	gpuReleaseVram: (comfyuiUrl?: string) =>
		invoke<VramReleaseResult>('gpu_release_vram', { comfyuiUrl: comfyuiUrl ?? null }),

	syncGetConfig: () => invoke<SelorsonConnectionConfig>('sync_get_config'),
	syncSaveConfig: (baseUrl: string, token?: string) =>
		invoke<SelorsonConnectionConfig>('sync_save_config', {
			baseUrl,
			token: token !== undefined ? token : null
		}),
	syncLogin: (baseUrl: string, email: string, password: string) =>
		invoke<Record<string, unknown>>('sync_login_selorson', { baseUrl, email, password }),
	syncFetchOverview: (baseUrl?: string) =>
		invoke<Record<string, unknown>>('sync_fetch_overview', { baseUrl: baseUrl ?? null }),
	syncAuditProject: (slug: string, forceDraft = true) =>
		invoke<QaAuditReport>('sync_audit_project', { slug, forceDraft }),
	syncPushProject: (slug: string, forceDraft = true, baseUrl?: string) =>
		invoke<Record<string, unknown>>('sync_push_project', {
			slug,
			forceDraft,
			baseUrl: baseUrl ?? null
		}),
	syncListLogs: (limit = 30) => invoke<SyncLogRow[]>('sync_list_logs', { limit }),

	chunksGenerateTerrain: (slug: string, biome?: string, amplitudeScale?: number) =>
		invoke<ChunkStitchReport>('chunks_generate_terrain', {
			slug,
			biome: biome ?? null,
			amplitudeScale: amplitudeScale ?? null
		}),
	chunksSculptTerrain: (
		slug: string,
		localX: number,
		localZ: number,
		radiusM: number,
		strengthOrTarget: number,
		brushMode: 'raise' | 'lower' | 'flatten' | 'smooth'
	) =>
		invoke<ChunkStitchReport>('chunks_sculpt_terrain', {
			slug,
			localX,
			localZ,
			radiusM,
			strengthOrTarget,
			brushMode
		}),
	chunksStitchNeighbors: (slug: string) =>
		invoke<ChunkStitchReport>('chunks_stitch_neighbors', { slug }),
	chunksPackZip: (slug: string) => invoke<ChunkPackResult>('chunks_pack_zip', { slug }),

	vnLoadEpisode: (slug: string) => invoke<VnEpisodeDocument>('vn_load_episode', { slug }),
	vnSaveEpisode: (slug: string, episode: VnEpisodeDocument) =>
		invoke<VnSaveResult>('vn_save_episode', { slug, episode }),
	vnPackEpisode: (slug: string) => invoke<VnPackResult>('vn_pack_episode', { slug })
};
