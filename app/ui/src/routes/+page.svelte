<script lang="ts">
	import { untrack } from 'svelte';
	import VaultPanel from '$lib/components/VaultPanel.svelte';
	import ProjectsStagePanel from '$lib/components/ProjectsStagePanel.svelte';
	import OpenWorldChunkWorkbench from '$lib/components/OpenWorldChunkWorkbench.svelte';
	import VnDirectorStagePanel from '$lib/components/VnDirectorStagePanel.svelte';
	import CinemaVfxTimelinePanel from '$lib/components/CinemaVfxTimelinePanel.svelte';
	import GpuQueuePanel from '$lib/components/GpuQueuePanel.svelte';
	import SyncHubPanel from '$lib/components/SyncHubPanel.svelte';
	import { getCurrentWindow } from '@tauri-apps/api/window';
	import { api, isTauriRuntime } from '$lib/ipc';
	import { setAllLoopsSuspended } from '$lib/webgl/on-demand-loop';
	import { requestWebglVramRelease } from '$lib/webgl/webgl-stage';
	import { listen } from '@tauri-apps/api/event';
	import type {
		AssetLibraryRow,
		CreateProjectInput,
		GpuJobRow,
		HardwareStackReport,
		ProjectManifest,
		ProjectRecord,
		SelorsonConnectionConfig,
		SyncLogRow,
		VaultSnapshot
	} from '$lib/types';

	type NavTab = 'vault' | 'projects' | 'chunks' | 'vn' | 'cinema' | 'gpu' | 'sync';

	let activeTab = $state<NavTab>('vault');
	let completedGpuCounter = $state(0);
	let dbPath = $state('');
	let projectsRoot = $state('E:\\Akunarch\\projects');

	let vault = $state<VaultSnapshot | null>(null);
	let loadingVault = $state(false);
	let assets = $state<AssetLibraryRow[]>([]);

	let projects = $state<ProjectRecord[]>([]);
	let selectedProjectSlug = $state<string | null>(null);

	let hardware = $state<HardwareStackReport | null>(null);
	let gpuJobs = $state<GpuJobRow[]>([]);
	let lastCompletedJobIds = new Set<number>();

	let selorsonConfig = $state<SelorsonConnectionConfig | null>(null);
	let syncLogs = $state<SyncLogRow[]>([]);

	// Cửa sổ bị ẩn hoặc thu nhỏ → không poll nvidia-smi, không chạy vòng render 3D liên tục
	let appBackgrounded = false;

	let toast = $state<{ message: string; isError: boolean } | null>(null);
	let toastTimer: ReturnType<typeof setTimeout> | null = null;

	function notify(message: string, isError = false) {
		toast = { message, isError };
		if (toastTimer) clearTimeout(toastTimer);
		toastTimer = setTimeout(() => {
			toast = null;
		}, 4800);
	}

	async function loadVault() {
		if (!isTauriRuntime()) return;
		loadingVault = true;
		try {
			vault = await api.vaultSnapshot();
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		} finally {
			loadingVault = false;
		}
	}

	async function refreshHardwareAndJobs() {
		if (!isTauriRuntime()) return;
		try {
			const [hw, jobs] = await Promise.all([api.gpuHardware(), api.gpuListJobs(40)]);
			hardware = hw;
			gpuJobs = jobs;

			// Auto-refresh projects when a project-bound GPU job finishes sculpting/baking/rendering
			let newlyFinishedProjectJob = false;
			for (const j of jobs) {
				if (j.status === 'completed' && !lastCompletedJobIds.has(j.id)) {
					lastCompletedJobIds.add(j.id);
					if (j.project_id !== null) newlyFinishedProjectJob = true;
				}
			}
			if (newlyFinishedProjectJob) {
				projects = await api.projectsList();
				completedGpuCounter += 1;
			}
		} catch {
			// ignore background poll errors
		}
	}

	async function bootstrapAll() {
		if (!isTauriRuntime()) return;
		try {
			const boot = await api.bootstrap();
			dbPath = boot.db_path;
			projectsRoot = boot.projects_root;
			projects = boot.projects;
			if (projects.length > 0 && !selectedProjectSlug) {
				const firstClockwork = projects.find((p) => p.manifest.kind === 'clockwork') ?? projects[0];
				selectedProjectSlug = firstClockwork.slug;
				// Open directly onto the live AAA PBR 3D Stage when real projects exist on disk!
				activeTab = 'projects';
			}
			assets = boot.asset_library;
			hardware = boot.hardware;
			selorsonConfig = boot.selorson_config;
			syncLogs = boot.sync_logs;
			const initialJobs = await api.gpuListJobs(40);
			gpuJobs = initialJobs;
			for (const j of initialJobs) {
				if (j.status === 'completed') lastCompletedJobIds.add(j.id);
			}
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		}
		await loadVault();
	}

	$effect(() => {
		untrack(() => {
			bootstrapAll();
		});
		// Mỗi lần poll spawn nvidia-smi (kéo GPU khỏi P8 trong chốc lát) → chỉ poll 4.5s khi có job GPU
		// hoặc đang mở tab GPU; còn lại 15s; dừng hẳn khi cửa sổ bị ẩn/thu nhỏ.
		let lastPollAt = Date.now();
		const timer = setInterval(() => {
			if (appBackgrounded) return;
			const busy = untrack(
				() => activeTab === 'gpu' || gpuJobs.some((j) => j.status === 'running' || j.status === 'queued')
			);
			if (!busy && Date.now() - lastPollAt < 15000) return;
			lastPollAt = Date.now();
			refreshHardwareAndJobs();
		}, 4500);

		// WebView2 trong Tauri KHÔNG báo document.hidden khi thu nhỏ cửa sổ (rAF vẫn 60/s — đã đo thực tế)
		// → hỏi trạng thái cửa sổ từ Tauri để tạm ngưng poll và mọi vòng render 3D liên tục.
		let disposedPage = false;
		const unlisteners: Array<() => void> = [];
		const updateBackgrounded = async () => {
			let minimized = false;
			if (isTauriRuntime()) {
				try {
					minimized = await getCurrentWindow().isMinimized();
				} catch {
					// giữ false nếu không đọc được
				}
			}
			const next = document.hidden || minimized;
			if (next === appBackgrounded) return;
			appBackgrounded = next;
			setAllLoopsSuspended(next);
			if (!next) refreshHardwareAndJobs();
		};
		document.addEventListener('visibilitychange', updateBackgrounded);
		if (isTauriRuntime()) {
			// B2: hàng đợi GPU sắp chạy job nặng → tháo sân khấu 3D để nhường VRAM
			void listen<{ kind: string; job_id: number }>('akunarch://gpu-job-starting', (ev) => {
				requestWebglVramRelease('gpu-job');
				notify(`Đã tạm tắt 3D để nhường VRAM cho tác vụ GPU '${ev.payload.kind}' #${ev.payload.job_id}.`);
			})
				.then((unlisten) => (disposedPage ? unlisten() : unlisteners.push(unlisten)))
				.catch(() => {});
			const win = getCurrentWindow();
			for (const subscribe of [win.onResized(updateBackgrounded), win.onFocusChanged(updateBackgrounded)]) {
				void subscribe.then((unlisten) => (disposedPage ? unlisten() : unlisteners.push(unlisten))).catch(() => {});
			}
		}

		const onStudioHotkey = (ev: KeyboardEvent) => {
			const tag = (ev.target as HTMLElement | null)?.tagName;
			if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
			if (ev.key === 'F1') {
				ev.preventDefault();
				activeTab = 'vault';
			} else if (ev.key === 'F2') {
				ev.preventDefault();
				activeTab = 'projects';
			} else if (ev.key === 'F3') {
				ev.preventDefault();
				activeTab = 'chunks';
			} else if (ev.key === 'F4') {
				ev.preventDefault();
				activeTab = 'vn';
			} else if (ev.key === 'F5') {
				ev.preventDefault();
				activeTab = 'cinema';
			} else if (ev.key === 'F6') {
				ev.preventDefault();
				activeTab = 'gpu';
			} else if (ev.key === 'F7') {
				ev.preventDefault();
				activeTab = 'sync';
			} else if (ev.key === '[' || ev.key === ']') {
				const list = untrack(() => projects);
				if (list.length === 0) return;
				const curIdx = list.findIndex((p) => p.slug === untrack(() => selectedProjectSlug));
				const step = ev.key === ']' ? 1 : -1;
				const nextIdx = ((curIdx < 0 ? 0 : curIdx) + step + list.length) % list.length;
				selectedProjectSlug = list[nextIdx].slug;
			}
		};
		window.addEventListener('keydown', onStudioHotkey);
		return () => {
			disposedPage = true;
			clearInterval(timer);
			document.removeEventListener('visibilitychange', updateBackgrounded);
			for (const unlisten of unlisteners) unlisten();
			window.removeEventListener('keydown', onStudioHotkey);
		};
	});

	function sanitizeSlugClient(raw: string): string {
		return raw
			.trim()
			.replace(/[đĐ]/g, 'd')
			.normalize('NFD')
			.replace(/[\u0300-\u036f]/g, '')
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '');
	}

	async function handleCreateProject(input: CreateProjectInput) {
		try {
			const created = await api.projectsCreate(input);
			projects = await api.projectsList();
			selectedProjectSlug = created.slug;
			activeTab =
				created.manifest.kind === 'open_world'
					? 'chunks'
					: created.manifest.kind === 'vn_episode'
						? 'vn'
						: created.manifest.kind === 'cinema'
							? 'cinema'
							: 'projects';
			notify(`Đã tạo dự án mở '${created.slug}' tại ${created.folder_path}`);
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			const cleanSlug = sanitizeSlugClient(input.slug || input.title);
			const existing = msg.includes('đã tồn tại')
				? projects.find((p) => p.slug === cleanSlug || p.slug === input.slug)
				: undefined;
			if (existing) {
				const addedConcepts = (input.concept_paths ?? []).filter(
					(cp) => cp && !existing.manifest.concept_paths.includes(cp)
				);
				if (addedConcepts.length > 0) {
					const merged = {
						...existing.manifest,
						concept_paths: [...existing.manifest.concept_paths, ...addedConcepts]
					};
					await api.projectsUpdate(merged);
					projects = await api.projectsList();
					selectedProjectSlug = existing.slug;
					activeTab = 'projects';
					notify(
						`Đã bổ sung ${addedConcepts.length} bản vẽ Concept vào dự án '${existing.slug}'.`
					);
					return;
				}
				selectedProjectSlug = existing.slug;
				activeTab = 'projects';
				notify(`Đã mở dự án hiện có '${existing.slug}'.`);
				return;
			}
			notify(msg, true);
		}
	}

	async function handleSaveManifest(manifest: ProjectManifest, originalSlug?: string) {
		try {
			const updated = await api.projectsUpdate(manifest, originalSlug);
			projects = await api.projectsList();
			selectedProjectSlug = updated.slug;
			notify(`Đã lưu project.akun.json cho '${updated.slug}'.`);
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleProjectMutated(updated: ProjectRecord, notice?: string) {
		projects = await api.projectsList();
		selectedProjectSlug = updated.slug;
		if (notice) notify(notice);
	}

	async function handleRescanProjects() {
		try {
			projects = await api.projectsRescan();
			notify(`Đã đồng bộ ${projects.length} dự án từ thư mục projects/.`);
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleScanAssets() {
		try {
			assets = await api.vaultScanAssets();
			notify(`Đã lập chỉ mục ${assets.length} tài nguyên vật liệu PBR & Mesh.`);
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleReleaseVram() {
		try {
			// B2: tháo sân khấu WebGL trước, chờ GPU process trả bộ nhớ, rồi mới giải phóng ComfyUI + đo lại
			requestWebglVramRelease('manual');
			await new Promise((r) => setTimeout(r, 300));
			const res = await api.gpuReleaseVram();
			if (hardware) {
				hardware = { ...hardware, vram: res.vram_after };
			}
			notify(res.message);
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleEnqueueJob(
		projectId: number | null,
		workerKind: string,
		payload: Record<string, unknown>
	) {
		try {
			await api.gpuEnqueueJob(projectId, workerKind, payload);
			notify(`Đã xếp hàng tác vụ '${workerKind}' vào GpuJobQueue.`);
			setTimeout(refreshHardwareAndJobs, 350);
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleEnqueueGpuForProject(
		project: ProjectRecord,
		workerKind: string,
		payload: Record<string, unknown>,
		noticeLabel: string
	) {
		try {
			await api.gpuEnqueueJob(project.id, workerKind, payload);
			notify(`⚡ Đã xếp hàng "${noticeLabel}" cho '${project.slug}' vào GpuJobQueue.`);
			setTimeout(refreshHardwareAndJobs, 350);
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleCancelJob(jobId: number) {
		try {
			await api.gpuCancelJob(jobId);
			await refreshHardwareAndJobs();
			notify(`Đã hủy tác vụ #${jobId}.`);
		} catch (err) {
			notify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleSyncedRefresh() {
		projects = await api.projectsList();
		syncLogs = await api.syncListLogs(30);
	}
</script>

<div class="studio-shell">
	<!-- Top Astrolabe Command Bar -->
	<header class="topbar">
		<div class="brand-cluster">
			<svg width="30" height="30" viewBox="0 0 64 64" aria-hidden="true">
				<circle cx="32" cy="32" r="27" fill="#101522" stroke="#d4a853" stroke-width="3" />
				<circle cx="32" cy="32" r="19" fill="none" stroke="#8c6826" stroke-width="1.8" />
				<polygon points="32,12 45,48 38,48 32,30 26,48 19,48" fill="#f2cb7c" />
				<rect x="23" y="36" width="18" height="3.5" fill="#d4a853" />
				<circle cx="32" cy="32" r="4" fill="#3bc9db" />
			</svg>
			<div>
				<div class="brand-title">AKUNARCH <span class="ver">v2.1</span></div>
				<div class="brand-sub">AAA PBR 3D · CHUNKS 256M · 3DGS SPARK · VN TTS · CINEMA -14 LUFS</div>
			</div>
		</div>

		<div class="telemetry-strip">
			{#if hardware}
				{@const v = hardware.vram}
				<div
					class="tele-pill"
					data-testid="topbar-vram-pill"
					title={`${v.gpu_name}
WebView2 (UI/3D): ${v.app_vram_available ? `${v.webview_used_mb ?? 0} MB` : 'không đọc được'}
GPU Worker: ${v.app_vram_available ? `${v.worker_used_mb ?? 0} MB` : 'không đọc được'}
Windows & app khác: ${v.other_system_mb ?? v.used_mb} MB
GPU ${v.utilization_pct}% · ${v.temperature_c} °C`}
				>
					<span class="dot {v.within_16gb_budget ? 'ok' : 'warn'}"></span>
					<span class="tabular">
						VRAM App: <strong data-testid="topbar-vram-app-mb">{v.app_vram_available ? (v.app_used_mb ?? 0) : '—'}</strong> MB
						· Máy: {v.used_mb} / {v.total_mb} MB
					</span>
					<button class="btn btn-sm btn-ghost" onclick={handleReleaseVram} title="Giải phóng VRAM">
						🧹
					</button>
				</div>
			{/if}

			{#if vault}
				<div class="tele-pill" title={vault.summary.db_path}>
					<span class="dot ok"></span>
					<span class="tabular">
						Co-Writer RO: <strong>{vault.summary.entities_count}</strong> thực thể ·
						<strong>{vault.summary.concepts_canon_15_count}</strong> concepts chuẩn
					</span>
				</div>
			{/if}

			<div class="tele-pill" title={dbPath}>
				<span class="dot cyan"></span>
				<span class="tabular">Dự án mở: <strong>{projects.length}</strong></span>
			</div>
		</div>
	</header>

	<!-- Main Workspace Split: Left Navigation Rail + Active Panel -->
	<div class="workspace-body">
		<nav class="nav-rail" aria-label="Phân xưởng Akunarch">
			<button
				class="nav-btn {activeTab === 'vault' ? 'active' : ''}"
				data-testid="nav-vault"
				onclick={() => (activeTab = 'vault')}
			>
				<span class="nav-idx">00</span>
				<div>
					<strong>Kho Thánh Tích</strong>
					<small>Co-Writer RO &amp; Concepts</small>
				</div>
			</button>

			<button
				class="nav-btn {activeTab === 'projects' ? 'active' : ''}"
				data-testid="nav-projects"
				onclick={() => (activeTab = 'projects')}
			>
				<span class="nav-idx">01</span>
				<div>
					<strong>Sa Bàn Cơ Khí 3D</strong>
					<small>AAA PBR .GLB · BYOA · Manga 2K</small>
				</div>
			</button>

			<button
				class="nav-btn {activeTab === 'chunks' ? 'active' : ''}"
				data-testid="nav-chunks"
				onclick={() => (activeTab = 'chunks')}
			>
				<span class="nav-idx">02</span>
				<div>
					<strong>Thế Giới Mở 256m</strong>
					<small>Edge-Stitch · 3DGS Spark · Audio</small>
				</div>
			</button>

			<button
				class="nav-btn {activeTab === 'vn' ? 'active' : ''}"
				data-testid="nav-vn"
				onclick={() => (activeTab = 'vn')}
			>
				<span class="nav-idx">03</span>
				<div>
					<strong>Trường Quay VN 3D</strong>
					<small>VieNeu-TTS · OmniVoice · Nhánh</small>
				</div>
			</button>

			<button
				class="nav-btn {activeTab === 'cinema' ? 'active' : ''}"
				data-testid="nav-cinema"
				onclick={() => (activeTab = 'cinema')}
			>
				<span class="nav-idx">04</span>
				<div>
					<strong>Điện Ảnh &amp; VFX</strong>
					<small>EffectCraft · ToneForge -14 LUFS</small>
				</div>
			</button>

			<button
				class="nav-btn {activeTab === 'gpu' ? 'active' : ''}"
				data-testid="nav-gpu"
				onclick={() => (activeTab = 'gpu')}
			>
				<span class="nav-idx">05</span>
				<div>
					<strong>GpuJobQueue &amp; 4/4 CLI</strong>
					<small>RTX 4080 16GB Supervisor</small>
				</div>
			</button>

			<button
				class="nav-btn {activeTab === 'sync' ? 'active' : ''}"
				data-testid="nav-sync"
				onclick={() => (activeTab = 'sync')}
			>
				<span class="nav-idx">06</span>
				<div>
					<strong>Kiểm Định &amp; Đồng Bộ</strong>
					<small>Selorson V3 Draft-First</small>
				</div>
			</button>

			<div class="nav-footer mono">
				<div>DB: akunarch.db (WAL)</div>
				<div>Stack: Tauri v2 · Svelte 5 · Draco</div>
			</div>
		</nav>

		<main class="main-stage">
			{#if activeTab === 'vault'}
				<VaultPanel
					{vault}
					{assets}
					{loadingVault}
					onRefreshVault={loadVault}
					onScanAssets={handleScanAssets}
					onQuickScaffoldProject={handleCreateProject}
				/>
			{:else if activeTab === 'projects'}
				<ProjectsStagePanel
					{projects}
					selectedSlug={selectedProjectSlug}
					{projectsRoot}
					entities={vault?.entities ?? []}
					onSelectSlug={(s) => (selectedProjectSlug = s)}
					onCreateProject={handleCreateProject}
					onSaveManifest={handleSaveManifest}
					onProjectMutated={handleProjectMutated}
					onRescanDisk={handleRescanProjects}
					onEnqueueGpuForProject={handleEnqueueGpuForProject}
					onJumpToSync={(s) => {
						selectedProjectSlug = s;
						activeTab = 'sync';
					}}
					onNotify={notify}
				/>
			{:else if activeTab === 'chunks'}
				<OpenWorldChunkWorkbench
					{projects}
					selectedSlug={selectedProjectSlug}
					onSelectSlug={(s) => (selectedProjectSlug = s)}
					onCreateProject={handleCreateProject}
					onSaveManifest={handleSaveManifest}
					onProjectMutated={handleProjectMutated}
					onEnqueueGpuForProject={handleEnqueueGpuForProject}
					onJumpToSync={(s) => {
						selectedProjectSlug = s;
						activeTab = 'sync';
					}}
					onNotify={notify}
				/>
			{:else if activeTab === 'vn'}
				<VnDirectorStagePanel
					{projects}
					selectedSlug={selectedProjectSlug}
					lastFinishedGpuCount={completedGpuCounter}
					onSelectSlug={(s) => (selectedProjectSlug = s)}
					onCreateProject={handleCreateProject}
					onProjectMutated={handleProjectMutated}
					onEnqueueGpuForProject={handleEnqueueGpuForProject}
					onJumpToSync={(s) => {
						selectedProjectSlug = s;
						activeTab = 'sync';
					}}
					onNotify={notify}
				/>
			{:else if activeTab === 'cinema'}
				<CinemaVfxTimelinePanel
					{projects}
					selectedSlug={selectedProjectSlug}
					onSelectSlug={(s) => (selectedProjectSlug = s)}
					onCreateProject={handleCreateProject}
					onSaveManifest={handleSaveManifest}
					onProjectMutated={handleProjectMutated}
					onEnqueueGpuForProject={handleEnqueueGpuForProject}
					onJumpToSync={(s) => {
						selectedProjectSlug = s;
						activeTab = 'sync';
					}}
					onNotify={notify}
				/>
			{:else if activeTab === 'gpu'}
				<GpuQueuePanel
					{hardware}
					jobs={gpuJobs}
					{projects}
					onRefresh={refreshHardwareAndJobs}
					onReleaseVram={handleReleaseVram}
					onEnqueueJob={handleEnqueueJob}
					onCancelJob={handleCancelJob}
				/>
			{:else if activeTab === 'sync'}
				<SyncHubPanel
					{projects}
					initialSlug={selectedProjectSlug}
					{selorsonConfig}
					{syncLogs}
					onConfigUpdated={(c) => (selorsonConfig = c)}
					onSyncedRefresh={handleSyncedRefresh}
					onNotify={notify}
				/>
			{/if}
		</main>
	</div>

	{#if toast}
		<div class="toast {toast.isError ? 'err' : 'ok'}" role="status">
			{toast.message}
		</div>
	{/if}
</div>

<style>
	.studio-shell {
		display: flex;
		flex-direction: column;
		width: 100vw;
		height: 100vh;
		background: radial-gradient(circle at top right, #151b2b 0%, #080a0f 60%);
		overflow: hidden;
	}
	.topbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		padding: 9px 16px;
		background: rgba(13, 16, 24, 0.95);
		border-bottom: 1px solid var(--brass-line-strong);
		flex-shrink: 0;
	}
	.brand-cluster {
		display: flex;
		align-items: center;
		gap: 11px;
	}
	.brand-title {
		font-size: 15.5px;
		font-weight: 800;
		letter-spacing: 0.12em;
		color: var(--brass-bright);
	}
	.brand-title .ver {
		font-size: 11px;
		font-weight: 600;
		padding: 1px 6px;
		border-radius: 4px;
		background: rgba(212, 168, 83, 0.16);
		color: var(--brass-primary);
		letter-spacing: 0.04em;
	}
	.brand-sub {
		font-size: 10.5px;
		letter-spacing: 0.08em;
		color: var(--text-muted);
	}
	.telemetry-strip {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}
	.tele-pill {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		padding: 4px 10px;
		border-radius: 999px;
		background: var(--obs-panel);
		border: 1px solid var(--brass-line);
		font-size: 12px;
	}
	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}
	.dot.ok {
		background: var(--emerald-ok);
		box-shadow: 0 0 8px var(--emerald-ok);
	}
	.dot.warn {
		background: var(--amber-warn);
	}
	.dot.cyan {
		background: var(--cyan-arcane);
		box-shadow: 0 0 8px var(--cyan-arcane);
	}
	.workspace-body {
		flex: 1;
		min-height: 0;
		display: grid;
		grid-template-columns: 228px 1fr;
	}
	.nav-rail {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 12px 10px;
		background: var(--obs-panel);
		border-right: 1px solid var(--brass-line);
	}
	.nav-btn {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 11px;
		border-radius: var(--radius-md);
		border: 1px solid transparent;
		background: transparent;
		cursor: pointer;
		text-align: left;
		transition: all 0.14s ease;
	}
	.nav-btn:hover {
		background: rgba(255, 255, 255, 0.04);
		border-color: var(--brass-line);
	}
	.nav-btn.active {
		background: linear-gradient(90deg, rgba(212, 168, 83, 0.18) 0%, rgba(212, 168, 83, 0.04) 100%);
		border-color: var(--brass-bright);
	}
	.nav-idx {
		font-family: var(--font-mono);
		font-size: 11px;
		font-weight: 700;
		color: var(--brass-primary);
		padding: 3px 6px;
		border-radius: 4px;
		background: rgba(212, 168, 83, 0.12);
	}
	.nav-btn div {
		display: flex;
		flex-direction: column;
	}
	.nav-btn small {
		font-size: 11px;
		color: var(--text-muted);
	}
	.nav-footer {
		margin-top: auto;
		padding: 10px;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
		color: var(--text-muted);
		font-size: 11px;
		line-height: 1.6;
	}
	.main-stage {
		padding: 12px;
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}
	.toast {
		position: fixed;
		right: 20px;
		bottom: 20px;
		z-index: 200;
		max-width: 520px;
		padding: 11px 16px;
		border-radius: var(--radius-md);
		font-weight: 500;
		box-shadow: 0 12px 32px rgba(0, 0, 0, 0.65);
	}
	.toast.ok {
		background: #13291d;
		border: 1px solid #40c057;
		color: #b2f2bb;
	}
	.toast.err {
		background: #2e1215;
		border: 1px solid #fa5252;
		color: #ffc9c9;
	}
</style>
