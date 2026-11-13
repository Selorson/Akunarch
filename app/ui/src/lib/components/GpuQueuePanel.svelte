<script lang="ts">
	import type { GpuJobRow, HardwareStackReport, ProjectRecord } from '$lib/types';

	interface Props {
		hardware: HardwareStackReport | null;
		jobs: GpuJobRow[];
		projects: ProjectRecord[];
		onRefresh: () => Promise<void>;
		onReleaseVram: () => Promise<void>;
		onEnqueueJob: (
			projectId: number | null,
			workerKind: string,
			payload: Record<string, unknown>
		) => Promise<void>;
		onCancelJob: (jobId: number) => Promise<void>;
	}

	let {
		hardware,
		jobs,
		projects,
		onRefresh,
		onReleaseVram,
		onEnqueueJob,
		onCancelJob
	}: Props = $props();

	let selectedWorker = $state('hunyuan3d');
	let selectedMode = $state('probe');
	let selectedProjectId = $state<number | null>(null);
	let busy = $state(false);

	let vramPct = $derived.by(() => {
		if (!hardware || hardware.vram.total_mb <= 0) return 0;
		return Math.min(100, Math.round((hardware.vram.used_mb / hardware.vram.total_mb) * 100));
	});
	// B2: thanh kép — phần của Akunarch (đồng) và phần nền Windows & app khác (xám)
	let appPct = $derived.by(() => {
		if (!hardware || hardware.vram.total_mb <= 0 || !hardware.vram.app_vram_available) return 0;
		return Math.min(vramPct, ((hardware.vram.app_used_mb ?? 0) / hardware.vram.total_mb) * 100);
	});

	let availableModes = $derived.by(() => {
		if (selectedWorker === 'hunyuan3d') {
			return [
				{ value: 'probe', label: 'probe (Kiểm định khóa GPU & đo VRAM)' },
				{ value: 'sculpt_concept', label: 'sculpt_concept (Đúc .glb từ Ảnh Concept Dự Án fp16)' },
				{
					value: 'sculpt_hero_parts',
					label: 'sculpt_hero_parts (sculpt_hero_parts_gpu.py · Kho 47 Mesh)'
				}
			];
		}
		if (selectedWorker === 'blender') {
			return [
				{ value: 'probe', label: 'probe (Kiểm định khóa GPU & đo VRAM)' },
				{
					value: 'assemble_glb',
					label: 'assemble_glb (Lắp Đế + Nướng Cycles OptiX AO + Draco .glb)'
				},
				{
					value: 'render_intro_mp4',
					label: 'render_intro_mp4 (Render Phim Intro Xoay Sa Bàn .mp4)'
				}
			];
		}
		if (selectedWorker === 'materialcraft') {
			return [
				{ value: 'sidecar_version', label: 'sidecar_version (Gọi materialcraft-cli --version)' },
				{ value: 'pbr_pack', label: 'pbr_pack (Nướng bộ bản đồ PBR 2K CPU SIMD)' },
				{ value: 'probe', label: 'probe (Kiểm định hàng đợi)' }
			];
		}
		if (selectedWorker === 'worldgen') {
			return [
				{
					value: 'image_to_splat',
					label: 'image_to_splat (Chuyển Ảnh BYOA sang Gaussian Splat .ply 3DGS)'
				},
				{ value: 'probe', label: 'probe (Kiểm định khóa GPU & đo VRAM)' }
			];
		}
		if (selectedWorker === 'tts') {
			return [
				{
					value: 'tts_synthesize',
					label: 'tts_synthesize (Lồng tiếng Kịch bản VN: VieNeu-TTS VI + OmniVoice EN)'
				},
				{ value: 'probe', label: 'probe (Kiểm định khóa GPU & đo VRAM)' }
			];
		}
		if (selectedWorker === 'effectcraft') {
			return [
				{
					value: 'effectcraft_overlay',
					label: 'effectcraft_overlay (Kết xuất lớp phủ Cổ ngữ / VFX RGBA 1080p)'
				},
				{ value: 'sidecar_version', label: 'sidecar_version (Gọi effectcraft-cli --version)' }
			];
		}
		if (selectedWorker === 'filmcraft') {
			return [
				{
					value: 'cinema_render_pipeline',
					label: 'cinema_render_pipeline (Dây chuyền Điện Ảnh VFX + Phụ đề + -14 LUFS .mp4)'
				},
				{ value: 'sidecar_version', label: 'sidecar_version (Gọi filmcraft-cli --version)' }
			];
		}
		if (selectedWorker === 'toneforge') {
			return [
				{
					value: 'toneforge_master',
					label: 'toneforge_master (Mastering chuẩn -14.0 LUFS / -1.0 dBTP)'
				},
				{ value: 'sidecar_version', label: 'sidecar_version (Gọi akunarch-audio-cli --version)' }
			];
		}
		return [
			{ value: 'probe', label: 'probe (Kiểm định khóa GPU & đo VRAM)' },
			{ value: 'sidecar_version', label: 'sidecar_version (Gọi binary --version)' }
		];
	});

	$effect(() => {
		if (!availableModes.some((m) => m.value === selectedMode)) {
			selectedMode = availableModes[0].value;
		}
	});

	async function handleDispatch() {
		busy = true;
		try {
			await onEnqueueJob(selectedProjectId, selectedWorker, {
				mode: selectedMode,
				release_vram_after: selectedWorker === 'comfyui'
			});
		} finally {
			busy = false;
		}
	}
</script>

<div class="gpu-layout">
	<!-- Left: Live RTX 4080 16GB VRAM Supervisor + Toolchain Matrix -->
	<div class="gpu-left">
		<div class="card">
			<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;">
				<div>
					<div class="section-label">SINGLE-MUTEX GPU SUPERVISOR · ZERO-OOM</div>
					<h2 style="margin: 4px 0 2px; font-size: 17px;">
						{hardware?.vram.gpu_name ?? 'Đang dò GPU NVIDIA...'}
					</h2>
				</div>
				<div style="display: flex; gap: 6px;">
					<button class="btn btn-sm btn-cyan" onclick={onReleaseVram}>
						🧹 Giải phóng VRAM (ComfyUI /free)
					</button>
					<button class="btn btn-sm" onclick={onRefresh}>🔄 Đo lại</button>
				</div>
			</div>

			{#if hardware}
				<div class="vram-meter-wrap">
					<div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 12.5px;">
						<span>
							Đang dùng:
							<strong class="tabular">{hardware.vram.used_mb} MB</strong> /
							<span class="tabular">{hardware.vram.total_mb} MB</span>
							(Trống <strong class="tabular" style="color: #8ce99a">{hardware.vram.free_mb} MB</strong>)
						</span>
						<span class="tabular">
							GPU Load: <strong>{hardware.vram.utilization_pct}%</strong> · Nhiệt độ:
							<strong>{hardware.vram.temperature_c}°C</strong>
						</span>
					</div>
					<div class="vram-bar-bg vram-bar-dual" data-testid="gpu-vram-dual-bar">
						<div
							class="vram-bar-app {hardware.vram.within_16gb_budget ? '' : 'warn'}"
							style="width: {appPct}%"
							title="Akunarch: {hardware.vram.app_used_mb ?? 0} MB (WebView2 {hardware.vram.webview_used_mb ?? 0} · Worker {hardware.vram.worker_used_mb ?? 0})"
						></div>
						<div
							class="vram-bar-other"
							style="width: {Math.max(0, vramPct - appPct)}%"
							title="Windows & app khác: {hardware.vram.other_system_mb ?? hardware.vram.used_mb} MB"
						></div>
					</div>
					<div style="display: flex; gap: 14px; margin-top: 5px; font-size: 11.5px; color: var(--text-secondary);">
						<span><span class="legend-dot app"></span> Akunarch:
							<strong class="tabular">{hardware.vram.app_vram_available ? `${hardware.vram.app_used_mb ?? 0} MB` : '—'}</strong>
							(WebView2 {hardware.vram.webview_used_mb ?? 0} · Worker {hardware.vram.worker_used_mb ?? 0})</span>
						<span><span class="legend-dot other"></span> Windows & app khác:
							<strong class="tabular">{hardware.vram.other_system_mb ?? hardware.vram.used_mb} MB</strong></span>
					</div>
					<div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 12px;">
						<span class="badge {hardware.vram.within_16gb_budget ? 'badge-ok' : 'badge-err'}">
							{hardware.vram.within_16gb_budget
								? '✓ An toàn trong trần kỷ luật 16GB VRAM'
								: '⚠️ Cảnh báo tiệm cận trần 16GB VRAM'}
						</span>
						<span class="badge {hardware.active_mutex_locked ? 'badge-warn' : 'badge-cyan'}">
							Mutex GPU: {hardware.active_mutex_locked ? 'ĐANG KHÓA CHẠY 1 MODEL' : 'RẢNH (1-BY-1 READY)'}
						</span>
					</div>
				</div>
			{/if}
		</div>

		<div class="card" style="flex: 1; overflow: auto;">
			<div class="section-label" style="margin-bottom: 10px;">
				MA TRẬN KIỂM ĐỊNH HẠ TẦNG &amp; NATIVE RUST SIDECARS (E:\Akunarch\bin\)
			</div>
			<div class="tools-grid">
				{#if hardware}
					{#each hardware.tools as t (t.id)}
						<div class="tool-card" data-testid={`tool-card-${t.id}`}>
							<div style="display: flex; justify-content: space-between; align-items: center; gap: 6px;">
								<strong>{t.label}</strong>
								{#if t.available}
									<span class="badge badge-ok">Sẵn sàng</span>
								{:else}
									<span class="badge badge-brass">Lộ trình kế</span>
								{/if}
							</div>
							<div class="mono" style="color: var(--text-muted); font-size: 11px; margin: 4px 0; word-break: break-all;">
								{t.path_or_url}
							</div>
							<div style="font-size: 11.5px; color: var(--text-secondary);">{t.stage_note}</div>
						</div>
					{/each}
				{/if}
			</div>
		</div>
	</div>

	<!-- Right: Sequential GpuJobQueue Dispatcher & SQLite History -->
	<div class="gpu-right card">
		<div class="section-label">HÀNG ĐỢI TUẦN TỰ GPU_JOBS (SQLITE WAL)</div>
		<h3 style="margin: 4px 0 10px; font-size: 15.5px;">
			Điều phối Tác vụ 1-Model-Tại-1-Thời-Điểm
		</h3>

		<div class="dispatch-box">
			<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
				<label class="field-lbl">
					<span>Worker (worker_kind)</span>
					<select class="select" bind:value={selectedWorker}>
						<option value="hunyuan3d">hunyuan3d (AI Mesh fp16)</option>
						<option value="blender">blender (Blender 5.2 Cycles OptiX)</option>
						<option value="materialcraft">materialcraft (Sidecar CLI SIMD)</option>
						<option value="comfyui">comfyui (Depth/Wan 2.1)</option>
						<option value="worldgen">worldgen (3DGS Low-VRAM)</option>
						<option value="tts">tts (VieNeu-TTS / OmniVoice)</option>
						<option value="effectcraft">effectcraft (VFX .ecproj)</option>
						<option value="filmcraft">filmcraft (Timeline .mp4)</option>
						<option value="toneforge">toneforge (DSP -14 LUFS)</option>
					</select>
				</label>
				<label class="field-lbl">
					<span>Chế độ thực thi (mode)</span>
					<select class="select" bind:value={selectedMode}>
						{#each availableModes as m (m.value)}
							<option value={m.value}>{m.label}</option>
						{/each}
					</select>
				</label>
			</div>

			<div style="display: flex; gap: 8px; align-items: flex-end; margin-top: 8px;">
				<label class="field-lbl" style="flex: 1;">
					<span>Gắn với Dự án (bắt buộc cho sculpt_concept / assemble_glb / render_intro_mp4)</span>
					<select class="select" bind:value={selectedProjectId}>
						<option value={null}>— Không gắn dự án cụ thể —</option>
						{#each projects as p (p.id)}
							<option value={p.id}>{p.title} ({p.slug})</option>
						{/each}
					</select>
				</label>
				<button
					class="btn btn-brass"
					data-testid="enqueue-gpu-job-btn"
					onclick={handleDispatch}
					disabled={busy}
				>
					⚡ Đưa vào GpuJobQueue
				</button>
			</div>
		</div>

		<div class="jobs-scroll">
			{#if jobs.length === 0}
				<div style="text-align: center; color: var(--text-muted); padding: 28px;">
					Hàng đợi <code>gpu_jobs</code> đang trống.
				</div>
			{:else}
				{#each jobs as j (j.id)}
					<div class="job-row">
						<div style="display: flex; justify-content: space-between; align-items: center;">
							<div style="display: flex; align-items: center; gap: 7px;">
								<span class="mono tabular" style="color: var(--brass-bright)">#{j.id}</span>
								<strong>{j.worker_kind}</strong>
								{#if j.payload?.mode}
									<span class="badge mono">{String(j.payload.mode)}</span>
								{/if}
								<span
									class="badge {j.status === 'completed'
										? 'badge-ok'
										: j.status === 'failed'
											? 'badge-err'
											: j.status === 'running'
												? 'badge-cyan'
												: 'badge-brass'}"
								>
									{j.status}
								</span>
							</div>
							<div style="display: flex; align-items: center; gap: 8px;">
								<span class="mono tabular" style="color: var(--text-secondary)">
									Peak VRAM: {j.vram_peak_mb} MB{typeof j.payload?.worker_vram_peak_mb === 'number'
										? ` · Worker ${j.payload.worker_vram_peak_mb} MB`
										: ''}
								</span>
								{#if j.status === 'queued'}
									<button class="btn btn-sm" onclick={() => onCancelJob(j.id)}>Hủy</button>
								{/if}
							</div>
						</div>
						{#if j.output_path}
							<div class="mono" style="color: #8ce99a; margin-top: 5px; font-size: 11.5px; word-break: break-all;">
								✓ {j.output_path}
							</div>
						{/if}
						{#if j.error_log}
							<div class="mono" style="color: #ffa8a8; margin-top: 5px; font-size: 11.5px; word-break: break-all;">
								✕ {j.error_log}
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
	</div>
</div>

<style>
	.gpu-layout {
		display: grid;
		grid-template-columns: 1.15fr 1fr;
		gap: 12px;
		height: 100%;
		min-height: 0;
	}
	.gpu-left,
	.gpu-right {
		display: flex;
		flex-direction: column;
		gap: 12px;
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}
	.vram-meter-wrap {
		margin-top: 12px;
		padding: 12px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
	}
	.vram-bar-bg {
		height: 11px;
		border-radius: 999px;
		background: #080a10;
		border: 1px solid rgba(255, 255, 255, 0.1);
		overflow: hidden;
	}
	.vram-bar-dual {
		display: flex;
	}
	.vram-bar-app,
	.vram-bar-other {
		height: 100%;
		transition: width 0.25s ease;
	}
	.vram-bar-app {
		background: linear-gradient(90deg, #b8742a 0%, #d4a853 100%);
	}
	.vram-bar-app.warn {
		background: linear-gradient(90deg, #fab005 0%, #fa5252 100%);
	}
	.vram-bar-other {
		background: #5c6370;
	}
	.legend-dot {
		display: inline-block;
		width: 9px;
		height: 9px;
		border-radius: 2px;
		vertical-align: -1px;
	}
	.legend-dot.app {
		background: #d4a853;
	}
	.legend-dot.other {
		background: #5c6370;
	}
	.tools-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
	}
	.tool-card {
		padding: 10px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
	}
	.dispatch-box {
		padding: 11px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line-strong);
	}
	.field-lbl {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 12px;
		color: var(--text-secondary);
	}
	.jobs-scroll {
		flex: 1;
		overflow: auto;
		display: flex;
		flex-direction: column;
		gap: 7px;
	}
	.job-row {
		padding: 10px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}
</style>
