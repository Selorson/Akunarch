<script lang="ts">
	import { untrack } from 'svelte';
	import { api, fileToBase64, mediaUrl } from '$lib/ipc';
	import type {
		CinemaCameraKeyframe,
		CinemaSubtitleCue,
		CreateProjectInput,
		ProjectManifest,
		ProjectRecord
	} from '$lib/types';

	interface Props {
		projects: ProjectRecord[];
		selectedSlug: string | null;
		onSelectSlug: (slug: string) => void;
		onCreateProject: (input: CreateProjectInput) => Promise<void>;
		onSaveManifest: (manifest: ProjectManifest, originalSlug?: string) => Promise<void>;
		onProjectMutated: (updated: ProjectRecord, notice?: string) => Promise<void>;
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
		onSelectSlug,
		onCreateProject,
		onSaveManifest,
		onProjectMutated,
		onEnqueueGpuForProject,
		onJumpToSync,
		onNotify
	}: Props = $props();

	let cinemaProjects = $derived.by(() => projects.filter((p) => p.manifest.kind === 'cinema'));
	let glbCatalogProjects = $derived.by(() =>
		projects.filter((p) => Boolean(p.manifest.clockwork.glb_path))
	);

	let activeCinema = $derived.by(() => {
		const exact = cinemaProjects.find((p) => p.slug === selectedSlug);
		return exact ?? cinemaProjects[0] ?? null;
	});

	let draft = $state<ProjectManifest | null>(null);
	let showCreateCinema = $state(false);
	let newCinSlug = $state('cinema-zyberon-awakening');
	let newCinTitleVi = $state('Khúc Thức Giấc Thánh Điện Zyberon');
	let newCinTitleEn = $state('Awakening of the Zyberon Temple');
	let newCinSourceGlbSlug = $state('temple-of-zyberon');

	// Video player & live subtitle preview state
	let videoEl = $state<HTMLVideoElement | null>(null);
	let playheadSec = $state(0);
	let subLang = $state<'vi' | 'en' | 'both'>('both');
	let renderMood = $state<'golden_hour' | 'arcane_night' | 'studio'>('golden_hour');
	let busyOp = $state(false);

	// Hidden BYOA inputs
	let voiceInputEl = $state<HTMLInputElement | null>(null);
	let bgmInputEl = $state<HTMLInputElement | null>(null);
	let mp4InputEl = $state<HTMLInputElement | null>(null);

	$effect(() => {
		const cur = activeCinema;
		untrack(() => {
			if (!cur) {
				draft = null;
				return;
			}
			const cloned = JSON.parse(JSON.stringify(cur.manifest)) as ProjectManifest;
			cloned.cinema.duration_sec ??= 6.0;
			cloned.cinema.fps ??= 24;
			cloned.cinema.vfx_preset ??= 'rune_sparks';
			cloned.cinema.comfyui_enabled ??= false;
			cloned.cinema.comfyui_prompt ??= '';
			if (!cloned.cinema.keyframes || cloned.cinema.keyframes.length === 0) {
				cloned.cinema.keyframes = [
					{
						id: 'kf_01',
						time_sec: 0.0,
						pos: [-12.0, 5.2, 16.5],
						target: [0.0, 2.8, 0.0],
						fov_deg: 40.0,
						explode_pct: 0
					},
					{
						id: 'kf_02',
						time_sec: 3.0,
						pos: [2.5, 7.6, 13.8],
						target: [0.0, 3.6, 0.0],
						fov_deg: 37.0,
						explode_pct: 0
					},
					{
						id: 'kf_03',
						time_sec: cloned.cinema.duration_sec ?? 6.0,
						pos: [11.5, 9.4, 12.2],
						target: [0.0, 4.2, 0.0],
						fov_deg: 35.0,
						explode_pct: 0
					}
				];
			} else {
				cloned.cinema.keyframes = cloned.cinema.keyframes.map((kf, idx) => ({
					...kf,
					id: kf.id && kf.id.trim() ? kf.id : `kf_${idx + 1}`
				}));
			}
			if (!cloned.cinema.subtitles || cloned.cinema.subtitles.length === 0) {
				cloned.cinema.subtitles = [
					{
						id: 'sub_01',
						start_sec: 0.2,
						end_sec: 3.0,
						text_vi: ' Dưới tầng sương sớm lòng chảo, năm vành đồng cổ bắt đầu chuyển nhịp.',
						text_en: 'Beneath the basin morning mist, the five ancient bronze rings begin to turn.'
					},
					{
						id: 'sub_02',
						start_sec: 3.1,
						end_sec: cloned.cinema.duration_sec ?? 6.0,
						text_vi: 'Ánh nắng đầu ngày rọi xuyên mái vòm xanh ngọc, đánh thức tòa thánh tích ngàn năm.',
						text_en: 'First daylight pierces the emerald dome, awakening the millennial sanctuary.'
					}
				];
			}
			draft = cloned;
		});
	});

	let activeSubtitleCue = $derived.by(() => {
		if (!draft?.cinema.subtitles) return null;
		return (
			draft.cinema.subtitles.find(
				(c) => playheadSec >= c.start_sec && playheadSec <= c.end_sec
			) ?? null
		);
	});

	async function saveCinemaDraft() {
		if (!activeCinema || !draft) return;
		await onSaveManifest(draft, activeCinema.slug);
	}

	async function handleRunFullCinemaPipeline() {
		if (!activeCinema || !draft) return;
		await onSaveManifest(draft, activeCinema.slug);
		await onEnqueueGpuForProject(
			activeCinema,
			'filmcraft',
			{
				mode: 'cinema_render_pipeline',
				project_slug: activeCinema.slug,
				duration_sec: draft.cinema.duration_sec ?? 6.0,
				fps: draft.cinema.fps ?? 24,
				width: 1280,
				height: 720,
				mood: renderMood,
				comfyui_enabled: Boolean(draft.cinema.comfyui_enabled)
			},
			`Dựng phim tuần tự 5 bước (Cycles OptiX → EffectCraft → ToneForge -14 LUFS → H.264 .MP4)`
		);
	}

	async function handleRunVfxOverlayOnly() {
		if (!activeCinema || !draft) return;
		await onSaveManifest(draft, activeCinema.slug);
		await onEnqueueGpuForProject(
			activeCinema,
			'effectcraft',
			{
				mode: 'effectcraft_overlay',
				project_slug: activeCinema.slug,
				time_sec: 1.25
			},
			'Kết xuất lớp phủ VFX RGBA (effectcraft-cli)'
		);
	}

	async function handleRunToneForgeMasterOnly() {
		if (!activeCinema || !draft) return;
		await onSaveManifest(draft, activeCinema.slug);
		await onEnqueueGpuForProject(
			activeCinema,
			'toneforge',
			{
				mode: 'toneforge_master',
				project_slug: activeCinema.slug,
				duration_sec: draft.cinema.duration_sec ?? 6.0
			},
			'Mastering âm thanh chuẩn -14.0 LUFS / -1.0 dBTP (akunarch-audio-cli)'
		);
	}

	function addKeyframe() {
		if (!draft) return;
		const kfs = draft.cinema.keyframes ?? [];
		const dur = draft.cinema.duration_sec ?? 6.0;
		const nextKf: CinemaCameraKeyframe = {
			id: `kf_${Date.now()}`,
			time_sec: Math.round(dur * 0.5 * 10) / 10,
			pos: [0.0, 6.5, 14.5],
			target: [0.0, 3.2, 0.0],
			fov_deg: 38.0,
			explode_pct: 0
		};
		draft.cinema.keyframes = [...kfs, nextKf].sort((a, b) => a.time_sec - b.time_sec);
	}

	function addSubtitleCue() {
		if (!draft) return;
		const subs = draft.cinema.subtitles ?? [];
		const lastEnd = subs.length > 0 ? subs[subs.length - 1].end_sec : 0;
		const cue: CinemaSubtitleCue = {
			id: `sub_${Date.now()}`,
			start_sec: Math.round(lastEnd * 10) / 10,
			end_sec: Math.round((lastEnd + 2.5) * 10) / 10,
			text_vi: 'Tiếng gió vọng qua hành lang đá cổ phương Nam.',
			text_en: 'Wind echoes along the ancient southern stone gallery.'
		};
		draft.cinema.subtitles = [...subs, cue];
	}

	async function handleUploadCinemaAsset(
		files: FileList | null,
		role: 'voice' | 'bgm' | 'video'
	) {
		if (!activeCinema || !draft || !files || files.length === 0) return;
		busyOp = true;
		try {
			const file = files[0];
			const b64 = await fileToBase64(file);
			const kind = role === 'video' ? 'video' : role === 'voice' ? 'voice' : 'audio';
			const updated = await api.projectsUploadAssetBytes(
				activeCinema.slug,
				kind,
				file.name,
				b64,
				role !== 'voice'
			);
			const newestAudio = updated.manifest.audio_paths[updated.manifest.audio_paths.length - 1];
			if (role === 'voice' && newestAudio) {
				draft.cinema.voice_track_path = newestAudio;
				await onSaveManifest(draft, activeCinema.slug);
			} else if (role === 'bgm' && newestAudio) {
				draft.cinema.bgm_track_path = newestAudio;
				await onSaveManifest(draft, activeCinema.slug);
			} else {
				await onProjectMutated(updated, `Đã nạp '${file.name}' vào dự án Điện ảnh.`);
			}
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			busyOp = false;
		}
	}

	async function handleCreateNewCinema() {
		const srcProj = glbCatalogProjects.find((p) => p.slug === newCinSourceGlbSlug);
		await onCreateProject({
			slug: newCinSlug,
			title: newCinTitleVi,
			title_en: newCinTitleEn,
			kind: 'cinema',
			planet: srcProj?.manifest.planet ?? 'akunalia',
			region_slug: srcProj?.manifest.region_slug ?? 'zyberon-basin',
			era: srcProj?.manifest.era ?? 'Kỷ Nguyên Thứ Tư',
			era_year: null,
			lat: null,
			lng: null,
			biome: 'temperate',
			chunk_x: 0,
			chunk_z: 0,
			cowriter_entity_id: null,
			cowriter_key: '',
			unlock_chapter: 1,
			description_vi: 'Phim điện ảnh 3D kết xuất tuần tự kèm VFX cổ ngữ và âm thanh chuẩn -14 LUFS.',
			description_en: 'Sequential 3D cinematic sequence with VFX rune overlay and -14 LUFS mastered audio.',
			local_image_path: srcProj?.manifest.local_image_path ?? null,
			concept_paths: [],
			glb_path: srcProj?.manifest.clockwork.glb_path ?? null
		});
		showCreateCinema = false;
	}
</script>

<input
	bind:this={voiceInputEl}
	type="file"
	accept=".wav,.mp3,.ogg,.flac"
	style="display:none"
	onchange={(e) => handleUploadCinemaAsset((e.currentTarget as HTMLInputElement).files, 'voice')}
/>
<input
	bind:this={bgmInputEl}
	type="file"
	accept=".wav,.mp3,.ogg,.flac"
	style="display:none"
	onchange={(e) => handleUploadCinemaAsset((e.currentTarget as HTMLInputElement).files, 'bgm')}
/>
<input
	bind:this={mp4InputEl}
	type="file"
	accept=".mp4,.webm"
	style="display:none"
	onchange={(e) => handleUploadCinemaAsset((e.currentTarget as HTMLInputElement).files, 'video')}
/>

<div class="cinema-workbench" data-testid="cinema-vfx-workbench">
	<!-- Left Column: Cinema Projects & Sequential Pipeline Controls -->
	<aside class="cin-left card">
		<div class="row-between">
			<div>
				<div class="section-label">CHẶNG 5 · CINEMA &amp; VFX</div>
				<h3 style="margin:2px 0 0; font-size:15px;">Phim Ngắn &amp; Mastering</h3>
			</div>
			<button class="btn btn-sm btn-brass" onclick={() => (showCreateCinema = !showCreateCinema)}>
				+ Phim Mới
			</button>
		</div>

		{#if showCreateCinema}
			<div class="sub-box">
				<label class="field-lbl">
					<span>Slug phim</span>
					<input class="input" bind:value={newCinSlug} />
				</label>
				<label class="field-lbl" style="margin-top:5px;">
					<span>Tựa phim (VI)</span>
					<input class="input" bind:value={newCinTitleVi} />
				</label>
				<label class="field-lbl" style="margin-top:5px;">
					<span>Title (EN)</span>
					<input class="input" bind:value={newCinTitleEn} />
				</label>
				<label class="field-lbl" style="margin-top:5px;">
					<span>Kỳ quan .GLB làm bối cảnh</span>
					<select class="select" bind:value={newCinSourceGlbSlug}>
						{#each glbCatalogProjects as gp (gp.slug)}
							<option value={gp.slug}>{gp.title}</option>
						{/each}
					</select>
				</label>
				<button class="btn btn-sm btn-brass" style="width:100%; margin-top:8px;" onclick={handleCreateNewCinema}>
					Tạo Dự Án Phim
				</button>
			</div>
		{/if}

		<div class="cin-list">
			{#each cinemaProjects as cp (cp.slug)}
				<button
					class="cin-item {activeCinema?.slug === cp.slug ? 'active' : ''}"
					onclick={() => onSelectSlug(cp.slug)}
				>
					<div class="row-between">
						<span class="badge {cp.manifest.cinema.video_path ? 'badge-ok' : 'badge-brass'}">
							{cp.manifest.cinema.video_path ? 'MP4 Sẵn sàng' : 'Chờ Render'}
						</span>
						{#if cp.manifest.cinema.mastered_lufs != null}
							<span class="mono" style="font-size:10.5px; color:#8ce99a">
								{cp.manifest.cinema.mastered_lufs.toFixed(1)} LUFS
							</span>
						{/if}
					</div>
					<strong style="display:block; margin-top:4px; font-size:12.5px;">{cp.title}</strong>
					<small style="color:var(--text-muted)">
						{cp.manifest.cinema.duration_sec ?? 6}s · {cp.manifest.cinema.fps ?? 24} fps · {cp.manifest.cinema.video_type}
					</small>
				</button>
			{/each}
		</div>

		{#if activeCinema && draft}
			<div class="sub-box" style="margin-top:auto;">
				<div class="section-label">DÂY CHUYỀN GPU TUẦN TỰ 16GB</div>
				<div style="font-size:11px; color:var(--text-secondary); line-height:1.55; margin:4px 0 8px;">
					1. Blender Cycles OptiX (Beauty + Depth)<br />
					2. ComfyUI (Tùy chọn + tự gọi <code>/free</code>)<br />
					3. <code>effectcraft-cli</code> VFX Cổ ngữ RGBA<br />
					4. <code>akunarch-audio-cli</code> (-14.0 LUFS)<br />
					5. FFmpeg H.264 + <code>filmcraft-cli probe</code>
				</div>
				<button
					class="btn btn-brass"
					style="width:100%;"
					onclick={handleRunFullCinemaPipeline}
					disabled={busyOp}
				>
					🎬 Render Trọn Gói .MP4 (-14 LUFS)
				</button>
				<div class="grid-2" style="margin-top:6px;">
					<button class="btn btn-sm" onclick={saveCinemaDraft}>💾 Lưu Timeline</button>
					<button class="btn btn-sm btn-cyan" onclick={() => onJumpToSync(activeCinema.slug)}>
						🚀 Đẩy Selorson
					</button>
				</div>
			</div>
		{/if}
	</aside>

	<!-- Center: Video Stage Monitor + Multi-Track Timeline -->
	<section class="cin-center card">
		{#if activeCinema && draft}
			<div class="row-between">
				<div>
					<span class="badge badge-cyan">{draft.cinema.video_type}</span>
					<strong style="margin-left:6px; font-size:15px;">{draft.title}</strong>
				</div>
				<div style="display:flex; gap:6px; align-items:center;">
					{#if draft.cinema.mastered_lufs != null}
						<span class="badge badge-ok tabular">
							🔊 ToneForge: {draft.cinema.mastered_lufs.toFixed(1)} LUFS · Peak {(draft.cinema.mastered_true_peak_dbtp ?? -1.2).toFixed(2)} dBTP
						</span>
					{/if}
					<select class="select" style="width:auto;" bind:value={subLang}>
						<option value="both">Phụ đề Song Ngữ VI+EN</option>
						<option value="vi">Chỉ Tiếng Việt</option>
						<option value="en">English Only</option>
					</select>
				</div>
			</div>

			<!-- Cinema Monitor -->
			<div class="monitor-wrap">
				{#if draft.cinema.video_path}
					<!-- svelte-ignore a11y_media_has_caption -->
					<video
						bind:this={videoEl}
						class="monitor-video"
						src={mediaUrl(draft.cinema.video_path)}
						poster={draft.cinema.thumbnail_path ? mediaUrl(draft.cinema.thumbnail_path) : undefined}
						controls
						loop
						ontimeupdate={() => {
							if (videoEl) playheadSec = videoEl.currentTime;
						}}
					></video>
				{:else if draft.cinema.thumbnail_path || draft.local_image_path}
					<img
						class="monitor-poster"
						src={mediaUrl(draft.cinema.thumbnail_path || draft.local_image_path)}
						alt={draft.title}
					/>
					<div class="monitor-badge-center">
						Bấm <strong>🎬 Render Trọn Gói .MP4 (-14 LUFS)</strong> để kết xuất phim H.264 thật từ kỳ quan 3D.
					</div>
				{:else}
					<div class="monitor-empty">Chưa có khung hình xem trước.</div>
				{/if}

				{#if activeSubtitleCue}
					<div class="subtitle-overlay">
						{#if subLang === 'vi' || subLang === 'both'}
							<div class="sub-vi">{activeSubtitleCue.text_vi}</div>
						{/if}
						{#if subLang === 'en' || subLang === 'both'}
							<div class="sub-en">{activeSubtitleCue.text_en}</div>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Multi-Track Timeline -->
			<div class="timeline-rack">
				<div class="row-between" style="margin-bottom:6px;">
					<span class="section-label">TIMELINE ĐA LỚP (THỜI LƯỢNG: {draft.cinema.duration_sec ?? 6}s · {draft.cinema.fps ?? 24} FPS)</span>
					<span class="mono tabular" style="font-size:11.5px; color:var(--brass-bright);">
						Playhead: {playheadSec.toFixed(2)}s / {(draft.cinema.duration_sec ?? 6).toFixed(2)}s
					</span>
				</div>

				<div class="track-row">
					<span class="track-name">1. Camera 3D</span>
					<div class="track-lane">
						{#each draft.cinema.keyframes ?? [] as kf, idx (kf.id || idx)}
							<span
								class="kf-diamond"
								style="left:{Math.min(97, (kf.time_sec / Math.max(1, draft.cinema.duration_sec ?? 6)) * 100)}%"
								title="{kf.time_sec}s · FOV {kf.fov_deg}°"
							>
								◆
							</span>
						{/each}
					</div>
				</div>

				<div class="track-row">
					<span class="track-name">2. EffectCraft</span>
					<div class="track-lane vfx-bar">
						<span>✨ Preset: {draft.cinema.vfx_preset ?? 'rune_sparks'} {draft.cinema.vfx_overlay_path ? '✓ RGBA Ready' : ''}</span>
					</div>
				</div>

				<div class="track-row">
					<span class="track-name">3. ToneForge</span>
					<div class="track-lane audio-bar">
						<span>
							🎵 Mastering -14.0 LUFS ·
							{draft.cinema.mastered_audio_path ? '✓ Đã chuẩn hóa EBU R128' : 'Sẽ tự động trộn khi Render'}
						</span>
					</div>
				</div>

				<div class="track-row">
					<span class="track-name">4. Phụ đề VI/EN</span>
					<div class="track-lane">
						{#each draft.cinema.subtitles ?? [] as cue (cue.id)}
							{@const dur = Math.max(1, draft.cinema.duration_sec ?? 6)}
							<span
								class="sub-clip"
								style="left:{(cue.start_sec / dur) * 100}%; width:{Math.max(6, ((cue.end_sec - cue.start_sec) / dur) * 100)}%;"
								title={cue.text_vi}
							>
								{cue.text_vi}
							</span>
						{/each}
					</div>
				</div>
			</div>
		{/if}
	</section>

	<!-- Right Column: Keyframes, VFX, ComfyUI, Audio Mastering & Subtitle Cues -->
	<aside class="cin-right card">
		{#if activeCinema && draft}
			<div class="sub-box">
				<div class="section-label">THÔNG SỐ QUAY &amp; BỐI CẢNH .GLB</div>
				<label class="field-lbl" style="margin-top:5px;">
					<span>Kỳ quan .GLB nguồn</span>
					<select
						class="select"
						value={draft.cinema.source_glb_path ?? draft.clockwork.glb_path ?? ''}
						onchange={(e) => {
							if (draft) draft.cinema.source_glb_path = (e.currentTarget as HTMLSelectElement).value || null;
						}}
					>
						<option value="">-- Dùng ảnh nền 2K của dự án --</option>
						{#each glbCatalogProjects as gp (gp.slug)}
							<option value={gp.manifest.clockwork.glb_path ?? ''}>{gp.title} ({gp.slug})</option>
						{/each}
					</select>
				</label>
				<div class="grid-2" style="margin-top:6px;">
					<label class="field-lbl">
						<span>Thời lượng (s)</span>
						<input class="input" type="number" min="2" max="20" step="0.5" bind:value={draft.cinema.duration_sec} />
					</label>
					<label class="field-lbl">
						<span>Ánh sáng</span>
						<select class="select" bind:value={renderMood}>
							<option value="golden_hour">Nắng vàng (Golden)</option>
							<option value="arcane_night">Đêm cổ ngữ (Arcane)</option>
							<option value="studio">Studio chuẩn</option>
						</select>
					</label>
				</div>
				<div class="grid-2" style="margin-top:6px;">
					<label class="field-lbl">
						<span>Lớp VFX EffectCraft</span>
						<select class="select" bind:value={draft.cinema.vfx_preset}>
							<option value="rune_sparks">Cổ ngữ &amp; Hạt sáng</option>
							<option value="mist_embers">Tàn lửa &amp; Sương</option>
							<option value="none">Tắt lớp phủ VFX</option>
						</select>
					</label>
					<div style="display:flex; align-items:flex-end;">
						<button class="btn btn-sm" style="width:100%;" onclick={handleRunVfxOverlayOnly}>
							✨ Thử VFX
						</button>
					</div>
				</div>
				<label style="display:flex; align-items:center; gap:6px; margin-top:8px; font-size:12px; cursor:pointer;">
					<input type="checkbox" bind:checked={draft.cinema.comfyui_enabled} />
					<span>Kết nối ComfyUI (127.0.0.1:8188 + tự động <code>/free</code> VRAM)</span>
				</label>
			</div>

			<!-- Audio & ToneForge Mastering -->
			<div class="sub-box">
				<div class="row-between">
					<span class="section-label">ÂM THANH &amp; TONEFORGE (-14 LUFS)</span>
					<button class="btn btn-sm btn-cyan" onclick={handleRunToneForgeMasterOnly}>
						🎚️ Master ngay
					</button>
				</div>
				<div class="grid-2" style="margin-top:6px;">
					<button class="btn btn-sm" onclick={() => voiceInputEl?.click()}>
						🎙️ Nạp Voice (.WAV)
					</button>
					<button class="btn btn-sm" onclick={() => bgmInputEl?.click()}>
						🎹 Nạp Nhạc FL Studio
					</button>
				</div>
				<button class="btn btn-sm" style="width:100%; margin-top:6px;" onclick={() => mp4InputEl?.click()}>
					🎞️ Nhập trực tiếp tệp .MP4 ngoài (BYOA)
				</button>
			</div>

			<!-- Camera Keyframes -->
			<div class="sub-box">
				<div class="row-between">
					<span class="section-label">CAMERA KEYFRAMES ({(draft.cinema.keyframes ?? []).length})</span>
					<button class="btn btn-sm" onclick={addKeyframe}>+ Keyframe</button>
				</div>
				{#each draft.cinema.keyframes ?? [] as kf, idx (kf.id || idx)}
					<div class="kf-row">
						<div class="row-between">
							<span class="mono" style="font-size:11px; color:var(--brass-bright);">#{idx + 1} · {kf.time_sec}s</span>
							<button
								class="btn btn-sm btn-ghost"
								onclick={() => {
									if (draft && draft.cinema.keyframes) {
										draft.cinema.keyframes = draft.cinema.keyframes.filter((_, i) => i !== idx);
									}
								}}
							>
								✕
							</button>
						</div>
						<div class="grid-2" style="margin-top:4px;">
							<input class="input" type="number" step="0.2" bind:value={kf.time_sec} title="Giây" />
							<input class="input" type="number" step="1" bind:value={kf.fov_deg} title="FOV (°)" />
						</div>
					</div>
				{/each}
			</div>

			<!-- Bilingual Subtitles -->
			<div class="sub-box">
				<div class="row-between">
					<span class="section-label">PHỤ ĐỀ SONG NGỮ VI / EN ({(draft.cinema.subtitles ?? []).length})</span>
					<button class="btn btn-sm" onclick={addSubtitleCue}>+ Phụ đề</button>
				</div>
				{#each draft.cinema.subtitles ?? [] as cue, idx (cue.id)}
					<div class="kf-row">
						<div class="row-between">
							<div style="display:flex; gap:4px; align-items:center;">
								<input class="input" style="width:58px;" type="number" step="0.2" bind:value={cue.start_sec} />
								<span>→</span>
								<input class="input" style="width:58px;" type="number" step="0.2" bind:value={cue.end_sec} />
							</div>
							<button
								class="btn btn-sm btn-ghost"
								onclick={() => {
									if (draft && draft.cinema.subtitles) {
										draft.cinema.subtitles = draft.cinema.subtitles.filter((_, i) => i !== idx);
									}
								}}
							>
								✕
							</button>
						</div>
						<input class="input" style="margin-top:4px;" placeholder="Phụ đề Tiếng Việt (Nam Bộ)" bind:value={cue.text_vi} />
						<input class="input" style="margin-top:4px;" placeholder="English Subtitle" bind:value={cue.text_en} />
					</div>
				{/each}
			</div>
		{/if}
	</aside>
</div>

<style>
	.cinema-workbench {
		display: grid;
		grid-template-columns: 265px 1fr 305px;
		gap: 10px;
		height: 100%;
		min-height: 0;
	}
	.cin-left,
	.cin-right {
		display: flex;
		flex-direction: column;
		gap: 8px;
		overflow-y: auto;
		min-height: 0;
	}
	.cin-center {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
		padding: 10px;
	}
	.row-between {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
	}
	.grid-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
	}
	.sub-box {
		padding: 9px;
		border-radius: var(--radius-md);
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.07);
	}
	.cin-list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		overflow-y: auto;
	}
	.cin-item {
		text-align: left;
		padding: 8px 10px;
		border-radius: var(--radius-md);
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.07);
		cursor: pointer;
	}
	.cin-item.active {
		border-color: var(--brass-bright);
		background: rgba(212, 168, 83, 0.14);
	}
	.monitor-wrap {
		position: relative;
		flex: 1;
		min-height: 300px;
		border-radius: var(--radius-md);
		overflow: hidden;
		background: #05080f;
		border: 1px solid var(--brass-line-strong);
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.monitor-video,
	.monitor-poster {
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
	.monitor-badge-center {
		position: absolute;
		padding: 10px 16px;
		border-radius: 10px;
		background: rgba(8, 12, 20, 0.88);
		border: 1px solid var(--brass-bright);
		font-size: 13px;
	}
	.subtitle-overlay {
		position: absolute;
		left: 10%;
		right: 10%;
		bottom: 46px;
		text-align: center;
		padding: 7px 14px;
		border-radius: 8px;
		background: rgba(6, 9, 15, 0.78);
		pointer-events: none;
	}
	.sub-vi {
		font-size: 15px;
		font-weight: 600;
		color: #fff3bf;
	}
	.sub-en {
		font-size: 12.5px;
		color: #dee2e6;
		margin-top: 2px;
	}
	.timeline-rack {
		padding: 10px;
		border-radius: var(--radius-md);
		background: rgba(10, 14, 22, 0.92);
		border: 1px solid var(--brass-line);
	}
	.track-row {
		display: grid;
		grid-template-columns: 105px 1fr;
		align-items: center;
		gap: 8px;
		margin-top: 5px;
	}
	.track-name {
		font-size: 11px;
		font-weight: 600;
		color: var(--text-secondary);
	}
	.track-lane {
		position: relative;
		height: 24px;
		border-radius: 5px;
		background: rgba(255, 255, 255, 0.04);
		border: 1px solid rgba(255, 255, 255, 0.08);
		overflow: hidden;
		display: flex;
		align-items: center;
		padding: 0 8px;
		font-size: 11px;
	}
	.vfx-bar {
		background: rgba(59, 201, 219, 0.14);
		border-color: rgba(59, 201, 219, 0.4);
		color: #99e9f2;
	}
	.audio-bar {
		background: rgba(64, 192, 87, 0.14);
		border-color: rgba(64, 192, 87, 0.4);
		color: #b2f2bb;
	}
	.kf-diamond {
		position: absolute;
		color: var(--brass-bright);
		font-size: 13px;
		transform: translateX(-50%);
	}
	.sub-clip {
		position: absolute;
		top: 2px;
		bottom: 2px;
		padding: 1px 6px;
		border-radius: 4px;
		background: rgba(212, 168, 83, 0.25);
		border: 1px solid var(--brass-primary);
		font-size: 10.5px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.kf-row {
		margin-top: 6px;
		padding-top: 6px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}
</style>
