<script lang="ts">
	import { api, mediaUrl } from '$lib/ipc';
	import type {
		AssetLibraryRow,
		ConceptBlueprintItem,
		CreateProjectInput,
		MangaEpisodeItem,
		MangaPageItem,
		SketchItem,
		StoryEntityItem,
		VaultSnapshot
	} from '$lib/types';

	interface Props {
		vault: VaultSnapshot | null;
		assets: AssetLibraryRow[];
		loadingVault: boolean;
		onRefreshVault: () => void;
		onScanAssets: () => void;
		onQuickScaffoldProject: (draft: CreateProjectInput) => void;
	}

	let {
		vault,
		assets,
		loadingVault,
		onRefreshVault,
		onScanAssets,
		onQuickScaffoldProject
	}: Props = $props();

	let activeSubTab = $state<'entities' | 'chapters' | 'sketches' | 'manga' | 'concepts' | 'assets'>(
		'entities'
	);
	let entityQuery = $state('');
	let entityKindFilter = $state('all');
	let selectedEntity = $state<StoryEntityItem | null>(null);

	let selectedEpisode = $state<MangaEpisodeItem | null>(null);
	let episodePages = $state<MangaPageItem[]>([]);
	let loadingPages = $state(false);

	let conceptFilter = $state<'canon15' | 'canon17' | 'all'>('canon15');
	let lightboxImage = $state<{ src: string; title: string; subtitle: string } | null>(null);

	let entityKinds = $derived.by(() => {
		if (!vault) return [];
		const set = new Set<string>();
		for (const e of vault.entities) {
			if (e.kind) set.add(e.kind);
		}
		return Array.from(set).sort();
	});

	let filteredEntities = $derived.by(() => {
		if (!vault) return [];
		const q = entityQuery.trim().toLowerCase();
		return vault.entities.filter((e) => {
			if (entityKindFilter !== 'all' && e.kind !== entityKindFilter) return false;
			if (!q) return true;
			return (
				e.name.toLowerCase().includes(q) ||
				e.subject_key.toLowerCase().includes(q) ||
				e.summary.toLowerCase().includes(q) ||
				e.role.toLowerCase().includes(q)
			);
		});
	});

	let filteredConcepts = $derived.by(() => {
		if (!vault) return [];
		if (conceptFilter === 'canon15') return vault.concepts.filter((c) => c.is_canon_15);
		if (conceptFilter === 'canon17') return vault.concepts.filter((c) => c.is_canon_extended);
		return vault.concepts;
	});

	async function selectMangaEpisode(ep: MangaEpisodeItem) {
		selectedEpisode = ep;
		loadingPages = true;
		try {
			episodePages = await api.vaultMangaPages(ep.id);
		} catch {
			episodePages = [];
		} finally {
			loadingPages = false;
		}
	}

	function slugifyVi(text: string): string {
		return text
			.normalize('NFD')
			.replace(/[\u0300-\u036f]/g, '')
			.replace(/đ/g, 'd')
			.replace(/Đ/g, 'D')
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '')
			.slice(0, 64);
	}

	function inferEntityPlanet(ent: StoryEntityItem): 'akunalia' | 'earth' {
		const hay = `${ent.subject_key} ${ent.name} ${ent.summary}`.toLowerCase();
		if (
			/(akunalia|zyberon|eldarin|behadona|nilanda)/.test(hay) &&
			!/(kyoto|stonehenge|avalon|camelot|olympus|samos|meru|sông hằng|dún scáith|dun-scaith|an nam|nam bộ|saqqara|eryndor|iga|khu 9)/.test(
				hay
			)
		) {
			return 'akunalia';
		}
		if (
			/(kyoto|nhật bản|stonehenge|avalon|camelot|anh quốc|olympus|samos|hy lạp|meru|sông hằng|nam ấn|dún scáith|dun-scaith|celtic|an nam|nam bộ|ai cập|saqqara|eryndor|iga|khu 9|tầng đệm|trái đất)/.test(
				hay
			)
		) {
			return 'earth';
		}
		return 'akunalia';
	}

	function scaffoldFromEntity(ent: StoryEntityItem) {
		const slug = slugifyVi(ent.subject_key.replace(/^[^:]+:/, '') || ent.name);
		const isPlaceOrRelic =
			ent.kind === 'place' ||
			ent.kind === 'location' ||
			ent.subject_key.startsWith('place:') ||
			ent.subject_key.startsWith('loc:');
		onQuickScaffoldProject({
			slug: slug || `entity-${ent.id}`,
			title: ent.name,
			title_en: '',
			kind: isPlaceOrRelic ? 'clockwork' : 'vn_episode',
			planet: inferEntityPlanet(ent),
			region_slug: '',
			era: '',
			era_year: null,
			lat: null,
			lng: null,
			biome: 'temperate',
			chunk_x: 0,
			chunk_z: 0,
			cowriter_entity_id: ent.id,
			cowriter_key: ent.subject_key,
			unlock_chapter: 1,
			description_vi: ent.summary,
			description_en: '',
			local_image_path: ent.primary_sketch_path,
			concept_paths: ent.primary_sketch_path ? [ent.primary_sketch_path] : []
		});
	}

	function scaffoldFromConcept(c: ConceptBlueprintItem) {
		onQuickScaffoldProject({
			slug: c.location_slug || slugifyVi(c.stem),
			title: c.location_title_vi || c.stem,
			title_en: '',
			kind: c.spoiler_locked ? 'vn_episode' : 'clockwork',
			planet: c.planet || 'earth',
			region_slug: '',
			era: c.era,
			era_year: null,
			lat: null,
			lng: null,
			biome: 'temperate',
			chunk_x: 0,
			chunk_z: 0,
			cowriter_entity_id: null,
			cowriter_key: `concept:${c.location_slug}`,
			unlock_chapter: 1,
			description_vi: c.architectural_note,
			description_en: '',
			local_image_path: c.spoiler_locked ? null : c.full_path,
			concept_paths: c.spoiler_locked ? [] : [c.full_path]
		});
	}

	function openSketchZoom(sk: SketchItem) {
		lightboxImage = {
			src: mediaUrl(sk.full_path),
			title: `${sk.subject} (${sk.kind})`,
			subtitle: sk.note || sk.rel_path
		};
	}
</script>

<div class="vault-wrap">
	<!-- Top Readonly Banner + KPI Strip -->
	<div class="vault-header card">
		<div class="vault-title-row">
			<div>
				<div class="section-label">PHÂN XƯỞNG 0 · VAULT &amp; BIBLE BRIDGE</div>
				<h2 style="margin: 4px 0 0; font-size: 17px;">
					Kho Thánh Tích Liên Thông Co-Writer &amp; Tools-3D
				</h2>
			</div>
			<div style="display: flex; align-items: center; gap: 8px;">
				<span class="badge badge-ok" data-testid="cowriter-ro-badge">
					🔒 SQLITE_OPEN_READ_ONLY + query_only=ON
				</span>
				<button class="btn btn-sm" onclick={onRefreshVault} disabled={loadingVault}>
					{loadingVault ? '⏳ Đang nạp...' : '🔄 Làm mới Kho'}
				</button>
			</div>
		</div>

		{#if vault}
			<div class="kpi-grid" data-testid="vault-kpi-grid">
				<button
					class="kpi-pill {activeSubTab === 'entities' ? 'active' : ''}"
					onclick={() => (activeSubTab = 'entities')}
				>
					<span class="kpi-num tabular" data-testid="kpi-entities"
						>{vault.summary.entities_count}</span
					>
					<span class="kpi-lbl">Thực thể Canon</span>
				</button>
				<button
					class="kpi-pill {activeSubTab === 'chapters' ? 'active' : ''}"
					onclick={() => (activeSubTab = 'chapters')}
				>
					<span class="kpi-num tabular" data-testid="kpi-arcs-chapters">
						{vault.summary.arcs_count} / {vault.summary.chapters_count}
					</span>
					<span class="kpi-lbl">Arcs / Chương</span>
				</button>
				<button
					class="kpi-pill {activeSubTab === 'sketches' ? 'active' : ''}"
					onclick={() => (activeSubTab = 'sketches')}
				>
					<span class="kpi-num tabular" data-testid="kpi-sketches"
						>{vault.summary.sketches_count}</span
					>
					<span class="kpi-lbl">Sketches gốc</span>
				</button>
				<button
					class="kpi-pill {activeSubTab === 'manga' ? 'active' : ''}"
					onclick={() => {
						activeSubTab = 'manga';
						if (!selectedEpisode && vault.manga_episodes.length > 0) {
							selectMangaEpisode(vault.manga_episodes[0]);
						}
					}}
				>
					<span class="kpi-num tabular" data-testid="kpi-manga">
						{vault.summary.manga_episodes_count}
						<small style="font-size: 12px; color: var(--text-secondary)"
							>({vault.summary.manga_pages_count} trang)</small
						>
					</span>
					<span class="kpi-lbl">Tập Manga</span>
				</button>
				<button
					class="kpi-pill {activeSubTab === 'concepts' ? 'active' : ''}"
					onclick={() => (activeSubTab = 'concepts')}
				>
					<span class="kpi-num tabular" data-testid="kpi-concepts">
						{vault.summary.concepts_canon_15_count}
						<small style="font-size: 12px; color: var(--text-secondary)"
							>/ {vault.summary.concepts_total_count}</small
						>
					</span>
					<span class="kpi-lbl">Concepts Chuẩn 3D</span>
				</button>
				<button
					class="kpi-pill {activeSubTab === 'assets' ? 'active' : ''}"
					onclick={() => (activeSubTab = 'assets')}
				>
					<span class="kpi-num tabular">{assets.length}</span>
					<span class="kpi-lbl">Vật liệu PBR &amp; Mesh</span>
				</button>
			</div>
		{/if}
	</div>

	<!-- Sub-tab Content -->
	<div class="vault-body">
		{#if !vault}
			<div class="card" style="text-align: center; padding: 36px;">
				{loadingVault ? 'Đang kết nối chỉ đọc tới co_writer.db...' : 'Chưa tải được Kho Thánh Tích.'}
			</div>
		{:else if activeSubTab === 'entities'}
			<div class="entities-split">
				<div class="entities-list-pane card">
					<div class="filter-bar">
						<input
							class="input"
							placeholder="Tìm trong {vault.summary.entities_count} thực thể (tên, subject_key, vai trò)..."
							bind:value={entityQuery}
						/>
						<select class="select" style="width: 170px;" bind:value={entityKindFilter}>
							<option value="all">Tất cả loại ({vault.entities.length})</option>
							{#each entityKinds as k}
								<option value={k}>{k}</option>
							{/each}
						</select>
					</div>

					<div class="scroll-list">
						{#each filteredEntities as ent (ent.id)}
							<button
								class="entity-row {selectedEntity?.id === ent.id ? 'selected' : ''}"
								onclick={() => (selectedEntity = ent)}
							>
								{#if ent.primary_sketch_path}
									<img
										src={mediaUrl(ent.primary_sketch_path)}
										alt={ent.name}
										class="entity-avatar"
										loading="lazy"
									/>
								{:else}
									<div class="entity-avatar placeholder">{ent.name.slice(0, 1)}</div>
								{/if}
								<div class="entity-meta">
									<div class="entity-name-line">
										<strong>{ent.name}</strong>
										<span class="badge">{ent.kind}</span>
										{#if ent.confirmed}
											<span class="badge badge-ok">Canon</span>
										{/if}
									</div>
									<div class="entity-sub">
										<span class="mono">{ent.subject_key}</span>
										{#if ent.role}<span>· {ent.role}</span>{/if}
									</div>
								</div>
								<span class="badge badge-brass tabular">{ent.mention_count}x</span>
							</button>
						{/each}
					</div>
				</div>

				<div class="entity-detail-pane card">
					{#if selectedEntity}
						<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;">
							<div>
								<span class="badge badge-brass">{selectedEntity.kind}</span>
								<h3 style="margin: 6px 0 2px; font-size: 18px;">{selectedEntity.name}</h3>
								<div class="mono" style="color: var(--text-muted)">
									#{selectedEntity.id} · {selectedEntity.subject_key}
								</div>
							</div>
							<button class="btn btn-brass btn-sm" onclick={() => scaffoldFromEntity(selectedEntity!)}>
								⚡ Tạo Dự Án 3D
							</button>
						</div>

						{#if selectedEntity.primary_sketch_path}
							<img
								src={mediaUrl(selectedEntity.primary_sketch_path)}
								alt={selectedEntity.name}
								class="detail-hero-img"
							/>
						{/if}

						{#if selectedEntity.role}
							<div class="detail-block">
								<div class="section-label">Vai trò</div>
								<p>{selectedEntity.role}</p>
							</div>
						{/if}
						<div class="detail-block">
							<div class="section-label">Hồ sơ Kinh Thánh Thế Giới</div>
							<p style="white-space: pre-wrap;">{selectedEntity.summary || 'Chưa có mô tả.'}</p>
						</div>
						{#if selectedEntity.visual_anchor}
							<div class="detail-block">
								<div class="section-label">Mỏ neo Thị giác (Visual Anchor)</div>
								<p style="white-space: pre-wrap;">{selectedEntity.visual_anchor}</p>
							</div>
						{/if}
						{#if selectedEntity.voice_profile}
							<div class="detail-block">
								<div class="section-label">Âm sắc Giọng nói (TTS Reference)</div>
								<p style="white-space: pre-wrap;">{selectedEntity.voice_profile}</p>
							</div>
						{/if}
					{:else}
						<div class="empty-hint">
							Chọn một thực thể bên trái để xem hồ sơ chi tiết, Visual Anchor và khởi tạo Dự án 3D / Visual Novel.
						</div>
					{/if}
				</div>
			</div>
		{:else if activeSubTab === 'chapters'}
			<div class="chapters-layout">
				<div class="card">
					<div class="section-label" style="margin-bottom: 10px;">
						7 ĐẠI MẠCH TRUYỆN (STORY ARCS)
					</div>
					<div class="arcs-grid">
						{#each vault.arcs as arc (arc.id)}
							<div class="arc-card">
								<div style="display: flex; justify-content: space-between; gap: 6px;">
									<span class="badge badge-brass">Arc {arc.ordinal}</span>
									{#if arc.chapter_start}
										<span class="badge tabular">
											Ch.{arc.chapter_start} → {arc.chapter_end ?? '∞'}
										</span>
									{/if}
								</div>
								<h4 style="margin: 6px 0 4px;">{arc.title}</h4>
								<p style="margin: 0; color: var(--text-secondary); font-size: 12.5px;">
									{arc.summary}
								</p>
							</div>
						{/each}
					</div>
				</div>

				<div class="card">
					<div class="section-label" style="margin-bottom: 10px;">
						12 KẾ HOẠCH CHƯƠNG ĐƯỜNG CHÂN TRỜI CUỘN (CHAPTER PLANS)
					</div>
					<div class="chapters-grid">
						{#each vault.chapters as ch (ch.id)}
							<div class="chapter-card">
								<div style="display: flex; flex-wrap: wrap; gap: 6px; align-items: center;">
									<span class="badge badge-brass tabular">Chương {ch.chapter_no}</span>
									{#if ch.era_label}<span class="badge badge-cyan">{ch.era_label}</span>{/if}
									{#if ch.pov_name}<span class="badge">POV: {ch.pov_name}</span>{/if}
									<span class="badge">{ch.status}</span>
								</div>
								<h4 style="margin: 7px 0 4px; font-size: 14.5px;">{ch.title}</h4>
								{#if ch.setting}
									<div style="font-size: 12px; color: var(--brass-bright); margin-bottom: 4px;">
										📍 {ch.setting} {ch.time_span ? `· ⏱ ${ch.time_span}` : ''}
									</div>
								{/if}
								{#if ch.opening_lens}
									<p style="margin: 4px 0; font-size: 12.5px; color: var(--text-secondary);">
										<strong>Ống kính mở màn:</strong> {ch.opening_lens}
									</p>
								{/if}
								{#if ch.intent}
									<p style="margin: 4px 0 0; font-size: 12.5px; color: var(--text-muted);">
										{ch.intent}
									</p>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			</div>
		{:else if activeSubTab === 'sketches'}
			<div class="card" style="height: 100%; overflow: auto;">
				<div class="section-label" style="margin-bottom: 12px;">
					KHO 46 BẢN VẼ REFERENCE SHEET &amp; SKETCHES GỐC TỪ CO-WRITER
				</div>
				<div class="media-gallery">
					{#each vault.sketches as sk (sk.id)}
						<button class="media-tile" onclick={() => openSketchZoom(sk)}>
							<div class="media-thumb-box">
								{#if sk.exists_on_disk}
									<img src={mediaUrl(sk.full_path)} alt={sk.subject} loading="lazy" />
								{:else}
									<div class="missing-thumb">Chưa có tệp</div>
								{/if}
							</div>
							<div class="media-caption">
								<strong>{sk.subject || `Sketch #${sk.id}`}</strong>
								<div style="display: flex; justify-content: space-between; margin-top: 3px;">
									<span class="badge">{sk.kind}</span>
									<span class="mono tabular" style="color: var(--text-muted)">
										{sk.width}×{sk.height}
									</span>
								</div>
							</div>
						</button>
					{/each}
				</div>
			</div>
		{:else if activeSubTab === 'manga'}
			<div class="entities-split">
				<div class="entities-list-pane card">
					<div class="section-label" style="margin-bottom: 8px;">
						13 TẬP MANGA ({vault.summary.manga_pages_count} TRANG)
					</div>
					<div class="scroll-list">
						{#each vault.manga_episodes as ep (ep.id)}
							<button
								class="entity-row {selectedEpisode?.id === ep.id ? 'selected' : ''}"
								onclick={() => selectMangaEpisode(ep)}
							>
								{#if ep.cover_full_path}
									<img
										src={mediaUrl(ep.cover_full_path)}
										alt={ep.title}
										class="entity-avatar"
										loading="lazy"
									/>
								{:else}
									<div class="entity-avatar placeholder">M</div>
								{/if}
								<div class="entity-meta">
									<div class="entity-name-line">
										<strong>{ep.title || `Episode #${ep.id}`}</strong>
									</div>
									<div class="entity-sub">
										{#if ep.chapter_no}<span>Ch.{ep.chapter_no} · </span>{/if}
										<span>{ep.style} · {ep.status}</span>
									</div>
								</div>
								<span class="badge badge-brass tabular">{ep.actual_pages_in_db} tr</span>
							</button>
						{/each}
					</div>
				</div>

				<div class="entity-detail-pane card">
					{#if selectedEpisode}
						<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
							<div>
								<h3 style="margin: 0; font-size: 16px;">{selectedEpisode.title}</h3>
								<span class="mono" style="color: var(--text-muted)">
									Episode #{selectedEpisode.id} · Phong cách: {selectedEpisode.style} · {episodePages.length} trang
								</span>
							</div>
						</div>
						{#if loadingPages}
							<p>Đang tải danh sách trang Manga...</p>
						{:else}
							<div class="manga-pages-grid">
								{#each episodePages as pg (pg.id)}
									<button
										class="media-tile"
										onclick={() =>
											(lightboxImage = {
												src: mediaUrl(pg.full_path),
												title: `${selectedEpisode?.title} — Trang ${pg.page_no}`,
												subtitle: pg.pacing_note || pg.layout_style
											})}
									>
										<div class="media-thumb-box portrait">
											{#if pg.exists_on_disk}
												<img
													src={mediaUrl(pg.full_path)}
													alt="Trang {pg.page_no}"
													loading="lazy"
												/>
											{:else}
												<div class="missing-thumb">Tr.{pg.page_no}</div>
											{/if}
										</div>
										<div class="media-caption">
											<strong>Trang {pg.page_no}</strong>
											{#if pg.title}
												<div style="font-size: 11px; color: var(--text-secondary)">
													{pg.title}
												</div>
											{/if}
										</div>
									</button>
								{/each}
							</div>
						{/if}
					{:else}
						<div class="empty-hint">Chọn một tập Manga bên trái để duyệt các trang phân cảnh.</div>
					{/if}
				</div>
			</div>
		{:else if activeSubTab === 'concepts'}
			<div class="card" style="height: 100%; overflow: auto;">
				<div
					style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 12px;"
				>
					<div>
						<div class="section-label">BỘ BẢN VẼ CONCEPT KIẾN TRÚC 3D TẠI E:\Tools-3D\concepts\</div>
						<div style="font-size: 12px; color: var(--text-secondary);">
							Khóa chuẩn thẩm mỹ chiếu màu trực giao <code>project_concept_albedo_onto_hero_mesh()</code> &amp; quy tắc Zero-Spoiler.
						</div>
					</div>
					<div style="display: flex; gap: 6px;">
						<button
							class="btn btn-sm {conceptFilter === 'canon15' ? 'btn-brass' : ''}"
							onclick={() => (conceptFilter = 'canon15')}
						>
							★ 15 Concept Chuẩn Duyệt (v2–v6)
						</button>
						<button
							class="btn btn-sm {conceptFilter === 'canon17' ? 'btn-brass' : ''}"
							onclick={() => (conceptFilter = 'canon17')}
						>
							Khóa Canon Đầy Đủ ({vault.summary.concepts_canon_extended_count})
						</button>
						<button
							class="btn btn-sm {conceptFilter === 'all' ? 'btn-brass' : ''}"
							onclick={() => (conceptFilter = 'all')}
						>
							Tất cả Kho ({vault.summary.concepts_total_count})
						</button>
					</div>
				</div>

				<div class="concepts-grid">
					{#each filteredConcepts as c (c.filename)}
						<div class="concept-card">
							<button
								class="concept-img-btn"
								onclick={() =>
									(lightboxImage = {
										src: mediaUrl(c.full_path),
										title: `${c.location_title_vi} — ${c.filename}`,
										subtitle: c.architectural_note
									})}
							>
								<img src={mediaUrl(c.full_path)} alt={c.filename} loading="lazy" />
							</button>
							<div class="concept-body">
								<div style="display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 5px;">
									{#if c.is_canon_15}
										<span class="badge badge-brass">★ Chuẩn 15</span>
									{/if}
									<span class="badge {c.planet === 'earth' ? 'badge-warn' : 'badge-cyan'}">
										{c.planet === 'earth' ? 'Trái Đất' : 'Akunalia'}
									</span>
									{#if c.era}<span class="badge">{c.era}</span>{/if}
									{#if c.spoiler_locked}
										<span class="badge badge-err">⚠️ Zero-Spoiler Lock</span>
									{/if}
								</div>
								<strong style="display: block; font-size: 13px;">{c.location_title_vi}</strong>
								<div class="mono" style="color: var(--text-muted); font-size: 11px; margin: 2px 0 6px;">
									{c.filename}
								</div>
								<p style="margin: 0 0 10px; font-size: 12px; color: var(--text-secondary); flex: 1;">
									{c.architectural_note}
								</p>
								<button class="btn btn-sm" style="width: 100%;" onclick={() => scaffoldFromConcept(c)}>
									⚡ Khởi tạo Dự Án từ Concept này
								</button>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{:else if activeSubTab === 'assets'}
			<div class="card" style="height: 100%; overflow: auto;">
				<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
					<div>
						<div class="section-label">ASSET LIBRARY (POLY HAVEN 2K PBR &amp; AI HERO MESHES)</div>
						<div style="font-size: 12px; color: var(--text-secondary);">
							Đã lập chỉ mục vào bảng <code>asset_library</code> trong <code>akunarch.db</code>.
						</div>
					</div>
					<button class="btn btn-sm btn-brass" onclick={onScanAssets}>
						🔄 Quét lại Poly Haven &amp; AI Meshes
					</button>
				</div>

				{#if assets.length === 0}
					<div class="empty-hint">Chưa có tài nguyên nào trong asset_library.</div>
				{:else}
					<div class="arcs-grid">
						{#each assets as a (a.id)}
							<div class="arc-card">
								<div style="display: flex; justify-content: space-between; align-items: center;">
									<span class="badge badge-brass">{a.category}</span>
									{#if a.license_clean}<span class="badge badge-ok">CC0 / Clean</span>{/if}
								</div>
								<strong style="display: block; margin-top: 6px;">{a.slug}</strong>
								<div class="mono" style="color: var(--text-muted); word-break: break-all; margin-top: 4px;">
									{a.file_path}
								</div>
								<div style="margin-top: 6px; font-size: 11.5px; color: var(--text-secondary);">
									Dung lượng: {(a.byte_size / (1024 * 1024)).toFixed(2)} MB
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>

{#if lightboxImage}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="modal-backdrop" onclick={() => (lightboxImage = null)}>
		<div class="modal-box" onclick={(e) => e.stopPropagation()}>
			<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
				<div>
					<h3 style="margin: 0;">{lightboxImage.title}</h3>
					<div style="font-size: 12px; color: var(--text-secondary);">{lightboxImage.subtitle}</div>
				</div>
				<button class="btn btn-sm" onclick={() => (lightboxImage = null)}>✕ Đóng</button>
			</div>
			<img
				src={lightboxImage.src}
				alt={lightboxImage.title}
				style="max-width: 100%; max-height: 75vh; display: block; margin: 0 auto; border-radius: 8px;"
			/>
		</div>
	</div>
{/if}

<style>
	.vault-wrap {
		display: flex;
		flex-direction: column;
		gap: 12px;
		height: 100%;
		overflow: hidden;
	}
	.vault-title-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		margin-bottom: 12px;
	}
	.kpi-grid {
		display: grid;
		grid-template-columns: repeat(6, minmax(0, 1fr));
		gap: 8px;
	}
	.kpi-pill {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		padding: 9px 12px;
		border-radius: var(--radius-sm);
		border: 1px solid var(--brass-line);
		background: var(--obs-base);
		cursor: pointer;
		text-align: left;
		transition: all 0.14s ease;
	}
	.kpi-pill:hover,
	.kpi-pill.active {
		border-color: var(--brass-bright);
		background: rgba(212, 168, 83, 0.11);
	}
	.kpi-num {
		font-size: 18px;
		font-weight: 800;
		color: var(--brass-bright);
	}
	.kpi-lbl {
		font-size: 11.5px;
		color: var(--text-secondary);
	}
	.vault-body {
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}
	.entities-split {
		display: grid;
		grid-template-columns: 1.15fr 1fr;
		gap: 12px;
		height: 100%;
	}
	.entities-list-pane,
	.entity-detail-pane {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}
	.entity-detail-pane {
		overflow: auto;
	}
	.filter-bar {
		display: flex;
		gap: 8px;
		margin-bottom: 10px;
	}
	.scroll-list {
		flex: 1;
		overflow: auto;
		display: flex;
		flex-direction: column;
		gap: 5px;
		padding-right: 4px;
	}
	.entity-row {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 10px;
		border-radius: var(--radius-sm);
		border: 1px solid rgba(255, 255, 255, 0.06);
		background: var(--obs-base);
		cursor: pointer;
		text-align: left;
	}
	.entity-row:hover,
	.entity-row.selected {
		border-color: var(--brass-bright);
		background: rgba(212, 168, 83, 0.1);
	}
	.entity-avatar {
		width: 40px;
		height: 40px;
		border-radius: 6px;
		object-fit: cover;
		flex-shrink: 0;
		border: 1px solid var(--brass-line);
	}
	.entity-avatar.placeholder {
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--obs-elevated);
		color: var(--brass-bright);
		font-weight: 700;
	}
	.entity-meta {
		flex: 1;
		min-width: 0;
	}
	.entity-name-line {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
	}
	.entity-sub {
		font-size: 11.5px;
		color: var(--text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.detail-hero-img {
		width: 100%;
		max-height: 240px;
		object-fit: contain;
		background: #080a10;
		border-radius: 8px;
		border: 1px solid var(--brass-line);
		margin: 10px 0;
	}
	.detail-block {
		margin-top: 12px;
		padding-top: 10px;
		border-top: 1px solid rgba(255, 255, 255, 0.07);
	}
	.detail-block p {
		margin: 4px 0 0;
		color: var(--text-secondary);
	}
	.empty-hint {
		margin: auto;
		text-align: center;
		color: var(--text-muted);
		padding: 32px;
	}
	.chapters-layout {
		height: 100%;
		overflow: auto;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.arcs-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
		gap: 10px;
	}
	.arc-card,
	.chapter-card {
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
		border-radius: var(--radius-sm);
		padding: 11px;
	}
	.chapters-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
		gap: 10px;
	}
	.media-gallery {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(185px, 1fr));
		gap: 10px;
	}
	.manga-pages-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(145px, 1fr));
		gap: 10px;
		overflow: auto;
	}
	.media-tile {
		display: flex;
		flex-direction: column;
		padding: 0;
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
		border-radius: var(--radius-sm);
		overflow: hidden;
		cursor: pointer;
		text-align: left;
	}
	.media-tile:hover {
		border-color: var(--brass-bright);
	}
	.media-thumb-box {
		width: 100%;
		height: 145px;
		background: #07090e;
		overflow: hidden;
	}
	.media-thumb-box.portrait {
		height: 200px;
	}
	.media-thumb-box img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.media-caption {
		padding: 8px;
		font-size: 12px;
	}
	.missing-thumb {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100%;
		color: var(--text-muted);
		font-size: 11px;
	}
	.concepts-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(275px, 1fr));
		gap: 12px;
	}
	.concept-card {
		display: flex;
		flex-direction: column;
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
		border-radius: var(--radius-md);
		overflow: hidden;
	}
	.concept-img-btn {
		padding: 0;
		border: none;
		background: #07090e;
		height: 175px;
		cursor: zoom-in;
		overflow: hidden;
	}
	.concept-img-btn img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.concept-body {
		padding: 11px;
		display: flex;
		flex-direction: column;
		flex: 1;
	}
</style>
