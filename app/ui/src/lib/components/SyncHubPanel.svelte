<script lang="ts">
	import { api } from '$lib/ipc';
	import type {
		ProjectRecord,
		QaAuditReport,
		SelorsonConnectionConfig,
		SyncLogRow
	} from '$lib/types';

	interface Props {
		projects: ProjectRecord[];
		initialSlug: string | null;
		selorsonConfig: SelorsonConnectionConfig | null;
		syncLogs: SyncLogRow[];
		onConfigUpdated: (cfg: SelorsonConnectionConfig) => void;
		onSyncedRefresh: () => Promise<void>;
		onNotify: (msg: string, isError?: boolean) => void;
	}

	let {
		projects,
		initialSlug,
		selorsonConfig,
		syncLogs,
		onConfigUpdated,
		onSyncedRefresh,
		onNotify
	}: Props = $props();

	let baseUrl = $state('http://127.0.0.1:8001');
	let manualToken = $state('');
	let loginEmail = $state('admin@selorson.com');
	let loginPassword = $state('');
	let showAuthBox = $state(false);

	let selectedSlug = $state('');
	let lastInitializedSlug = '';
	let forceDraft = $state(true);
	let qaReport = $state<QaAuditReport | null>(null);

	let overviewLoading = $state(false);
	let overviewData = $state<Record<string, unknown> | null>(null);
	let overviewError = $state('');

	let pushing = $state(false);

	$effect(() => {
		if (selorsonConfig?.base_url) {
			baseUrl = selorsonConfig.base_url;
		}
	});

	$effect(() => {
		if (initialSlug && projects.some((p) => p.slug === initialSlug)) {
			selectedSlug = initialSlug;
		} else if ((!selectedSlug || !projects.some((p) => p.slug === selectedSlug)) && projects.length > 0) {
			selectedSlug = projects[0].slug;
		}
	});

	$effect(() => {
		if (selectedSlug && selectedSlug !== lastInitializedSlug) {
			const matched = projects.find((p) => p.slug === selectedSlug);
			if (matched) {
				lastInitializedSlug = selectedSlug;
				forceDraft = matched.manifest.sync_policy?.force_draft ?? true;
			}
		}
	});

	$effect(() => {
		const slug = selectedSlug;
		const draft = forceDraft;
		const projVersion = projects.find((p) => p.slug === slug)?.updated_at ?? '';
		void projVersion;
		if (!slug) {
			qaReport = null;
			return;
		}
		let cancelled = false;
		api
			.syncAuditProject(slug, draft)
			.then((rep) => {
				if (!cancelled) qaReport = rep;
			})
			.catch(() => {
				if (!cancelled) qaReport = null;
			});
		return () => {
			cancelled = true;
		};
	});

	let overviewSummary = $derived.by(() => {
		const d = overviewData?.data as Record<string, unknown> | undefined;
		return (d?.summary as Record<string, number> | undefined) ?? null;
	});

	let overviewItems = $derived.by(() => {
		const d = overviewData?.data as Record<string, unknown> | undefined;
		return (d?.items as Array<Record<string, unknown>> | undefined) ?? [];
	});

	async function handleFetchOverview() {
		overviewLoading = true;
		overviewError = '';
		try {
			const res = await api.syncFetchOverview(baseUrl);
			overviewData = res;
			const updatedCfg = await api.syncGetConfig();
			onConfigUpdated(updatedCfg);
			onNotify('Đã kết nối 2 chiều và tải tổng quan /admin/world/overview từ Selorson Beta!');
		} catch (err) {
			overviewError = err instanceof Error ? err.message : String(err);
		} finally {
			overviewLoading = false;
		}
	}

	async function handleSaveToken() {
		try {
			const cfg = await api.syncSaveConfig(baseUrl, manualToken || undefined);
			onConfigUpdated(cfg);
			manualToken = '';
			onNotify('Đã lưu cấu hình cổng Selorson.');
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleLogin(e: SubmitEvent) {
		e.preventDefault();
		try {
			await api.syncLogin(baseUrl, loginEmail, loginPassword);
			const cfg = await api.syncGetConfig();
			onConfigUpdated(cfg);
			loginPassword = '';
			showAuthBox = false;
			onNotify('Đăng nhập Admin Selorson thành công!');
			await handleFetchOverview();
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handlePushToSelorson() {
		if (!selectedSlug) return;
		pushing = true;
		try {
			const res = await api.syncPushProject(selectedSlug, forceDraft, baseUrl);
			const updatedCfg = await api.syncGetConfig();
			onConfigUpdated(updatedCfg);
			const msg =
				(res.message as string | undefined) ??
				'Đã đẩy gói tài nguyên sang Selorson ở trạng thái Nháp!';
			onNotify(msg);
			await onSyncedRefresh();
			await handleFetchOverview();
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			pushing = false;
		}
	}

	async function handleExportBundle() {
		if (!selectedSlug) return;
		try {
			const outPath = await api.projectsExportBundle(selectedSlug);
			onNotify(`Đã đóng gói .akunbundle.zip tại: ${outPath}`);
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		}
	}
</script>

<div class="sync-layout">
	<!-- Left: Selorson Beta Inbound Overview (GET /api/v1/admin/world/overview) -->
	<div class="sync-left card">
		<div class="section-label">PHÂN XƯỞNG 4 · CỔNG LIÊN THÔNG 2 CHIỀU VỚI SELORSON BETA</div>
		<div style="display: flex; gap: 8px; align-items: center; margin-top: 8px;">
			<input
				class="input mono"
				style="flex: 1;"
				bind:value={baseUrl}
				placeholder="http://127.0.0.1:8001"
			/>
			<button
				class="btn btn-brass"
				data-testid="connect-selorson-btn"
				onclick={handleFetchOverview}
				disabled={overviewLoading}
			>
				{overviewLoading ? '⏳ Đang nối...' : '⚡ Nối & Tải /admin/world/overview'}
			</button>
			<button class="btn" onclick={() => (showAuthBox = !showAuthBox)}>🔑 Phiên Admin</button>
		</div>

		<div style="display: flex; gap: 8px; align-items: center; margin-top: 6px; font-size: 12px;">
			<span class="badge {selorsonConfig?.has_token ? 'badge-ok' : 'badge-brass'}">
				Token: {selorsonConfig?.token_preview ?? 'Chưa cấu hình (Tự động cấp JWT nội bộ khi nối Beta cùng máy)'}
			</span>
		</div>

		{#if showAuthBox}
			<div class="auth-drawer">
				<form onsubmit={handleLogin} style="display: flex; gap: 6px; align-items: center;">
					<input class="input" placeholder="Email Admin" bind:value={loginEmail} />
					<input
						class="input"
						type="password"
						placeholder="Mật khẩu Admin"
						bind:value={loginPassword}
					/>
					<button type="submit" class="btn btn-sm btn-brass">Đăng nhập</button>
				</form>
				<div style="display: flex; gap: 6px; margin-top: 7px;">
					<input
						class="input mono"
						placeholder="Hoặc dán trực tiếp Bearer JWT Token..."
						bind:value={manualToken}
					/>
					<button type="button" class="btn btn-sm" onclick={handleSaveToken}>Lưu Token</button>
				</div>
			</div>
		{/if}

		{#if overviewError}
			<div class="err-banner">
				<strong>Trạng thái kết nối Selorson:</strong> {overviewError}
			</div>
		{/if}

		{#if overviewSummary}
			<div class="overview-kpis">
				<div class="ov-stat">
					<span class="ov-num tabular">{overviewSummary.total_places ?? 0}</span>
					<span class="ov-lbl">
						Địa danh ({overviewSummary.published_places ?? 0} duyệt · {overviewSummary.pending_places ?? 0} nháp)
					</span>
				</div>
				<div class="ov-stat">
					<span class="ov-num tabular">{overviewSummary.total_chunks ?? 0}</span>
					<span class="ov-lbl">
						Ô Chunk ({overviewSummary.published_chunks ?? 0} duyệt · {overviewSummary.pending_chunks ?? 0} nháp)
					</span>
				</div>
				<div class="ov-stat">
					<span class="ov-num tabular">{overviewSummary.with_desktop_pack ?? 0}</span>
					<span class="ov-lbl">Có gói 3D (.glb/.zip)</span>
				</div>
				<div class="ov-stat">
					<span class="ov-num tabular">{overviewSummary.total_videos ?? 0}</span>
					<span class="ov-lbl">Tổng Video / Intro</span>
				</div>
			</div>

			<div class="items-scroll">
				{#each overviewItems as it (it.id)}
					<div class="ov-item-row">
						<div>
							<strong>{it.name}</strong>
							<span class="mono" style="color: var(--text-muted); margin-left: 6px;">
								({it.slug})
							</span>
							<div style="display: flex; gap: 5px; margin-top: 4px;">
								<span class="badge">{it.category}</span>
								{#if it.is_active}
									<span class="badge badge-ok">Đã xuất bản</span>
								{:else}
									<span class="badge badge-warn">Nháp chờ duyệt</span>
								{/if}
								{#if it.en_translation}
									<span class="badge badge-cyan">🇬🇧 Có bản EN</span>
								{/if}
							</div>
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<div class="empty-center">
				Bấm <strong>⚡ Nối &amp; Tải /admin/world/overview</strong> để đồng bộ danh mục địa danh &amp; lưới ô Chunk hiện có từ <code>Selorson Beta</code>.
			</div>
		{/if}
	</div>

	<!-- Right: Outbound QA Audit & POST /api/v1/admin/sync/world-studio + sync_logs -->
	<div class="sync-right">
		<div class="card" style="flex: 1.25; display: flex; flex-direction: column; min-height: 0;">
			<div class="section-label">KIỂM ĐỊNH QA CANON &amp; ĐẨY SANG SELORSON (DRAFT-FIRST)</div>
			<div style="display: flex; gap: 8px; align-items: center; margin-top: 8px;">
				<select class="select" style="flex: 1;" bind:value={selectedSlug}>
					{#if projects.length === 0}
						<option value="">— Chưa có dự án nào —</option>
					{:else}
						{#each projects as p (p.slug)}
							<option value={p.slug}>{p.title} ({p.slug} · {p.kind})</option>
						{/each}
					{/if}
				</select>
				<label style="display: flex; align-items: center; gap: 6px; font-size: 12.5px; white-space: nowrap;">
					<input type="checkbox" bind:checked={forceDraft} />
					<span>Bắt buộc Nháp (<code>force_draft = true</code>)</span>
				</label>
			</div>

			{#if qaReport}
				<div class="qa-findings">
					{#each qaReport.findings as f, idx (idx)}
						<div class="qa-row {f.severity}">
							<span
								class="badge {f.severity === 'blocker'
									? 'badge-err'
									: f.severity === 'warning'
										? 'badge-warn'
										: 'badge-ok'}"
							>
								{f.rule_code}
							</span>
							<span>{f.message}</span>
						</div>
					{/each}
				</div>

				<div class="section-label" style="margin: 8px 0 4px;">
					HỢP ĐỒNG GỬI ĐI (POST /api/v1/admin/sync/world-studio)
				</div>
				<pre class="payload-box mono">{JSON.stringify(qaReport.payload_preview, null, 2)}</pre>

				<div style="display: flex; gap: 8px; margin-top: 10px;">
					<button
						class="btn btn-brass"
						style="flex: 1.4;"
						onclick={handlePushToSelorson}
						disabled={pushing || !qaReport.passed}
					>
						{pushing
							? '⏳ Đang đẩy sang Selorson...'
							: '🚀 Đẩy Gói Nháp sang Selorson Beta'}
					</button>
					<button class="btn" style="flex: 1;" onclick={handleExportBundle}>
						📦 Xuất .akunbundle.zip
					</button>
				</div>
			{:else}
				<div class="empty-center">Chọn một dự án để chạy bộ kiểm định QA Canon &amp; xem trước gói đồng bộ.</div>
			{/if}
		</div>

		<div class="card" style="flex: 0.75; display: flex; flex-direction: column; min-height: 0;">
			<div class="section-label" style="margin-bottom: 6px;">
				NHẬT KÝ ĐỒNG BỘ (SYNC_LOGS TRONG AKUNARCH.DB · {syncLogs.length})
			</div>
			<div class="items-scroll">
				{#if syncLogs.length === 0}
					<div style="color: var(--text-muted); font-size: 12px; padding: 12px 0;">
						Chưa có lượt đẩy nào được ghi nhận.
					</div>
				{:else}
					{#each syncLogs as lg (lg.id)}
						<div class="ov-item-row">
							<div style="display: flex; justify-content: space-between; font-size: 12px;">
								<strong class="mono">{lg.payload_summary.slug ?? `Project #${lg.project_id}`}</strong>
								<span class="mono tabular" style="color: var(--text-muted)">{lg.created_at}</span>
							</div>
							<div class="mono" style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
								→ {lg.target_url} · force_draft={String(lg.payload_summary.force_draft ?? true)}
							</div>
						</div>
					{/each}
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	.sync-layout {
		display: grid;
		grid-template-columns: 1fr 1.08fr;
		gap: 12px;
		height: 100%;
		min-height: 0;
	}
	.sync-left,
	.sync-right {
		display: flex;
		flex-direction: column;
		gap: 12px;
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}
	.auth-drawer {
		margin-top: 8px;
		padding: 10px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line-strong);
	}
	.err-banner {
		margin-top: 8px;
		padding: 9px 11px;
		border-radius: var(--radius-sm);
		background: rgba(250, 176, 5, 0.12);
		border: 1px solid rgba(250, 176, 5, 0.4);
		color: #ffe066;
		font-size: 12px;
	}
	.overview-kpis {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
		margin-top: 10px;
	}
	.ov-stat {
		padding: 9px 11px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
		display: flex;
		flex-direction: column;
	}
	.ov-num {
		font-size: 18px;
		font-weight: 800;
		color: var(--brass-bright);
	}
	.ov-lbl {
		font-size: 11.5px;
		color: var(--text-secondary);
	}
	.items-scroll {
		flex: 1;
		overflow: auto;
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin-top: 8px;
	}
	.ov-item-row {
		padding: 8px 10px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid rgba(255, 255, 255, 0.07);
	}
	.qa-findings {
		display: flex;
		flex-direction: column;
		gap: 5px;
		margin-top: 8px;
	}
	.qa-row {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 9px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		font-size: 12px;
	}
	.payload-box {
		flex: 1;
		min-height: 110px;
		overflow: auto;
		margin: 0;
		padding: 9px;
		border-radius: var(--radius-sm);
		background: #080a10;
		border: 1px solid var(--brass-line);
		color: #99e9f2;
	}
	.empty-center {
		margin: auto;
		text-align: center;
		color: var(--text-muted);
		padding: 24px;
	}
</style>
