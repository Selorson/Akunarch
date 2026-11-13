export interface VaultSummary {
	db_path: string;
	readonly_verified: boolean;
	entities_count: number;
	arcs_count: number;
	chapters_count: number;
	sketches_count: number;
	manga_episodes_count: number;
	manga_pages_count: number;
	concepts_canon_15_count: number;
	concepts_canon_extended_count: number;
	concepts_total_count: number;
}

export interface StoryEntityItem {
	id: number;
	subject_key: string;
	kind: string;
	name: string;
	role: string;
	summary: string;
	confirmed: boolean;
	mention_count: number;
	voice_profile: string;
	visual_anchor: string;
	primary_sketch_path: string | null;
}

export interface StoryArcItem {
	id: number;
	arc_key: string;
	title: string;
	ordinal: number;
	summary: string;
	goal: string;
	stakes: string;
	turn: string;
	chapter_start: number | null;
	chapter_end: number | null;
	status: string;
}

export interface ChapterPlanItem {
	id: number;
	chapter_no: number;
	arc_id: number | null;
	title: string;
	intent: string;
	beats: unknown[];
	pov_entity_id: number | null;
	pov_name: string | null;
	setting: string;
	status: string;
	era_label: string;
	time_span: string;
	opening_lens: string;
	emotional_turn: string;
	note: string;
}

export interface SketchItem {
	id: number;
	entity_id: number | null;
	subject: string;
	kind: string;
	prompt: string;
	rel_path: string;
	full_path: string;
	exists_on_disk: boolean;
	width: number;
	height: number;
	bytes: number;
	note: string;
	created_at: string;
}

export interface MangaEpisodeItem {
	id: number;
	title: string;
	chapter_no: number | null;
	mode: string;
	style: string;
	aspect_ratio: string;
	status: string;
	page_count: number;
	done_pages: number;
	actual_pages_in_db: number;
	cover_full_path: string | null;
	note: string;
	updated_at: string;
}

export interface MangaPageItem {
	id: number;
	episode_id: number;
	page_no: number;
	title: string;
	layout_style: string;
	pacing_note: string;
	rel_path: string;
	full_path: string;
	exists_on_disk: boolean;
	width: number;
	height: number;
	byte_size: number;
	status: string;
}

export interface ConceptBlueprintItem {
	filename: string;
	stem: string;
	full_path: string;
	byte_size: number;
	location_slug: string;
	location_title_vi: string;
	planet: string;
	era: string;
	is_canon_15: boolean;
	is_canon_extended: boolean;
	spoiler_locked: boolean;
	spoiler_note: string;
	architectural_note: string;
}

export interface VaultSnapshot {
	summary: VaultSummary;
	entities: StoryEntityItem[];
	arcs: StoryArcItem[];
	chapters: ChapterPlanItem[];
	sketches: SketchItem[];
	manga_episodes: MangaEpisodeItem[];
	concepts: ConceptBlueprintItem[];
}

export interface AssetLibraryRow {
	id: number;
	slug: string;
	category: string;
	file_path: string;
	thumb_path: string;
	poly_count: number;
	byte_size: number;
	tags: string[];
	license_clean: boolean;
}

export interface ClockworkPartMeta {
	id: string;
	name_vi?: string;
	name_en?: string;
	summary_vi?: string;
	summary_en?: string;
	dir?: [number, number, number];
}

export interface MangaPlateCapture {
	id: string;
	label: string;
	beauty_path: string;
	depth_path: string;
	width: number;
	height: number;
	created_at: string;
}

export interface AiMeshEntry {
	file_name: string;
	stem: string;
	glb_path: string;
	size_bytes: number;
	concept_path: string | null;
}

export interface MangaPlateExportResult {
	plate: MangaPlateCapture;
	beauty_plate_path: string;
	depth_map_path: string;
	project: ProjectRecord;
}

export interface ChunkPlacementItem {
	id: string;
	slug: string;
	title: string;
	glb_path: string;
	x: number;
	y: number;
	z: number;
	rot_y_deg: number;
	scale: number;
}

export interface AmbientAudioZone {
	id: string;
	label: string;
	audio_path: string;
	x: number;
	z: number;
	radius: number;
	volume: number;
}

export interface ChunkSpawnPoint {
	id: string;
	label: string;
	x: number;
	y: number;
	z: number;
	yaw_deg?: number;
}

export interface ChunkVnTrigger {
	id: string;
	label: string;
	episode_slug: string;
	local_episode_path?: string | null;
	x: number;
	y: number;
	z: number;
	radius: number;
}

export interface CinemaCameraKeyframe {
	id: string;
	time_sec: number;
	pos: [number, number, number];
	target: [number, number, number];
	fov_deg: number;
	explode_pct: number;
}

export interface CinemaSubtitleCue {
	id: string;
	start_sec: number;
	end_sec: number;
	text_vi: string;
	text_en: string;
}

export interface ChunkStitchReport {
	slug: string;
	chunk_x: number;
	chunk_z: number;
	grid_resolution: number;
	min_height_m: number;
	max_height_m: number;
	max_seam_error_m: number;
	stitched_neighbors: string[];
	heightmap_png_path: string;
	project: ProjectRecord;
}

export interface ChunkPackResult {
	zip_path: string;
	size_bytes: number;
	max_seam_error_m: number;
	stitched_neighbors: string[];
	project: ProjectRecord;
}

export interface VnCameraRig {
	preset: string;
	fov_deg: number;
	pos: [number, number, number];
	target: [number, number, number];
	weather: string;
	exposure: number;
	source_slug: string | null;
}

export interface VnCharacterCast {
	id: string;
	name_vi: string;
	name_en: string;
	voice_vi: string;
	voice_en: string;
	portrait_path: string | null;
	accent_color: string;
}

export interface VnHotspot {
	id: string;
	x_pct: number;
	y_pct: number;
	label_vi: string;
	label_en: string;
	inspect_vi: string;
	inspect_en: string;
	unlock_tip_id: string | null;
}

export interface VnChoiceOption {
	id: string;
	label_vi: string;
	label_en: string;
	target_node_id: string;
	grant_shard_id: string | null;
}

export interface VnDialogueNode {
	id: string;
	speaker_id: string;
	expression: string;
	text_vi: string;
	text_en: string;
	backdrop_path: string | null;
	voice_vi_path: string | null;
	voice_en_path: string | null;
	bgm_override_path: string | null;
	next_node_id: string | null;
	choices: VnChoiceOption[];
	hotspots: VnHotspot[];
	unlock_tip_ids: string[];
	unlock_shard_id: string | null;
}

export interface VnTipEntry {
	id: string;
	term_vi: string;
	term_en: string;
	body_vi: string;
	body_en: string;
}

export interface VnMemoryShard {
	id: string;
	title_vi: string;
	title_en: string;
	echo_vi: string;
	echo_en: string;
	chapter_hint: number | null;
}

export interface VnEpisodeDocument {
	schema_version: string;
	slug: string;
	title_vi: string;
	title_en: string;
	synopsis_vi: string;
	synopsis_en: string;
	entry_node_id: string;
	bgm_path: string | null;
	default_backdrop_path: string | null;
	camera_rig: VnCameraRig;
	cast: VnCharacterCast[];
	nodes: VnDialogueNode[];
	tips: VnTipEntry[];
	memory_shards: VnMemoryShard[];
	archive_asset_map: Record<string, string>;
}

export interface VnLintIssue {
	severity: 'blocker' | 'warning' | string;
	rule_code: string;
	location: string;
	message: string;
}

export interface VnSaveResult {
	episode: VnEpisodeDocument;
	lint_issues: VnLintIssue[];
	project: ProjectRecord;
}

export interface VnPackResult {
	zip_path: string;
	size_bytes: number;
	bundled_files_count: number;
	lint_issues: VnLintIssue[];
	project: ProjectRecord;
}

export interface ProjectManifest {
	schema_version: string;
	slug: string;
	title: string;
	title_en: string;
	kind: 'clockwork' | 'open_world' | 'vn_episode' | 'cinema' | string;
	planet: 'akunalia' | 'earth' | string;
	region_slug: string;
	era: string;
	era_year: number | null;
	lat: number | null;
	lng: number | null;
	biome: string;
	chunk_x: number;
	chunk_z: number;
	world_size: number;
	cowriter_entity_id: number | null;
	cowriter_key: string;
	unlock_chapter: number;
	description_vi: string;
	description_en: string;
	local_image_path: string | null;
	concept_paths: string[];
	bgm_audio_path: string | null;
	audio_paths: string[];
	manga_plates: MangaPlateCapture[];
	clockwork: {
		parts: ClockworkPartMeta[];
		glb_path: string | null;
		intro_video_path: string | null;
		pack_version: string;
		/** C2: ảnh xem trước Blender 1920×1080 cho thẻ Chờ 2D. */
		preview_render_path?: string | null;
		/** P0: bản cơ khí có animation assemble/idle (glb_path vẫn là bản thật). */
		mechanism_glb_path?: string | null;
	};
	chunks: {
		pack_zip_path: string | null;
		heightmap_path: string | null;
		splat_path?: string | null;
		water_level?: number;
		foliage_density?: number;
		grid_resolution?: number;
		heightmap_values?: number[];
		placements?: ChunkPlacementItem[];
		audio_zones?: AmbientAudioZone[];
		pack_version: string;
		spawn_points: ChunkSpawnPoint[];
		vn_triggers: ChunkVnTrigger[];
	};
	stage_vn: {
		episode_zip_path: string | null;
		episode_json_path?: string | null;
		episode_title: string | null;
	};
	cinema: {
		video_path: string | null;
		thumbnail_path: string | null;
		video_type: string;
		episode_number: number | null;
		duration_sec?: number;
		fps?: number;
		vfx_preset?: string;
		vfx_overlay_path?: string | null;
		comfyui_enabled?: boolean;
		comfyui_prompt?: string;
		source_glb_path?: string | null;
		voice_track_path?: string | null;
		bgm_track_path?: string | null;
		mastered_audio_path?: string | null;
		mastered_lufs?: number | null;
		mastered_true_peak_dbtp?: number | null;
		keyframes?: CinemaCameraKeyframe[];
		subtitles?: CinemaSubtitleCue[];
	};
	sync_policy: {
		source_app: string;
		force_draft: boolean;
	};
}

export interface ProjectRecord {
	id: number;
	slug: string;
	title: string;
	kind: string;
	planet: string;
	region_slug: string;
	cowriter_entity_id: number | null;
	chapter_no: number | null;
	folder_path: string;
	manifest_path: string;
	status: string;
	last_synced_at: string | null;
	created_at: string;
	updated_at: string;
	manifest: ProjectManifest;
}

export interface CreateProjectInput {
	slug: string;
	title: string;
	title_en: string;
	kind: string;
	planet: string;
	region_slug: string;
	era: string;
	era_year: number | null;
	lat: number | null;
	lng: number | null;
	biome: string;
	chunk_x: number;
	chunk_z: number;
	cowriter_entity_id: number | null;
	cowriter_key: string;
	unlock_chapter: number | null;
	description_vi: string;
	description_en: string;
	local_image_path: string | null;
	concept_paths: string[];
	bgm_audio_path?: string | null;
	glb_path?: string | null;
}

export interface VramTelemetry {
	gpu_available: boolean;
	gpu_name: string;
	total_mb: number;
	used_mb: number;
	free_mb: number;
	utilization_pct: number;
	temperature_c: number;
	vram_budget_mb: number;
	within_16gb_budget: boolean;
	/** B2: VRAM của riêng cây tiến trình Akunarch (PDH, LUID GPU rời). */
	app_used_mb?: number;
	webview_used_mb?: number;
	worker_used_mb?: number;
	/** Windows & app khác = used_mb - app_used_mb. */
	other_system_mb?: number;
	app_vram_available?: boolean;
}

export interface ToolProbeItem {
	id: string;
	label: string;
	path_or_url: string;
	available: boolean;
	stage_note: string;
}

export interface HardwareStackReport {
	vram: VramTelemetry;
	tools: ToolProbeItem[];
	active_mutex_locked: boolean;
	queued_count: number;
	running_count: number;
}

export interface GpuJobRow {
	id: number;
	project_id: number | null;
	worker_kind: string;
	payload: Record<string, unknown>;
	status: string;
	progress_pct: number;
	vram_peak_mb: number;
	output_path: string;
	error_log: string;
	created_at: string;
	updated_at: string;
}

export interface VramReleaseResult {
	comfyui_reachable: boolean;
	unloaded_models: boolean;
	message: string;
	vram_after: VramTelemetry;
}

export interface QaFinding {
	severity: 'blocker' | 'warning' | 'pass' | string;
	rule_code: string;
	message: string;
}

export interface QaAuditReport {
	slug: string;
	passed: boolean;
	draft_first_enforced: boolean;
	findings: QaFinding[];
	payload_preview: Record<string, unknown>;
}

export interface SelorsonConnectionConfig {
	base_url: string;
	has_token: boolean;
	token_preview: string;
}

export interface SyncLogRow {
	id: number;
	project_id: number | null;
	target_url: string;
	payload_summary: Record<string, unknown>;
	response: Record<string, unknown>;
	created_at: string;
}

export interface StudioBootstrapPayload {
	db_path: string;
	projects_root: string;
	projects: ProjectRecord[];
	asset_library: AssetLibraryRow[];
	hardware: HardwareStackReport;
	selorson_config: SelorsonConnectionConfig;
	sync_logs: SyncLogRow[];
}
