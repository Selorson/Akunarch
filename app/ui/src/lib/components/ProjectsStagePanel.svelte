<script lang="ts">
	import { untrack } from 'svelte';
	import RealPbrStageViewport from './RealPbrStageViewport.svelte';
	import { api, fileToBase64, isTauriRuntime, mediaUrl, openFolderOnDisk } from '$lib/ipc';
	import type {
		AiMeshEntry,
		CreateProjectInput,
		ProjectManifest,
		ProjectRecord,
		StoryEntityItem
	} from '$lib/types';

	interface Props {
		projects: ProjectRecord[];
		selectedSlug: string | null;
		projectsRoot: string;
		entities?: StoryEntityItem[];
		onSelectSlug: (slug: string) => void;
		onCreateProject: (input: CreateProjectInput) => Promise<void>;
		onSaveManifest: (manifest: ProjectManifest, originalSlug?: string) => Promise<void>;
		onProjectMutated: (updated: ProjectRecord, notice?: string) => Promise<void>;
		onRescanDisk: () => Promise<void>;
		onEnqueueGpuForProject: (
			project: ProjectRecord,
			workerKind: string,
			payload: Record<string, unknown>,
			noticeLabel: string
		) => Promise<void>;
		onJumpToSync: (slug: string) => void;
		onNotify: (msg: string, isError?: boolean) => void;
	}

	let {
		projects,
		selectedSlug,
		projectsRoot,
		entities = [],
		onSelectSlug,
		onCreateProject,
		onSaveManifest,
		onProjectMutated,
		onRescanDisk,
		onEnqueueGpuForProject,
		onJumpToSync,
		onNotify
	}: Props = $props();

	let showNewForm = $state(false);
	let showRawJson = $state(false);
	let saving = $state(false);
	let importingAsset = $state(false);
	let dragActive = $state(false);

	// 47 AI Meshes Library Modal
	let showAiMeshModal = $state(false);
	let aiMeshes = $state<AiMeshEntry[]>([]);
	let loadingMeshes = $state(false);
	let meshQuery = $state('');

	// Hidden file inputs for BYOA browser/webview file dialog
	let conceptInputEl = $state<HTMLInputElement | null>(null);
	let glbInputEl = $state<HTMLInputElement | null>(null);
	let audioInputEl = $state<HTMLInputElement | null>(null);

	// Optional direct path import bar
	let externalPathInput = $state('');

	let newSlug = $state('');
	let newTitle = $state('');
	let newTitleEn = $state('');
	let newKind = $state('clockwork');
	let newPlanet = $state('akunalia');
	let newRegion = $state('');
	let newEra = $state('');
	let newUnlockCh = $state(1);
	let newCowriterKey = $state('');
	let newDescVi = $state('');

	let selectedProject = $derived.by(
		() => projects.find((p) => p.slug === selectedSlug) ?? projects[0] ?? null
	);

	let filteredAiMeshes = $derived.by(() => {
		const q = meshQuery.trim().toLowerCase();
		if (!q) return aiMeshes;
		return aiMeshes.filter(
			(m) => m.stem.toLowerCase().includes(q) || m.file_name.toLowerCase().includes(q)
		);
	});

	let draft = $state<ProjectManifest | null>(null);
	let rawJsonText = $state('');
	let rawJsonError = $state('');

	$effect(() => {
		if (selectedProject) {
			const cloned = JSON.parse(JSON.stringify(selectedProject.manifest)) as ProjectManifest;
			draft = cloned;
			rawJsonText = JSON.stringify(cloned, null, 2);
			rawJsonError = '';
		} else {
			draft = null;
			rawJsonText = '';
			rawJsonError = '';
		}
	});

	function inferAssetKindFromName(nameOrPath: string): 'concept' | 'glb' | 'audio' | 'video' | null {
		const lower = nameOrPath.trim().toLowerCase();
		if (/\.(png|jpg|jpeg|webp)$/.test(lower)) return 'concept';
		if (/\.(glb|gltf|spz|ply)$/.test(lower)) return 'glb';
		if (/\.(mp3|wav|ogg|flac|m4a)$/.test(lower)) return 'audio';
		if (/\.(mp4|webm)$/.test(lower)) return 'video';
		return null;
	}

	// Tauri v2 Native OS Drag-and-Drop listener (receives real disk file paths directly!)
	$effect(() => {
		if (!isTauriRuntime()) return;
		let unlisten: (() => void) | null = null;
		let cancelled = false;

		(async () => {
			try {
				const { getCurrentWebview } = await import('@tauri-apps/api/webview');
				const fn = await getCurrentWebview().onDragDropEvent(async (event) => {
					if (event.payload.type === 'enter' || event.payload.type === 'over') {
						dragActive = true;
					} else if (event.payload.type === 'leave') {
						dragActive = false;
					} else if (event.payload.type === 'drop') {
						dragActive = false;
						const proj = untrack(() => selectedProject);
						if (!proj || !event.payload.paths?.length) return;
						await importDiskPathsIntoProject(proj.slug, event.payload.paths);
					}
				});
				if (cancelled) fn();
				else unlisten = fn;
			} catch {
				// HTML5 drag-drop fallback remains active
			}
		})();

		return () => {
			cancelled = true;
			if (unlisten) unlisten();
		};
	});

	async function importDiskPathsIntoProject(slug: string, paths: string[]) {
		importingAsset = true;
		try {
			let latest: ProjectRecord | null = null;
			let importedCount = 0;
			for (const p of paths) {
				const kind = inferAssetKindFromName(p);
				if (!kind) {
					onNotify(`Bỏ qua tệp chưa hỗ trợ định dạng: ${p}`, true);
					continue;
				}
				latest = await api.projectsImportExternalFile(slug, kind, p, true);
				importedCount++;
			}
			if (latest && importedCount > 0) {
				await onProjectMutated(
					latest,
					`Đã nạp ${importedCount} tài nguyên ngoài vào dự án '${slug}'.`
				);
			}
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			importingAsset = false;
		}
	}

	async function handleBrowserFilesPicked(
		files: FileList | null,
		forcedKind?: 'concept' | 'glb' | 'audio' | 'video'
	) {
		if (!files || files.length === 0 || !selectedProject) return;
		importingAsset = true;
		try {
			let latest: ProjectRecord | null = null;
			let count = 0;
			for (const file of Array.from(files)) {
				const kind = forcedKind ?? inferAssetKindFromName(file.name);
				if (!kind) {
					onNotify(`Định dạng '${file.name}' không thuộc concept/glb/audio/video.`, true);
					continue;
				}
				const b64 = await fileToBase64(file);
				latest = await api.projectsUploadAssetBytes(
					selectedProject.slug,
					kind,
					file.name,
					b64,
					true
				);
				count++;
			}
			if (latest && count > 0) {
				await onProjectMutated(
					latest,
					`Đã nhập ${count} tệp vào thư mục dự án '${selectedProject.slug}'.`
				);
			}
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			importingAsset = false;
		}
	}

	function handleHtmlDragOver(ev: DragEvent) {
		ev.preventDefault();
		dragActive = true;
	}

	function handleHtmlDragLeave() {
		dragActive = false;
	}

	async function handleHtmlDrop(ev: DragEvent) {
		ev.preventDefault();
		dragActive = false;
		if (ev.dataTransfer?.files?.length) {
			await handleBrowserFilesPicked(ev.dataTransfer.files);
		}
	}

	async function handleImportByPathSubmit(ev: SubmitEvent) {
		ev.preventDefault();
		if (!selectedProject || !externalPathInput.trim()) return;
		const cleaned = externalPathInput.trim().replace(/^["']|["']$/g, '');
		await importDiskPathsIntoProject(selectedProject.slug, [cleaned]);
		externalPathInput = '';
	}

	async function openAiMeshesPicker() {
		showAiMeshModal = true;
		if (aiMeshes.length > 0) return;
		loadingMeshes = true;
		try {
			aiMeshes = await api.projectsListAiMeshes();
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			loadingMeshes = false;
		}
	}

	async function handlePickAiMesh(mesh: AiMeshEntry) {
		if (!selectedProject) return;
		importingAsset = true;
		try {
			let updated = await api.projectsImportExternalFile(
				selectedProject.slug,
				'glb',
				mesh.glb_path,
				true
			);
			if (mesh.concept_path && !updated.manifest.local_image_path) {
				updated = await api.projectsImportExternalFile(
					selectedProject.slug,
					'concept',
					mesh.concept_path,
					true
				);
			}
			showAiMeshModal = false;
			await onProjectMutated(
				updated,
				`Đã nạp mesh điêu khắc '${mesh.file_name}' vào clockwork\\ của '${selectedProject.slug}'.`
			);
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			importingAsset = false;
		}
	}

	async function handleExportMangaPlates(
		width: number,
		height: number,
		beautyPngDataUrl: string,
		depthPngDataUrl: string,
		label: string
	) {
		if (!selectedProject) return;
		const res = await api.projectsSaveMangaPlates(
			selectedProject.slug,
			width,
			height,
			beautyPngDataUrl,
			depthPngDataUrl,
			label
		);
		await onProjectMutated(
			res.project,
			`Đã lưu Phông Nền Manga 2K (beauty_plate.png + depth_map.png) tại ${res.beauty_plate_path}`
		);
	}

	function toggleJsonMode() {
		if (!showRawJson && draft) {
			rawJsonText = JSON.stringify(draft, null, 2);
			rawJsonError = '';
			showRawJson = true;
		} else {
			try {
				const parsed = JSON.parse(rawJsonText) as ProjectManifest;
				draft = parsed;
				rawJsonError = '';
				showRawJson = false;
			} catch (err) {
				rawJsonError = `JSON không hợp lệ: ${err instanceof Error ? err.message : String(err)}`;
			}
		}
	}

	async function handleCreateSubmit(e: SubmitEvent) {
		e.preventDefault();
		saving = true;
		try {
			const matchedEnt = newCowriterKey
				? entities.find((en) => en.subject_key === newCowriterKey)
				: undefined;
			await onCreateProject({
				slug: newSlug,
				title: newTitle,
				title_en: newTitleEn,
				kind: newKind,
				planet: newPlanet,
				region_slug: newRegion,
				era: newEra,
				era_year: null,
				lat: null,
				lng: null,
				biome: 'temperate',
				chunk_x: 0,
				chunk_z: 0,
				cowriter_entity_id: matchedEnt?.id ?? null,
				cowriter_key: newCowriterKey.trim(),
				unlock_chapter: newUnlockCh,
				description_vi: newDescVi,
				description_en: '',
				local_image_path: null,
				concept_paths: []
			});
			showNewForm = false;
			newSlug = '';
			newTitle = '';
			newTitleEn = '';
			newCowriterKey = '';
			newDescVi = '';
		} finally {
			saving = false;
		}
	}

	async function handleSaveDraft() {
		if (!draft) return;
		if (showRawJson) {
			try {
				const parsed = JSON.parse(rawJsonText) as ProjectManifest;
				draft = parsed;
				rawJsonError = '';
			} catch (err) {
				rawJsonError = `JSON không hợp lệ: ${err instanceof Error ? err.message : String(err)}`;
				return;
			}
		}
		saving = true;
		try {
			await onSaveManifest(draft, selectedProject?.slug);
		} finally {
			saving = false;
		}
	}

	function handleLinkCowriterSelect(ev: Event) {
		if (!draft) return;
		const key = (ev.currentTarget as HTMLSelectElement).value;
		draft.cowriter_key = key;
		const ent = entities.find((e) => e.subject_key === key);
		draft.cowriter_entity_id = ent ? ent.id : null;
	}

	function formatSizeMb(bytes: number): string {
		return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
	}
</script>

<!-- Hidden File Inputs for BYOA Import -->
<input
	bind:this={conceptInputEl}
	type="file"
	accept=".png,.jpg,.jpeg,.webp"
	multiple
	style="display: none;"
	onchange={(e) => {
		handleBrowserFilesPicked((e.currentTarget as HTMLInputElement).files, 'concept');
		(e.currentTarget as HTMLInputElement).value = '';
	}}
/>
<input
	bind:this={glbInputEl}
	type="file"
	accept=".glb,.gltf,.spz,.ply"
	style="display: none;"
	onchange={(e) => {
		handleBrowserFilesPicked((e.currentTarget as HTMLInputElement).files, 'glb');
		(e.currentTarget as HTMLInputElement).value = '';
	}}
/>
<input
	bind:this={audioInputEl}
	type="file"
	accept=".mp3,.wav,.ogg,.flac,.m4a"
	style="display: none;"
	onchange={(e) => {
		handleBrowserFilesPicked((e.currentTarget as HTMLInputElement).files, 'audio');
		(e.currentTarget as HTMLInputElement).value = '';
	}}
/>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="projects-grid-layout {dragActive ? 'drag-over' : ''}"
	ondragover={handleHtmlDragOver}
	ondragleave={handleHtmlDragLeave}
	ondrop={handleHtmlDrop}
>
	{#if dragActive}
		<div class="dropzone-banner">
			<strong>📥 Thả tệp vào đây để nhập thẳng vào dự án "{selectedProject?.title ?? ''}"</strong>
			<span>Hỗ trợ: Ảnh (.png/.jpg/.webp) → concepts\ · Mô hình (.glb/.spz/.ply) → clockwork\ · Nhạc FL Studio (.mp3/.wav/.ogg/.flac) → audio\</span>
		</div>
	{/if}

	<!-- Left Column: Open Projects List + World-First Creator -->
	<div class="projects-sidebar card">
		<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
			<div class="section-label">DỰ ÁN MỞ ({projects.length})</div>
			<div style="display: flex; gap: 5px;">
				<button class="btn btn-sm" title="Quét lại project.akun.json trên ổ cứng" onclick={onRescanDisk}>
					🔄 Vibecode
				</button>
				<button
					class="btn btn-sm btn-brass"
					data-testid="open-new-project-btn"
					onclick={() => (showNewForm = !showNewForm)}
				>
					+ Mới
				</button>
			</div>
		</div>

		<div class="mono" style="font-size: 11px; color: var(--text-muted); margin-bottom: 8px;">
			📂 {projectsRoot}
		</div>

		{#if showNewForm}
			<form class="new-proj-box" onsubmit={handleCreateSubmit}>
				<div class="section-label" style="margin-bottom: 4px;">
					KHỞI TẠO DỰ ÁN ĐỘC LẬP (WORLD-FIRST)
				</div>
				<input
					class="input"
					placeholder="Slug (VD: citadel-of-ash)"
					bind:value={newSlug}
					required
				/>
				<input
					class="input"
					placeholder="Tên Tiếng Việt *"
					bind:value={newTitle}
					required
				/>
				<input class="input" placeholder="Tên Tiếng Anh (EN)" bind:value={newTitleEn} />
				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
					<select class="select" bind:value={newKind}>
						<option value="clockwork">1. Sa bàn (clockwork)</option>
						<option value="open_world">2. Thế giới mở (open_world)</option>
						<option value="vn_episode">3A. Visual Novel (vn_episode)</option>
						<option value="cinema">3B. Điện ảnh (cinema)</option>
					</select>
					<select class="select" bind:value={newPlanet}>
						<option value="akunalia">Akunalia</option>
						<option value="earth">Trái Đất</option>
					</select>
				</div>
				<div style="display: grid; grid-template-columns: 1.4fr 1fr; gap: 6px;">
					<input class="input" placeholder="Kỷ nguyên (VD: 292 TCN)" bind:value={newEra} />
					<input
						class="input"
						type="number"
						min="1"
						placeholder="Ch. mở khóa"
						bind:value={newUnlockCh}
					/>
				</div>
				<input
					class="input mono"
					placeholder="Khóa Co-Writer (để trống nếu xây Thế Giới trước)"
					bind:value={newCowriterKey}
				/>
				<textarea
					class="textarea"
					placeholder="Mô tả địa danh / phân cảnh (chuẩn phương ngữ Nam Bộ)..."
					bind:value={newDescVi}
				></textarea>
				<div style="display: flex; justify-content: flex-end; gap: 6px;">
					<button type="button" class="btn btn-sm" onclick={() => (showNewForm = false)}>Hủy</button>
					<button type="submit" class="btn btn-sm btn-brass" disabled={saving}>
						Tạo dự án độc lập
					</button>
				</div>
			</form>
		{/if}

		<div class="proj-list">
			{#if projects.length === 0}
				<div class="empty-note">
					Chưa có dự án nào trong <code>projects/</code>. Bấm <strong>+ Mới</strong> (không cần <code>cowriter_key</code>) hoặc chọn một Concept trong <strong>Kho Thánh Tích</strong>!
				</div>
			{:else}
				{#each projects as p (p.slug)}
					<button
						class="proj-item {selectedProject?.slug === p.slug ? 'active' : ''}"
						data-testid={`project-card-${p.slug}`}
						onclick={() => onSelectSlug(p.slug)}
					>
						<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 6px;">
							<strong style="line-height: 1.3;">{p.title}</strong>
							<span
								class="badge {p.manifest.clockwork.glb_path
									? 'badge-ok'
									: 'badge-brass'}"
							>
								{p.manifest.clockwork.glb_path ? '.GLB PBR' : 'CONCEPT'}
							</span>
						</div>
						<div class="mono" style="color: var(--text-muted); margin-top: 2px; font-size: 11px;">
							{p.slug}
						</div>
						<div style="display: flex; gap: 5px; margin-top: 5px; flex-wrap: wrap;">
							<span class="badge {p.planet === 'earth' ? 'badge-warn' : 'badge-cyan'}">
								{p.planet === 'earth' ? 'Trái Đất' : 'Akunalia'}
							</span>
							{#if p.manifest.cowriter_key}
								<span class="badge mono" title="Đã nối Co-Writer">{p.manifest.cowriter_key}</span>
							{:else}
								<span class="badge" title="Dự án xây thế giới độc lập">World-First</span>
							{/if}
							{#if p.manifest.bgm_audio_path}
								<span class="badge">🎵 BGM</span>
							{/if}
						</div>
					</button>
				{/each}
			{/if}
		</div>
	</div>

	<!-- Center Column: Real AAA PBR/HDRI Stage + BYOA Quick Hub -->
	<div class="stage-center-col">
		<div style="flex: 1; min-height: 0;">
			<RealPbrStageViewport
				slug={draft?.slug ?? 'unselected-stage'}
				title={draft?.title ?? 'Chọn hoặc tạo dự án để mở Sân khấu PBR'}
				titleEn={draft?.title_en ?? ''}
				planet={draft?.planet ?? 'akunalia'}
				kind={draft?.kind ?? 'clockwork'}
				era={draft?.era ?? ''}
				unlockChapter={draft?.unlock_chapter ?? 1}
				glbPath={draft?.clockwork?.glb_path ?? null}
				partsMeta={draft?.clockwork?.parts ?? []}
				localImagePath={draft?.local_image_path ?? null}
				conceptPaths={draft?.concept_paths ?? []}
				bgmAudioPath={draft?.bgm_audio_path ?? null}
				introVideoPath={draft?.clockwork?.intro_video_path ?? null}
				mangaPlates={draft?.manga_plates ?? []}
				previewRenderPath={draft?.clockwork?.preview_render_path ?? null}
				mechanismGlbPath={draft?.clockwork?.mechanism_glb_path ?? null}
				onSculptFromConcept={(conceptPath) => {
					if (!selectedProject) return;
					onEnqueueGpuForProject(
						selectedProject,
						'hunyuan3d',
						{
							mode: 'sculpt_concept',
							concept_path: conceptPath,
							auto_assemble: true
						},
						'Hunyuan3D-2 fp16 (Đúc .glb từ Concept)'
					);
				}}
				onRequestImportGlb={() => glbInputEl?.click()}
				onRequestPickAiMesh={openAiMeshesPicker}
				onRequestImportConcept={() => conceptInputEl?.click()}
				onRequestImportAudio={() => audioInputEl?.click()}
				onExportMangaPlates={handleExportMangaPlates}
				onOpenSubfolder={(sub) => {
					if (selectedProject) api.projectsOpenFolder(selectedProject.slug, sub);
				}}
			/>
		</div>

		<!-- Bring-Your-Own-Assets (BYOA) & Direct GPU Forge Bar -->
		<div class="byoa-hub-strip card">
			<div class="byoa-top-row">
				<div>
					<span class="section-label">CỔNG KÉO-THẢ TÀI NGUYÊN NGOÀI (BYOA) &amp; ĐÚC GPU TRỰC TIẾP</span>
				</div>
				<div class="byoa-btn-row">
					<button
						class="btn btn-sm"
						disabled={!selectedProject || importingAsset}
						onclick={() => conceptInputEl?.click()}
						title="Nhập ảnh .png/.jpg/.webp từ máy vào projects/<slug>/concepts/"
					>
						🖼️ +Ảnh Concept
					</button>
					<button
						class="btn btn-sm btn-cyan"
						disabled={!selectedProject || importingAsset}
						onclick={() => glbInputEl?.click()}
						title="Nhập file .glb/.spz/.ply bên ngoài vào projects/<slug>/clockwork/"
					>
						🏛️ +Nhập .GLB Ngoài
					</button>
					<button
						class="btn btn-sm btn-brass"
						data-testid="open-aimeshes-modal-btn"
						disabled={!selectedProject || importingAsset}
						onclick={openAiMeshesPicker}
						title="Chọn nhanh từ 47 mesh điêu khắc có sẵn tại E:\Tools-3D\ai_meshes\"
					>
						🗿 Kho 47 Mesh Điêu Khắc
					</button>
					<button
						class="btn btn-sm"
						disabled={!selectedProject || importingAsset}
						onclick={() => audioInputEl?.click()}
						title="Nhập nhạc nền .mp3/.wav/.ogg/.flac xuất từ FL Studio vào projects/<slug>/audio/"
					>
						🎵 +Nhạc BGM (FL Studio)
					</button>
					{#if selectedProject}
						<button
							class="btn btn-sm"
							onclick={() =>
								onEnqueueGpuForProject(
									selectedProject,
									'blender',
									{ mode: 'assemble_glb' },
									'Blender 5.2 Cycles OptiX AO + Draco .glb'
								)}
							title="Lắp đế cơ khí, nướng Cycles OptiX AO và xuất chuẩn Draco .glb"
						>
							⚙️ Blender Nướng AO
						</button>
						<button
							class="btn btn-sm"
							onclick={() =>
								onEnqueueGpuForProject(
									selectedProject,
									'blender',
									{ mode: 'render_intro_mp4', frames: 36 },
									'Blender 5.2 + FFmpeg Render Intro .mp4'
								)}
							title="Kết xuất phim Intro xoay sa bàn .mp4 qua Blender 5.2 & FFmpeg"
						>
							🎬 Render Intro .mp4
						</button>
					{/if}
				</div>
			</div>

			<form class="byoa-path-form" onsubmit={handleImportByPathSubmit}>
				<input
					class="input mono"
					style="padding: 5px 9px; font-size: 11.5px;"
					placeholder="Hoặc dán đường dẫn tệp trên máy (VD: D:\FLStudio\theme.flac, E:\Models\citadel.glb, C:\Art\sketch.png) rồi Enter..."
					bind:value={externalPathInput}
				/>
				<button
					type="submit"
					class="btn btn-sm"
					disabled={!selectedProject || !externalPathInput.trim() || importingAsset}
				>
					📥 Chép vào Dự Án
				</button>
			</form>
		</div>
	</div>

	<!-- Right Column: Vibecode-Ready project.akun.json Inspector -->
	<div class="manifest-inspector card">
		{#if draft && selectedProject}
			<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
				<div>
					<div class="section-label">VIBECODE MANIFEST INSPECTOR</div>
					<div class="mono" style="color: var(--text-muted); font-size: 11px;">
						project.akun.json · v{draft.schema_version || '2.0'}
					</div>
				</div>
				<div style="display: flex; gap: 6px;">
					<button class="btn btn-sm" onclick={toggleJsonMode}>
						{showRawJson ? '📝 Biểu mẫu' : '{ } JSON'}
					</button>
					<button
						class="btn btn-sm"
						onclick={() => openFolderOnDisk(selectedProject.folder_path)}
					>
						📂 Mở thư mục
					</button>
				</div>
			</div>

			{#if showRawJson}
				{#if rawJsonError}
					<div class="badge badge-err" style="margin-bottom: 6px; white-space: normal;">
						{rawJsonError}
					</div>
				{/if}
				<textarea
					class="raw-json-box mono"
					spellcheck="false"
					aria-label="Vibecode project.akun.json editor"
					bind:value={rawJsonText}
				></textarea>
			{:else}
				<div class="inspector-scroll">
					{#if draft.local_image_path}
						<img
							src={mediaUrl(draft.local_image_path)}
							alt={draft.title}
							class="preview-banner"
						/>
					{/if}

					<label class="field-lbl">
						<span>Tên dự án (Tiếng Việt)</span>
						<input class="input" bind:value={draft.title} />
					</label>
					<label class="field-lbl">
						<span>Tên bản dịch Tiếng Anh (EN)</span>
						<input class="input" bind:value={draft.title_en} placeholder="English Title..." />
					</label>

					<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
						<label class="field-lbl">
							<span>Phân xưởng (kind)</span>
							<select class="select" bind:value={draft.kind}>
								<option value="clockwork">clockwork (Sa bàn)</option>
								<option value="open_world">open_world (Chunk)</option>
								<option value="vn_episode">vn_episode (VN)</option>
								<option value="cinema">cinema (Phim .mp4)</option>
							</select>
						</label>
						<label class="field-lbl">
							<span>Hành tinh</span>
							<select class="select" bind:value={draft.planet}>
								<option value="akunalia">akunalia</option>
								<option value="earth">earth</option>
							</select>
						</label>
					</div>

					<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
						<label class="field-lbl">
							<span>Vùng (region_slug)</span>
							<input class="input" bind:value={draft.region_slug} placeholder="eldarin-highlands" />
						</label>
						<label class="field-lbl">
							<span>Kỷ nguyên (era)</span>
							<input class="input" bind:value={draft.era} placeholder="292 TCN" />
						</label>
					</div>

					{#if draft.kind === 'open_world'}
						<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
							<label class="field-lbl">
								<span>Chunk X</span>
								<input class="input tabular" type="number" bind:value={draft.chunk_x} />
							</label>
							<label class="field-lbl">
								<span>Chunk Z</span>
								<input class="input tabular" type="number" bind:value={draft.chunk_z} />
							</label>
							<label class="field-lbl">
								<span>Biome</span>
								<input class="input" bind:value={draft.biome} />
							</label>
							<label class="field-lbl">
								<span>Ch. mở khóa</span>
								<input
									class="input tabular"
									type="number"
									min="1"
									bind:value={draft.unlock_chapter}
								/>
							</label>
						</div>
					{:else}
						<div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;">
							<label class="field-lbl">
								<span>Vĩ độ (lat)</span>
								<input class="input tabular" type="number" step="0.01" bind:value={draft.lat} />
							</label>
							<label class="field-lbl">
								<span>Kinh độ (lng)</span>
								<input class="input tabular" type="number" step="0.01" bind:value={draft.lng} />
							</label>
							<label class="field-lbl">
								<span>Ch. mở khóa</span>
								<input
									class="input tabular"
									type="number"
									min="1"
									bind:value={draft.unlock_chapter}
								/>
							</label>
						</div>
					{/if}

					<div class="field-lbl">
						<span>Liên kết Co-Writer (tùy chọn · có thể nối sau bất kỳ lúc nào)</span>
						<input
							class="input mono"
							placeholder="Để trống nếu chạy độc lập World-First"
							bind:value={draft.cowriter_key}
						/>
						{#if entities.length > 0}
							<select
								class="select"
								style="margin-top: 3px; font-size: 11.5px;"
								value={draft.cowriter_key}
								onchange={handleLinkCowriterSelect}
							>
								<option value="">-- Chạy độc lập (Chưa gắn thực thể Co-Writer) --</option>
								{#each entities as ent (ent.id)}
									<option value={ent.subject_key}>
										[{ent.kind}] {ent.name} ({ent.subject_key})
									</option>
								{/each}
							</select>
						{/if}
					</div>

					<label class="field-lbl">
						<span>Mô hình PBR (.glb) gắn trên sân khấu</span>
						<input
							class="input mono"
							placeholder="Chưa có .glb · dùng Bàn phóng Concept hoặc Kho 47 Mesh"
							bind:value={draft.clockwork.glb_path}
						/>
					</label>

					<label class="field-lbl">
						<span>Nhạc nền dự án (bgm_audio_path)</span>
						<input
							class="input mono"
							placeholder="projects\<slug>\audio\theme.flac"
							bind:value={draft.bgm_audio_path}
						/>
					</label>

					<label class="field-lbl">
						<span>Mô tả Tiếng Việt (Chuẩn phương ngữ Nam Bộ · Rule #36)</span>
						<textarea class="textarea" bind:value={draft.description_vi}></textarea>
					</label>

					<label class="field-lbl">
						<span>Mô tả Tiếng Anh (Literary Epic Fantasy · EN)</span>
						<textarea class="textarea" bind:value={draft.description_en}></textarea>
					</label>

					<div class="subfolders-pill-box">
						<div class="section-label" style="margin-bottom: 5px;">
							8 THƯ MỤC CHUẨN TRÊN Ổ CỨNG (BẤM ĐỂ MỞ)
						</div>
						<div style="display: flex; flex-wrap: wrap; gap: 5px;">
							{#each ['concepts', 'clockwork', 'audio', 'manga_plates', 'chunks', 'stage_vn', 'cinema', 'dist'] as sub (sub)}
								<button
									type="button"
									class="badge mono sub-pill-btn"
									onclick={() => api.projectsOpenFolder(selectedProject.slug, sub)}
								>
									{sub}\
								</button>
							{/each}
						</div>
					</div>
				</div>
			{/if}

			<div class="inspector-actions">
				<button class="btn btn-brass" onclick={handleSaveDraft} disabled={saving}>
					{saving ? '⏳ Đang lưu...' : '💾 Lưu project.akun.json'}
				</button>
				<button class="btn btn-cyan" onclick={() => onJumpToSync(selectedProject.slug)}>
					🚀 Kiểm định &amp; Đồng bộ →
				</button>
			</div>
		{:else}
			<div class="empty-note" style="margin: auto;">
				Chọn hoặc khởi tạo một dự án để chỉnh sửa cấu hình <code>project.akun.json</code> và soi trên sân khấu 3D PBR.
			</div>
		{/if}
	</div>
</div>

<!-- 47 Sculpted AI Meshes Quick-Picker Modal (`E:\Tools-3D\ai_meshes\`) -->
{#if showAiMeshModal}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="modal-backdrop" onclick={() => (showAiMeshModal = false)}>
		<div
			class="aimesh-modal card"
			data-testid="aimeshes-picker-modal"
			onclick={(e) => e.stopPropagation()}
		>
			<div style="display: flex; justify-content: space-between; align-items: center; gap: 12px;">
				<div>
					<div class="section-label">KHO MESH ĐIÊU KHẮC CÓ SẴN · E:\Tools-3D\ai_meshes\</div>
					<h3 style="margin: 3px 0 0; font-size: 16px;">
						Chọn nhanh từ {aiMeshes.length} Mesh Điêu Khắc Hunyuan3D-2 nạp vào "{selectedProject?.slug}"
					</h3>
				</div>
				<button class="btn btn-sm" onclick={() => (showAiMeshModal = false)}>✕ Đóng</button>
			</div>

			<input
				class="input"
				placeholder="🔍 Lọc nhanh theo tên mesh (VD: sealing_stone, golden_dome, avalon, olympus, skiff...)"
				bind:value={meshQuery}
			/>

			<div class="aimesh-grid">
				{#if loadingMeshes}
					<div class="empty-note">Đang quét kho E:\Tools-3D\ai_meshes\...</div>
				{:else if filteredAiMeshes.length === 0}
					<div class="empty-note">Không tìm thấy mesh nào khớp từ khóa "{meshQuery}".</div>
				{:else}
					{#each filteredAiMeshes as m (m.file_name)}
						<div class="aimesh-card">
							{#if m.concept_path}
								<img src={mediaUrl(m.concept_path)} alt={m.stem} class="aimesh-thumb" />
							{:else}
								<div class="aimesh-thumb aimesh-no-thumb mono">GLB MESH</div>
							{/if}
							<div class="aimesh-info">
								<strong class="mono" style="font-size: 11.5px; word-break: break-all;">
									{m.file_name}
								</strong>
								<span class="mono tabular" style="font-size: 10.5px; color: var(--text-muted);">
									{formatSizeMb(m.size_bytes)}
								</span>
							</div>
							<button
								class="btn btn-sm btn-brass"
								disabled={importingAsset}
								onclick={() => handlePickAiMesh(m)}
							>
								📥 Nạp vào clockwork\
							</button>
						</div>
					{/each}
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.projects-grid-layout {
		position: relative;
		display: grid;
		grid-template-columns: 295px 1fr 352px;
		gap: 12px;
		height: 100%;
		min-height: 0;
	}
	.projects-grid-layout.drag-over {
		outline: 2px dashed var(--brass-bright);
		outline-offset: -4px;
	}
	.dropzone-banner {
		position: absolute;
		inset: 14px;
		z-index: 60;
		background: rgba(12, 17, 28, 0.92);
		border: 2px dashed var(--brass-bright);
		border-radius: var(--radius-md);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 8px;
		pointer-events: none;
		text-align: center;
		padding: 24px;
	}
	.dropzone-banner strong {
		font-size: 16px;
		color: var(--brass-bright);
	}
	.dropzone-banner span {
		color: var(--text-secondary);
		font-size: 12.5px;
	}
	.projects-sidebar,
	.manifest-inspector {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}
	.stage-center-col {
		display: flex;
		flex-direction: column;
		gap: 9px;
		height: 100%;
		min-height: 0;
	}
	.new-proj-box {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 10px;
		margin-bottom: 10px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line-strong);
	}
	.proj-list {
		flex: 1;
		overflow: auto;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.proj-item {
		padding: 9px 10px;
		border-radius: var(--radius-sm);
		border: 1px solid rgba(255, 255, 255, 0.07);
		background: var(--obs-base);
		cursor: pointer;
		text-align: left;
	}
	.proj-item:hover,
	.proj-item.active {
		border-color: var(--brass-bright);
		background: rgba(212, 168, 83, 0.11);
	}
	.byoa-hub-strip {
		padding: 8px 11px;
		display: flex;
		flex-direction: column;
		gap: 6px;
		flex-shrink: 0;
	}
	.byoa-top-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	.byoa-btn-row {
		display: flex;
		gap: 5px;
		flex-wrap: wrap;
	}
	.byoa-path-form {
		display: flex;
		gap: 6px;
	}
	.byoa-path-form input {
		flex: 1;
	}
	.inspector-scroll {
		flex: 1;
		overflow: auto;
		display: flex;
		flex-direction: column;
		gap: 9px;
		padding-right: 4px;
	}
	.field-lbl {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 12px;
		color: var(--text-secondary);
	}
	.preview-banner {
		width: 100%;
		height: 116px;
		object-fit: cover;
		border-radius: 6px;
		border: 1px solid var(--brass-line);
	}
	.subfolders-pill-box {
		padding: 9px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px dashed var(--brass-line);
	}
	.sub-pill-btn {
		cursor: pointer;
		border: 1px solid rgba(212, 168, 83, 0.25);
	}
	.sub-pill-btn:hover {
		border-color: var(--brass-bright);
		color: var(--brass-bright);
	}
	.inspector-actions {
		display: flex;
		gap: 8px;
		padding-top: 10px;
		margin-top: 8px;
		border-top: 1px solid var(--brass-line);
	}
	.inspector-actions > button {
		flex: 1;
	}
	.raw-json-box {
		flex: 1;
		width: 100%;
		resize: none;
		overflow: auto;
		margin: 0;
		padding: 10px;
		font-size: 11.5px;
		line-height: 1.45;
		background: #080a10;
		border-radius: var(--radius-sm);
		border: 1px solid var(--brass-line);
		color: #99e9f2;
		outline: none;
	}
	.raw-json-box:focus {
		border-color: var(--brass-bright);
	}
	.empty-note {
		color: var(--text-muted);
		text-align: center;
		padding: 20px;
		font-size: 12.5px;
	}

	/* 47 AI Meshes Picker Modal */
	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 150;
		background: rgba(5, 7, 12, 0.82);
		backdrop-filter: blur(5px);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 24px;
	}
	.aimesh-modal {
		width: min(980px, 95vw);
		max-height: 84vh;
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 16px;
		overflow: hidden;
	}
	.aimesh-grid {
		flex: 1;
		overflow-y: auto;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(205px, 1fr));
		gap: 10px;
		padding-right: 4px;
	}
	.aimesh-card {
		display: flex;
		flex-direction: column;
		gap: 7px;
		padding: 8px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
	}
	.aimesh-thumb {
		width: 100%;
		height: 108px;
		object-fit: cover;
		border-radius: 5px;
		background: #090d16;
	}
	.aimesh-no-thumb {
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-muted);
		font-size: 11px;
		border: 1px dashed rgba(255, 255, 255, 0.1);
	}
	.aimesh-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: 1;
	}
</style>
