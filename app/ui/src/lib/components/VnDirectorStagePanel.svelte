<script lang="ts">
	import { untrack } from 'svelte';
	import { api, fileToBase64, isTauriRuntime, mediaUrl } from '$lib/ipc';
	import { acquireStage, RELEASE_WEBGL_VRAM_EVENT, type StageLease } from '$lib/webgl/webgl-stage';
	import { createOnDemandLoop } from '$lib/webgl/on-demand-loop';
	import { disposeComposer, disposeObject3DDeep } from '$lib/webgl/dispose';
	import { getSharedKtx2Loader } from '$lib/webgl/ktx2';
	import { inverseAcesFilmic } from '$lib/webgl/stage-quality';
	import type {
		CreateProjectInput,
		ProjectRecord,
		VnChoiceOption,
		VnDialogueNode,
		VnEpisodeDocument,
		VnHotspot,
		VnLintIssue
	} from '$lib/types';

	interface Props {
		projects: ProjectRecord[];
		selectedSlug: string | null;
		lastFinishedGpuCount: number;
		onSelectSlug: (slug: string) => void;
		onCreateProject: (input: CreateProjectInput) => Promise<void>;
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
		lastFinishedGpuCount,
		onSelectSlug,
		onCreateProject,
		onProjectMutated,
		onEnqueueGpuForProject,
		onJumpToSync,
		onNotify
	}: Props = $props();

	const VI_PRESET_VOICES = [
		'Thùy Dung',
		'Minh Triết',
		'Mỹ Duyên',
		'Thái Sơn',
		'Kim Thanh',
		'Thục Đoan',
		'Đức Trí'
	];
	const EN_PRESET_VOICES = ['female', 'male', 'narrator', 'elder', 'whisper'];

	let vnProjects = $derived.by(() =>
		projects.filter(
			(p) =>
				p.manifest.kind === 'vn_episode' ||
				p.manifest.kind === 'clockwork' ||
				Boolean(p.manifest.stage_vn.episode_zip_path)
		)
	);
	let glbProjects = $derived.by(() => projects.filter((p) => Boolean(p.manifest.clockwork.glb_path)));

	let activeProject = $derived.by(() => {
		const exact = vnProjects.find((p) => p.slug === selectedSlug);
		if (exact) return exact;
		const firstDedicated = vnProjects.find((p) => p.manifest.kind === 'vn_episode');
		return firstDedicated ?? vnProjects[0] ?? null;
	});

	let episode = $state<VnEpisodeDocument | null>(null);
	let selectedNodeId = $state<string>('n01_arrival');
	let lintIssues = $state<VnLintIssue[]>([]);
	let loadingEp = $state(false);
	let savingEp = $state(false);

	// Stage mode: 'rig3d' (3D Monument Camera Rig) | 'play' (Interactive VN Player Preview)
	let stageViewMode = $state<'rig3d' | 'play'>('play');
	let previewLang = $state<'vi' | 'en'>('vi');
	let playNodeId = $state<string>('n01_arrival');
	let inspectedHotspot = $state<VnHotspot | null>(null);
	let unlockedTips = $state<string[]>([]);
	let unlockedShards = $state<string[]>([]);
	let showTipsDrawer = $state(false);

	// Right inspector tab
	let rightTab = $state<'node' | 'cast' | 'codex'>('node');

	// New VN project quick modal
	let showCreateVn = $state(false);
	let newVnSlug = $state('vn-zyberon-sanctum-prelude');
	let newVnTitleVi = $state('Tiếng Vọng Thánh Điện Zyberon');
	let newVnTitleEn = $state('Echoes of the Zyberon Sanctum');

	// Audio players & BYOA inputs
	let voiceAudioEl = $state<HTMLAudioElement | null>(null);
	let bgmAudioEl = $state<HTMLAudioElement | null>(null);
	let backdropUploadEl = $state<HTMLInputElement | null>(null);
	let voiceUploadEl = $state<HTMLInputElement | null>(null);
	let portraitUploadEl = $state<HTMLInputElement | null>(null);
	let uploadingVoiceLang = $state<'vi' | 'en'>('vi');
	let uploadingCastIdx = $state(0);

	// 3D Rig Viewport
	let rigCanvasHost = $state<HTMLDivElement | null>(null);
	let rigCtrl: {
		captureBackdropDataUrl: () => { beauty: string; depth: string } | null;
		syncRigFromCamera: () => void;
	} | null = null;

	let selectedNode = $derived.by(() => {
		if (!episode || episode.nodes.length === 0) return null;
		return episode.nodes.find((n) => n.id === selectedNodeId) ?? episode.nodes[0];
	});

	let playNode = $derived.by(() => {
		if (!episode || episode.nodes.length === 0) return null;
		return episode.nodes.find((n) => n.id === playNodeId) ?? episode.nodes[0];
	});

	let liveClientLintIssues = $derived.by(() => {
		if (!episode) return [];
		const out: VnLintIssue[] = [];
		const checkViEn = (loc: string, vi: string, en: string) => {
			if (vi.includes('—')) {
				out.push({
					severity: 'blocker',
					rule_code: 'RULE_36_NO_EM_DASH',
					location: loc,
					message: `Cấm dấu gạch ngang dài '—' tại ${loc}`
				});
			}
			if (/(^|[^\p{L}\p{N}])ạ($|[^\p{L}\p{N}])/iu.test(vi)) {
				out.push({
					severity: 'blocker',
					rule_code: 'RULE_36_NO_PARTICLE_A',
					location: loc,
					message: `Cấm trợ từ 'ạ' trái phương ngữ Nam Bộ tại ${loc}`
				});
			}
			const combined = `${vi}\n${en}`.toLowerCase();
			for (const term of [
				'lượng tử',
				'quantum',
				'entropy',
				'relativity',
				'spacetime',
				'wavefunction',
				'nietzsche',
				'kant',
				'trang tử',
				'steins;gate'
			]) {
				if (combined.includes(term)) {
					out.push({
						severity: 'blocker',
						rule_code: 'RULE_34_SUBTEXT_ONLY',
						location: loc,
						message: `Cấm thuật ngữ hiện đại / tên riêng ngoại lai '${term}' tại ${loc}`
					});
				}
			}
		};
		checkViEn('synopsis', episode.synopsis_vi, episode.synopsis_en);
		for (const n of episode.nodes) {
			checkViEn(`node:${n.id}`, n.text_vi, n.text_en);
		}
		return out;
	});

	let sourceGlbPathForRig = $derived.by(() => {
		if (!episode) return activeProject?.manifest.clockwork.glb_path ?? null;
		const srcSlug = episode.camera_rig.source_slug;
		if (srcSlug) {
			const hit = projects.find((p) => p.slug === srcSlug);
			if (hit?.manifest.clockwork.glb_path) return hit.manifest.clockwork.glb_path;
		}
		return activeProject?.manifest.clockwork.glb_path ?? glbProjects[0]?.manifest.clockwork.glb_path ?? null;
	});

	async function loadEpisodeForSlug(slug: string) {
		if (!isTauriRuntime()) return;
		loadingEp = true;
		try {
			const loaded = await api.vnLoadEpisode(slug);
			episode = loaded;
			if (!loaded.nodes.some((n) => n.id === selectedNodeId)) {
				selectedNodeId = loaded.entry_node_id || loaded.nodes[0]?.id || 'n01_arrival';
			}
			playNodeId = loaded.entry_node_id || loaded.nodes[0]?.id || 'n01_arrival';
			unlockedTips = [...(loaded.nodes[0]?.unlock_tip_ids ?? [])];
			unlockedShards = loaded.nodes[0]?.unlock_shard_id ? [loaded.nodes[0].unlock_shard_id] : [];
			lintIssues = [];
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			loadingEp = false;
		}
	}

	$effect(() => {
		const slug = activeProject?.slug;
		const _gpuTick = lastFinishedGpuCount;
		if (!slug) return;
		untrack(() => {
			void loadEpisodeForSlug(slug);
		});
	});

	// Play voice automatically when stepping nodes in Play Preview
	$effect(() => {
		const node = playNode;
		const lang = previewLang;
		const mode = stageViewMode;
		if (mode !== 'play' || !node || !voiceAudioEl) return;
		const vPath = lang === 'vi' ? node.voice_vi_path : node.voice_en_path;
		if (vPath && vPath.trim()) {
			voiceAudioEl.src = mediaUrl(vPath);
			void voiceAudioEl.play().catch(() => {});
		}
	});

	// C2: 🧹 hoặc job GPU nặng sắp chạy → thoát rig3d (về play 2D) để nhường VRAM
	$effect(() => {
		const toPlay = () => (stageViewMode = 'play');
		window.addEventListener(RELEASE_WEBGL_VRAM_EVENT, toPlay);
		return () => window.removeEventListener(RELEASE_WEBGL_VRAM_EVENT, toPlay);
	});

	// 3D Camera Rig WebGL2 Stage when stageViewMode === 'rig3d'
	// (Kế hoạch VRAM v2 · Đợt A · A6) Renderer dùng chung + render theo nhu cầu + dọn sạch khi thoát rig3d.
	$effect(() => {
		const host = rigCanvasHost;
		const mode = stageViewMode;
		const glbPath = sourceGlbPathForRig;
		if (mode !== 'rig3d' || !host || !glbPath) return;

		let disposed = false;
		let teardown: (() => void) | null = null;

		(async () => {
			const THREE = await import('three');
			const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
			const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
			const { DRACOLoader } = await import('three/examples/jsm/loaders/DRACOLoader.js');
			const { EffectComposer } = await import('three/examples/jsm/postprocessing/EffectComposer.js');
			const { RenderPass } = await import('three/examples/jsm/postprocessing/RenderPass.js');
			const { OutputPass } = await import('three/examples/jsm/postprocessing/OutputPass.js');
			if (disposed) return;

			const w0 = host.clientWidth || 860;
			const h0 = host.clientHeight || 480;
			const dpr = () => Math.min(window.devicePixelRatio || 1, 2);
			const lease: StageLease = await acquireStage(
				host,
				{
					toneMapping: THREE.ACESFilmicToneMapping,
					toneMappingExposure: untrack(() => episode?.camera_rig.exposure ?? 1.08),
					outputColorSpace: THREE.SRGBColorSpace,
					shadowMapEnabled: false,
					pixelRatio: dpr(),
					width: w0,
					height: h0
				},
				() => teardown?.()
			);
			if (disposed) {
				lease.release();
				return;
			}
			const renderer = lease.renderer;
			const ktx2Loader = await getSharedKtx2Loader(renderer);
			if (disposed) {
				lease.release();
				return;
			}

			const scene = new THREE.Scene();
			const weather = untrack(() => episode?.camera_rig.weather ?? 'mist');
			// Cảnh vẽ qua composer → OutputPass tone-map ACES cả màu nền (vẽ thẳng ra canvas trước Đợt A thì không).
			// Bù ngược ACES để nền giữ đúng màu cũ (B0: #0c1522 từng bị tối thành RGB 2,6,16).
			const bgLinear = new THREE.Color(weather === 'sunset' ? '#1c1420' : '#0c1522');
			const bgColor = new THREE.Color();
			const applyBackground = (exposure: number) => {
				const [r, g, b] = inverseAcesFilmic([bgLinear.r, bgLinear.g, bgLinear.b], exposure);
				bgColor.setRGB(r, g, b, THREE.LinearSRGBColorSpace);
			};
			applyBackground(renderer.toneMappingExposure);
			scene.background = bgColor;
			scene.fog = new THREE.FogExp2(
				weather === 'sunset' ? '#251824' : '#0e1c2b',
				weather === 'clear' ? 0.004 : 0.014
			);

			const rigInit = untrack(() => episode?.camera_rig);
			const camera = new THREE.PerspectiveCamera(
				rigInit?.fov_deg ?? 36,
				w0 / Math.max(1, h0),
				0.1,
				600
			);
			camera.position.set(rigInit?.pos[0] ?? 0, rigInit?.pos[1] ?? 4.8, rigInit?.pos[2] ?? 15.2);

			const controls = new OrbitControls(camera, renderer.domElement);
			controls.enableDamping = true;
			controls.target.set(rigInit?.target[0] ?? 0, rigInit?.target[1] ?? 3.4, rigInit?.target[2] ?? 0);

			const hemi = new THREE.HemisphereLight('#bfdfff', '#231f1a', 1.2);
			scene.add(hemi);
			const key = new THREE.DirectionalLight(weather === 'sunset' ? '#ffbe82' : '#fff0d4', 2.6);
			key.position.set(16, 26, 18);
			scene.add(key);

			// Canvas dùng chung không bật antialias → khử răng cưa bằng render target MSAA 4× + OutputPass
			// (OutputPass áp tone mapping ACES + sRGB như khi vẽ thẳng ra canvas trước đây).
			const msaaTarget = new THREE.WebGLRenderTarget(Math.round(w0 * dpr()), Math.round(h0 * dpr()), {
				type: THREE.HalfFloatType,
				samples: 4
			});
			const composer = new EffectComposer(renderer, msaaTarget);
			// RenderPass vẽ vào readBuffer; OutputPass vẽ thẳng ra màn hình → không cần bộ đệm thứ hai full-res
			composer.renderTarget2.dispose();
			const idleTarget = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType });
			idleTarget.setSize = () => {};
			composer.renderTarget2 = idleTarget;
			composer.readBuffer = msaaTarget;
			composer.writeBuffer = idleTarget;
			composer.setPixelRatio(dpr());
			composer.setSize(w0, h0);
			composer.addPass(new RenderPass(scene, camera));
			const outputPass = new OutputPass();
			outputPass.needsSwap = false;
			composer.addPass(outputPass);

			const loop = createOnDemandLoop(() => {
				const moving = controls.update();
				composer.render();
				return moving;
			});
			const requestRender = () => loop.invalidate();
			controls.addEventListener('change', requestRender);

			const draco = new DRACOLoader();
			draco.setDecoderPath('/draco/');
			const loader = new GLTFLoader();
			loader.setDRACOLoader(draco);
			loader.setKTX2Loader(ktx2Loader);
			loader.load(
				mediaUrl(glbPath),
				(gltf) => {
					if (disposed) {
						// Về muộn sau khi đã thoát rig3d → dọn ngay, không gắn vào cảnh
						disposeObject3DDeep(gltf.scene);
						return;
					}
					scene.add(gltf.scene);
					requestRender();
				},
				undefined,
				() => {}
			);

			const ro = new ResizeObserver(() => {
				if (disposed || !lease.active) return;
				const w = Math.max(320, host.clientWidth);
				const h = Math.max(200, host.clientHeight);
				camera.aspect = w / h;
				camera.updateProjectionMatrix();
				renderer.setSize(w, h);
				composer.setSize(w, h);
				requestRender();
			});
			ro.observe(host);

			rigCtrl = {
				syncRigFromCamera: () => {
					if (!episode) return;
					episode.camera_rig.pos = [
						Math.round(camera.position.x * 100) / 100,
						Math.round(camera.position.y * 100) / 100,
						Math.round(camera.position.z * 100) / 100
					];
					episode.camera_rig.target = [
						Math.round(controls.target.x * 100) / 100,
						Math.round(controls.target.y * 100) / 100,
						Math.round(controls.target.z * 100) / 100
					];
				},
				captureBackdropDataUrl: () => {
					const w = 2560;
					const h = 1440;
					const prevAspect = camera.aspect;
					const prevW = Math.max(320, host.clientWidth);
					const prevH = Math.max(200, host.clientHeight);
					renderer.setPixelRatio(1);
					renderer.setSize(w, h, false);
					composer.setPixelRatio(1);
					composer.setSize(w, h);
					camera.aspect = w / h;
					camera.fov = episode?.camera_rig.fov_deg ?? 36;
					camera.updateProjectionMatrix();
					renderer.toneMappingExposure = episode?.camera_rig.exposure ?? 1.08;
				applyBackground(renderer.toneMappingExposure);

					// render rồi toDataURL ngay trong cùng tác vụ → không cần preserveDrawingBuffer
					composer.render();
					const beauty = renderer.domElement.toDataURL('image/png');

					const prevMat = scene.overrideMaterial;
					const depthMat = new THREE.MeshDepthMaterial();
					scene.overrideMaterial = depthMat;
					renderer.setRenderTarget(null);
					renderer.render(scene, camera);
					const depth = renderer.domElement.toDataURL('image/png');
					scene.overrideMaterial = prevMat;
					depthMat.dispose();

					renderer.setPixelRatio(dpr());
					renderer.setSize(prevW, prevH, false);
					composer.setPixelRatio(dpr());
					composer.setSize(prevW, prevH);
					camera.aspect = prevAspect;
					camera.updateProjectionMatrix();
					requestRender();
					return { beauty, depth };
				}
			};

			let tornDown = false;
			teardown = () => {
				if (tornDown) return;
				tornDown = true;
				rigCtrl = null;
				loop.dispose();
				ro.disconnect();
				controls.removeEventListener('change', requestRender);
				controls.dispose();
				disposeObject3DDeep(scene);
				disposeComposer(composer);
				msaaTarget.dispose();
				idleTarget.dispose();
				draco.dispose();
				lease.release();
			};
			requestRender();
		})().catch((err) => {
			console.error('[vn-rig3d] Lỗi dựng sân khấu 3D:', err);
			teardown?.();
		});

		return () => {
			disposed = true;
			teardown?.();
		};
	});

	async function handleSaveEpisode() {
		if (!activeProject || !episode) return;
		savingEp = true;
		try {
			rigCtrl?.syncRigFromCamera();
			const res = await api.vnSaveEpisode(activeProject.slug, episode);
			episode = res.episode;
			lintIssues = res.lint_issues;
			await onProjectMutated(res.project, `Đã lưu kịch bản VN '${episode.title_vi}'.`);
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			savingEp = false;
		}
	}

	async function handlePackVnZip() {
		if (!activeProject || !episode) return;
		savingEp = true;
		try {
			await api.vnSaveEpisode(activeProject.slug, episode);
			const packed = await api.vnPackEpisode(activeProject.slug);
			lintIssues = packed.lint_issues;
			await onProjectMutated(
				packed.project,
				`Đã đóng gói ${packed.zip_path} (${packed.bundled_files_count} tệp lồng tiếng/phông nền · ${Math.round(packed.size_bytes / 1024)} KB).`
			);
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			savingEp = false;
		}
	}

	async function handleCaptureRigToNodeBackdrop() {
		if (!activeProject || !episode || !selectedNode || !rigCtrl) return;
		savingEp = true;
		try {
			rigCtrl.syncRigFromCamera();
			const cap = rigCtrl.captureBackdropDataUrl();
			if (!cap) return;
			const savedPlate = await api.projectsSaveMangaPlates(
				activeProject.slug,
				2560,
				1440,
				cap.beauty,
				cap.depth,
				`vn_${selectedNode.id}`
			);
			selectedNode.backdrop_path = savedPlate.beauty_plate_path;
			if (!episode.default_backdrop_path) {
				episode.default_backdrop_path = savedPlate.beauty_plate_path;
			}
			const res = await api.vnSaveEpisode(activeProject.slug, episode);
			episode = res.episode;
			await onProjectMutated(
				res.project,
				`Đã chụp Camera Rig 3D 2K và gắn làm bối cảnh cho node '${selectedNode.id}'.`
			);
			stageViewMode = 'play';
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			savingEp = false;
		}
	}

	async function handleSynthesizeLine(lang: 'vi' | 'en') {
		if (!activeProject || !episode || !selectedNode) return;
		await handleSaveEpisode();
		const speaker = episode.cast.find((c) => c.id === selectedNode.speaker_id);
		const text = lang === 'vi' ? selectedNode.text_vi : selectedNode.text_en;
		const voice = lang === 'vi' ? (speaker?.voice_vi ?? 'Thùy Dung') : (speaker?.voice_en ?? 'female');
		if (!text.trim()) {
			onNotify('Lời thoại đang trống, hãy nhập nội dung trước khi lồng tiếng.', true);
			return;
		}
		await onEnqueueGpuForProject(
			activeProject,
			'tts',
			{
				mode: 'tts_synthesize',
				project_slug: activeProject.slug,
				batch_episode: false,
				node_id: selectedNode.id,
				lang,
				text,
				voice
			},
			`Lồng tiếng ${lang.toUpperCase()} (${lang === 'vi' ? 'VieNeu-TTS' : 'OmniVoice'}) cho ${selectedNode.id}`
		);
	}

	async function handleSynthesizeAllBatch() {
		if (!activeProject || !episode) return;
		await handleSaveEpisode();
		await onEnqueueGpuForProject(
			activeProject,
			'tts',
			{
				mode: 'tts_synthesize',
				project_slug: activeProject.slug,
				batch_episode: true
			},
			`Lồng tiếng trọn bộ VI + EN (${episode.nodes.length} cảnh)`
		);
	}

	function addDialogueNode() {
		if (!episode) return;
		const nextIdx = episode.nodes.length + 1;
		const id = `n${String(nextIdx).padStart(2, '0')}_scene`;
		const newNode: VnDialogueNode = {
			id,
			speaker_id: episode.cast[0]?.id ?? 'narrator',
			expression: 'calm',
			text_vi: 'Gió chiều thổi nhẹ qua hàng cột đá cổ, để lại tiếng ngân thanh thoát.',
			text_en: 'Evening breeze drifts gently past the ancient stone columns, leaving a clear resonance.',
			backdrop_path: episode.default_backdrop_path,
			voice_vi_path: null,
			voice_en_path: null,
			bgm_override_path: null,
			next_node_id: null,
			choices: [],
			hotspots: [],
			unlock_tip_ids: [],
			unlock_shard_id: null
		};
		episode.nodes = [...episode.nodes, newNode];
		selectedNodeId = id;
	}

	function addChoiceToSelectedNode() {
		if (!selectedNode || !episode) return;
		const target = episode.nodes[episode.nodes.length - 1]?.id ?? selectedNode.id;
		const ch: VnChoiceOption = {
			id: `ch_${Date.now()}`,
			label_vi: 'Bước lại gần lắng nghe tiếng mạch ngầm',
			label_en: 'Step closer to listen to the subterranean pulse',
			target_node_id: target,
			grant_shard_id: null
		};
		selectedNode.choices = [...selectedNode.choices, ch];
		selectedNode.next_node_id = null;
	}

	function addHotspotToSelectedNode() {
		if (!selectedNode) return;
		const hs: VnHotspot = {
			id: `hs_${Date.now()}`,
			x_pct: 50,
			y_pct: 45,
			label_vi: 'Dấu Khắc Cổ Vật',
			label_en: 'Relic Inscription',
			inspect_vi: 'Nét chạm khắc đồng xanh còn sáng rõ dưới lớp sương mỏng.',
			inspect_en: 'The bronze engraving remains vivid beneath the thin mist.',
			unlock_tip_id: episode?.tips[0]?.id ?? null
		};
		selectedNode.hotspots = [...selectedNode.hotspots, hs];
	}

	function advancePlayNode(targetId?: string | null, shardId?: string | null) {
		if (!episode || !playNode) return;
		inspectedHotspot = null;
		const destId = targetId ?? playNode.next_node_id;
		if (shardId && !unlockedShards.includes(shardId)) {
			unlockedShards = [...unlockedShards, shardId];
		}
		if (!destId) {
			// Restart from entry node
			playNodeId = episode.entry_node_id || episode.nodes[0]?.id || playNode.id;
			return;
		}
		const nextNode = episode.nodes.find((n) => n.id === destId);
		if (nextNode) {
			playNodeId = nextNode.id;
			for (const tid of nextNode.unlock_tip_ids) {
				if (!unlockedTips.includes(tid)) unlockedTips = [...unlockedTips, tid];
			}
			if (nextNode.unlock_shard_id && !unlockedShards.includes(nextNode.unlock_shard_id)) {
				unlockedShards = [...unlockedShards, nextNode.unlock_shard_id];
			}
		}
	}

	async function handleUploadVnAsset(
		files: FileList | null,
		target: 'backdrop' | 'voice' | 'portrait'
	) {
		if (!activeProject || !episode || !files || files.length === 0) return;
		const file = files[0];
		try {
			const b64 = await fileToBase64(file);
			const kind = target === 'voice' ? 'voice' : 'concept';
			const updated = await api.projectsUploadAssetBytes(
				activeProject.slug,
				kind,
				file.name,
				b64,
				false
			);
			if (target === 'backdrop' && selectedNode) {
				const newest = updated.manifest.concept_paths[updated.manifest.concept_paths.length - 1];
				if (newest) selectedNode.backdrop_path = newest;
			} else if (target === 'voice' && selectedNode) {
				const newestAudio = updated.manifest.audio_paths[updated.manifest.audio_paths.length - 1];
				if (newestAudio) {
					if (uploadingVoiceLang === 'vi') selectedNode.voice_vi_path = newestAudio;
					else selectedNode.voice_en_path = newestAudio;
				}
			} else if (target === 'portrait' && episode.cast[uploadingCastIdx]) {
				const newest = updated.manifest.concept_paths[updated.manifest.concept_paths.length - 1];
				if (newest) episode.cast[uploadingCastIdx].portrait_path = newest;
			}
			await handleSaveEpisode();
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		}
	}

	async function handleCreateNewVnProject() {
		await onCreateProject({
			slug: newVnSlug,
			title: newVnTitleVi,
			title_en: newVnTitleEn,
			kind: 'vn_episode',
			planet: 'akunalia',
			region_slug: 'zyberon-basin',
			era: 'Kỷ Nguyên Thứ Tư',
			era_year: null,
			lat: null,
			lng: null,
			biome: 'temperate',
			chunk_x: 0,
			chunk_z: 0,
			cowriter_entity_id: null,
			cowriter_key: '',
			unlock_chapter: 1,
			description_vi: 'Tập Visual Novel 3D đa nhánh lồng tiếng cục bộ phương ngữ Nam Bộ.',
			description_en: 'Branching 3D Visual Novel episode with local bilingual voice synthesis.',
			local_image_path: glbProjects[0]?.manifest.local_image_path ?? null,
			concept_paths: []
		});
		showCreateVn = false;
	}
</script>

<audio bind:this={voiceAudioEl}></audio>
<audio bind:this={bgmAudioEl} loop></audio>
<input
	bind:this={backdropUploadEl}
	type="file"
	accept=".png,.jpg,.jpeg,.webp"
	style="display:none"
	onchange={(e) => handleUploadVnAsset((e.currentTarget as HTMLInputElement).files, 'backdrop')}
/>
<input
	bind:this={voiceUploadEl}
	type="file"
	accept=".wav,.mp3,.ogg,.flac"
	style="display:none"
	onchange={(e) => handleUploadVnAsset((e.currentTarget as HTMLInputElement).files, 'voice')}
/>
<input
	bind:this={portraitUploadEl}
	type="file"
	accept=".png,.jpg,.jpeg,.webp"
	style="display:none"
	onchange={(e) => handleUploadVnAsset((e.currentTarget as HTMLInputElement).files, 'portrait')}
/>

<div class="vn-workbench" data-testid="vn-director-workbench">
	<!-- Left Column: Episode Selector & Branching Scene Graph -->
	<aside class="vn-left card">
		<div class="row-between">
			<div>
				<div class="section-label">CHẶNG 4 · VISUAL NOVEL 3D</div>
				<h3 style="margin:2px 0 0; font-size:15px;">Kịch Bản &amp; Nhánh Thoại</h3>
			</div>
			<button class="btn btn-sm btn-brass" onclick={() => (showCreateVn = !showCreateVn)}>
				+ Tập VN
			</button>
		</div>

		{#if showCreateVn}
			<div class="sub-box">
				<label class="field-lbl">
					<span>Slug tập VN</span>
					<input class="input" bind:value={newVnSlug} />
				</label>
				<label class="field-lbl" style="margin-top:5px;">
					<span>Tựa Việt (Nam Bộ)</span>
					<input class="input" bind:value={newVnTitleVi} />
				</label>
				<label class="field-lbl" style="margin-top:5px;">
					<span>Title (EN)</span>
					<input class="input" bind:value={newVnTitleEn} />
				</label>
				<button class="btn btn-sm btn-brass" style="width:100%; margin-top:8px;" onclick={handleCreateNewVnProject}>
					Khởi tạo Tập VN
				</button>
			</div>
		{/if}

		<label class="field-lbl">
			<span>Dự án đang mở</span>
			<select
				class="select"
				value={activeProject?.slug ?? ''}
				onchange={(e) => onSelectSlug((e.currentTarget as HTMLSelectElement).value)}
			>
				{#each vnProjects as vp (vp.slug)}
					<option value={vp.slug}>[{vp.manifest.kind}] {vp.title}</option>
				{/each}
			</select>
		</label>

		{#if episode}
			<!-- Live Rule #36 & Rule #34 Canon Shield -->
			<div class="sub-box">
				<div class="row-between">
					<span class="section-label">KHIÊN CANON RULE #36 &amp; #34</span>
					{#if liveClientLintIssues.length === 0 && lintIssues.length === 0}
						<span class="badge badge-ok">Chuẩn Nam Bộ · 0 lỗi</span>
					{:else}
						<span class="badge badge-err">{liveClientLintIssues.length + lintIssues.length} cảnh báo</span>
					{/if}
				</div>
				{#each liveClientLintIssues.slice(0, 3) as iss (iss.location + iss.rule_code)}
					<div style="font-size:11px; color:#ffa8a8; margin-top:4px;">• {iss.message}</div>
				{/each}
			</div>

			<div class="row-between" style="margin-top:4px;">
				<span class="section-label">DANH SÁCH CẢNH ({episode.nodes.length})</span>
				<button class="btn btn-sm" onclick={addDialogueNode}>+ Cảnh mới</button>
			</div>

			<div class="node-list">
				{#each episode.nodes as n (n.id)}
					{@const spk = episode.cast.find((c) => c.id === n.speaker_id)}
					<button
						class="node-card {selectedNodeId === n.id ? 'active' : ''}"
						onclick={() => {
							selectedNodeId = n.id;
							playNodeId = n.id;
						}}
					>
						<div class="row-between">
							<span class="mono" style="font-size:11px; color:var(--brass-bright);">{n.id}</span>
							<div style="display:flex; gap:4px;">
								{#if n.voice_vi_path}
									<span class="badge badge-ok" title="Đã có giọng VieNeu-TTS VI">VI 🔊</span>
								{/if}
								{#if n.voice_en_path}
									<span class="badge badge-cyan" title="Đã có giọng OmniVoice EN">EN 🔊</span>
								{/if}
								{#if n.choices.length > 0}
									<span class="badge badge-brass">⑂ {n.choices.length}</span>
								{/if}
							</div>
						</div>
						<strong style="font-size:12px; color:{spk?.accent_color ?? '#e9ecef'}">
							{spk?.name_vi ?? n.speaker_id}
						</strong>
						<div class="node-snippet">{n.text_vi}</div>
					</button>
				{/each}
			</div>

			<div style="margin-top:auto; display:flex; flex-direction:column; gap:6px;">
				<button class="btn btn-sm btn-cyan" onclick={handleSynthesizeAllBatch}>
					🎙️ Lồng Tiếng Trọn Bộ (VieNeu-TTS + OmniVoice)
				</button>
				<div class="grid-2">
					<button class="btn btn-sm" onclick={handleSaveEpisode} disabled={savingEp}>
						💾 Lưu Kịch Bản
					</button>
					<button class="btn btn-sm btn-brass" onclick={handlePackVnZip} disabled={savingEp}>
						📦 Đóng gói .ZIP
					</button>
				</div>
				{#if activeProject}
					<button class="btn btn-sm btn-cyan" onclick={() => onJumpToSync(activeProject.slug)}>
						🚀 Đẩy gói VN sang Selorson
					</button>
				{/if}
			</div>
		{:else if loadingEp}
			<div class="empty-hint">Đang nạp kịch bản Visual Novel...</div>
		{/if}
	</aside>

	<!-- Center: Interactive VN Stage Player & 3D Camera Rig -->
	<section class="vn-center card">
		{#if episode && playNode}
			{@const activeSpeaker = episode.cast.find((c) => c.id === playNode.speaker_id)}
			{@const backdropSrc = playNode.backdrop_path || episode.default_backdrop_path || activeProject?.manifest.local_image_path}

			<div class="row-between">
				<div style="display:flex; gap:6px; align-items:center;">
					<button
						class="btn btn-sm {stageViewMode === 'play' ? 'btn-brass' : ''}"
						onclick={() => (stageViewMode = 'play')}
					>
						🎭 Chơi Thử Sân Khấu VN
					</button>
					<button
						class="btn btn-sm {stageViewMode === 'rig3d' ? 'btn-brass' : ''}"
						onclick={() => (stageViewMode = 'rig3d')}
					>
						🎥 Camera Rig 3D (.GLB)
					</button>
				</div>

				<div style="display:flex; gap:6px; align-items:center;">
					<button
						class="btn btn-sm {previewLang === 'vi' ? 'btn-cyan' : ''}"
						onclick={() => (previewLang = 'vi')}
					>
						VI (Nam Bộ)
					</button>
					<button
						class="btn btn-sm {previewLang === 'en' ? 'btn-cyan' : ''}"
						onclick={() => (previewLang = 'en')}
					>
						EN (Global)
					</button>
					<button class="btn btn-sm" onclick={() => (showTipsDrawer = !showTipsDrawer)}>
						📚 TIPS ({unlockedTips.length}/{episode.tips.length}) · Mảnh ({unlockedShards.length}/{episode.memory_shards.length})
					</button>
				</div>
			</div>

			{#if stageViewMode === 'rig3d'}
				<div class="rig-stage-wrap">
					<div class="rig-canvas" bind:this={rigCanvasHost}></div>
					<div class="rig-controls-bar">
						<label class="field-lbl">
							<span>Nguồn Bối Cảnh .GLB</span>
							<select class="select" bind:value={episode.camera_rig.source_slug}>
								{#each glbProjects as gp (gp.slug)}
									<option value={gp.slug}>{gp.title}</option>
								{/each}
							</select>
						</label>
						<label class="field-lbl">
							<span>Tiêu cự FOV ({episode.camera_rig.fov_deg}°)</span>
							<input type="range" min="22" max="68" bind:value={episode.camera_rig.fov_deg} />
						</label>
						<label class="field-lbl">
							<span>Thời tiết</span>
							<select class="select" bind:value={episode.camera_rig.weather}>
								<option value="mist">Sương sớm (Mist)</option>
								<option value="sunset">Hoàng hôn đồng (Sunset)</option>
								<option value="clear">Quang đãng (Clear)</option>
							</select>
						</label>
						<button class="btn btn-brass" onclick={handleCaptureRigToNodeBackdrop} disabled={savingEp}>
							📸 Chụp Góc Máy 2K → Gắn Vào Cảnh '{selectedNode?.id}'
						</button>
					</div>
				</div>
			{:else}
				<!-- Playable Visual Novel Stage Preview -->
				<div class="vn-player-stage">
					{#if backdropSrc}
						<img class="vn-backdrop" src={mediaUrl(backdropSrc)} alt={episode.title_vi} />
					{:else}
						<div class="vn-backdrop-fallback"></div>
					{/if}
					<div class="vn-vignette"></div>

					<!-- Interactive Relic Hotspots -->
					{#each playNode.hotspots as hs (hs.id)}
						<button
							class="vn-hotspot-pin"
							style="left:{hs.x_pct}%; top:{hs.y_pct}%;"
							onclick={() => {
								inspectedHotspot = hs;
								if (hs.unlock_tip_id && !unlockedTips.includes(hs.unlock_tip_id)) {
									unlockedTips = [...unlockedTips, hs.unlock_tip_id];
								}
							}}
						>
							🔍 {previewLang === 'vi' ? hs.label_vi : hs.label_en}
						</button>
					{/each}

					<!-- Character Portrait Layer -->
					{#if activeSpeaker?.portrait_path}
						<img
							class="vn-portrait"
							src={mediaUrl(activeSpeaker.portrait_path)}
							alt={activeSpeaker.name_vi}
						/>
					{/if}

					<!-- Hotspot Inspection Popover -->
					{#if inspectedHotspot}
						<div class="vn-hotspot-modal">
							<div class="row-between">
								<strong style="color:var(--brass-bright)">
									🔍 {previewLang === 'vi' ? inspectedHotspot.label_vi : inspectedHotspot.label_en}
								</strong>
								<button class="btn btn-sm btn-ghost" onclick={() => (inspectedHotspot = null)}>✕</button>
							</div>
							<p style="margin:6px 0 0; font-size:13px; line-height:1.55;">
								{previewLang === 'vi' ? inspectedHotspot.inspect_vi : inspectedHotspot.inspect_en}
							</p>
						</div>
					{/if}

					<!-- TIPS & Memory Shards Drawer -->
					{#if showTipsDrawer}
						<div class="vn-codex-drawer">
							<div class="row-between">
								<strong>BÁCH KHOA TIPS &amp; MẢNH KÝ ỨC</strong>
								<button class="btn btn-sm btn-ghost" onclick={() => (showTipsDrawer = false)}>✕</button>
							</div>
							{#each episode.tips as tip (tip.id)}
								<div class="codex-entry">
									<span class="badge badge-cyan">TIP</span>
									<strong>{previewLang === 'vi' ? tip.term_vi : tip.term_en}</strong>
									<p>{previewLang === 'vi' ? tip.body_vi : tip.body_en}</p>
								</div>
							{/each}
							{#each episode.memory_shards as sh (sh.id)}
								<div class="codex-entry">
									<span class="badge badge-brass">SHARD</span>
									<strong>{previewLang === 'vi' ? sh.title_vi : sh.title_en}</strong>
									<p>{previewLang === 'vi' ? sh.echo_vi : sh.echo_en}</p>
								</div>
							{/each}
						</div>
					{/if}

					<!-- Branching Choices Overlay -->
					{#if playNode.choices.length > 0}
						<div class="vn-choices-stack">
							{#each playNode.choices as ch (ch.id)}
								<button
									class="vn-choice-btn"
									onclick={() => advancePlayNode(ch.target_node_id, ch.grant_shard_id)}
								>
									✦ {previewLang === 'vi' ? ch.label_vi : ch.label_en}
								</button>
							{/each}
						</div>
					{/if}

					<!-- VN Dialogue Glass Box -->
					<div class="vn-dialogue-box">
						<div class="row-between" style="margin-bottom:6px;">
							<div style="display:flex; align-items:center; gap:8px;">
								<span
									class="vn-speaker-pill"
									style="border-color:{activeSpeaker?.accent_color ?? '#d4a853'}; color:{activeSpeaker?.accent_color ?? '#f2cb7c'}"
								>
									{previewLang === 'vi'
										? (activeSpeaker?.name_vi ?? playNode.speaker_id)
										: (activeSpeaker?.name_en ?? playNode.speaker_id)}
								</span>
								<span class="badge mono">{playNode.expression}</span>
							</div>

							<div style="display:flex; gap:6px;">
								{#if (previewLang === 'vi' ? playNode.voice_vi_path : playNode.voice_en_path) && voiceAudioEl}
									<button
										class="btn btn-sm btn-cyan"
										onclick={() => {
											const vp = previewLang === 'vi' ? playNode.voice_vi_path : playNode.voice_en_path;
											if (vp && voiceAudioEl) {
												voiceAudioEl.src = mediaUrl(vp);
												void voiceAudioEl.play();
											}
										}}
									>
										🔊 Nghe Giọng Lồng Tiếng
									</button>
								{/if}
								{#if playNode.choices.length === 0}
									<button class="btn btn-sm btn-brass" onclick={() => advancePlayNode()}>
										{playNode.next_node_id ? 'Tiếp tục ▶' : '↺ Chơi lại từ đầu'}
									</button>
								{/if}
							</div>
						</div>

						<div class="vn-dialogue-text">
							{previewLang === 'vi' ? playNode.text_vi : playNode.text_en}
						</div>
					</div>
				</div>
			{/if}
		{/if}
	</section>

	<!-- Right Column: Node Bilingual Editor, TTS Controls, Cast & Codex -->
	<aside class="vn-right card">
		<div style="display:flex; gap:5px;">
			<button
				class="btn btn-sm {rightTab === 'node' ? 'btn-brass' : ''}"
				onclick={() => (rightTab = 'node')}
			>
				✍️ Lời Thoại &amp; TTS
			</button>
			<button
				class="btn btn-sm {rightTab === 'cast' ? 'btn-brass' : ''}"
				onclick={() => (rightTab = 'cast')}
			>
				👥 Nhân Vật ({episode?.cast.length ?? 0})
			</button>
			<button
				class="btn btn-sm {rightTab === 'codex' ? 'btn-brass' : ''}"
				onclick={() => (rightTab = 'codex')}
			>
				🔮 TIPS / Shards
			</button>
		</div>

		{#if episode && rightTab === 'node' && selectedNode}
			<div class="sub-box">
				<div class="grid-2">
					<label class="field-lbl">
						<span>Người nói</span>
						<select class="select" bind:value={selectedNode.speaker_id}>
							{#each episode.cast as c (c.id)}
								<option value={c.id}>{c.name_vi}</option>
							{/each}
						</select>
					</label>
					<label class="field-lbl">
						<span>Biểu cảm</span>
						<select class="select" bind:value={selectedNode.expression}>
							<option value="calm">Điềm tĩnh (calm)</option>
							<option value="focused">Chăm chú (focused)</option>
							<option value="warm">Ấm áp (warm)</option>
							<option value="solemn">Trang nghiêm (solemn)</option>
							<option value="surprised">Ngạc nhiên (surprised)</option>
						</select>
					</label>
				</div>

				<label class="field-lbl" style="margin-top:8px;">
					<span>Lời thoại Tiếng Việt (Phương ngữ Nam Bộ — Cấm 'ạ', Cấm '—')</span>
					<textarea class="input" rows="3" bind:value={selectedNode.text_vi}></textarea>
				</label>
				<div style="display:flex; gap:5px; margin-top:4px;">
					<button class="btn btn-sm btn-cyan" onclick={() => handleSynthesizeLine('vi')}>
						🎙️ Đúc Giọng VieNeu-TTS (VI)
					</button>
					<button
						class="btn btn-sm"
						onclick={() => {
							uploadingVoiceLang = 'vi';
							voiceUploadEl?.click();
						}}
					>
						📂 Nạp WAV VI
					</button>
				</div>

				<label class="field-lbl" style="margin-top:10px;">
					<span>English Dialogue (Subtext Only — Rule #34)</span>
					<textarea class="input" rows="3" bind:value={selectedNode.text_en}></textarea>
				</label>
				<div style="display:flex; gap:5px; margin-top:4px;">
					<button class="btn btn-sm btn-cyan" onclick={() => handleSynthesizeLine('en')}>
						🎙️ Đúc Giọng OmniVoice (EN)
					</button>
					<button
						class="btn btn-sm"
						onclick={() => {
							uploadingVoiceLang = 'en';
							voiceUploadEl?.click();
						}}
					>
						📂 Nạp WAV EN
					</button>
				</div>

				<div class="grid-2" style="margin-top:10px;">
					<label class="field-lbl">
						<span>Cảnh kế tiếp (nếu không rẽ nhánh)</span>
						<select class="select" bind:value={selectedNode.next_node_id}>
							<option value={null}>— Kết thúc nhánh —</option>
							{#each episode.nodes as n (n.id)}
								<option value={n.id}>{n.id}</option>
							{/each}
						</select>
					</label>
					<div style="display:flex; align-items:flex-end;">
						<button class="btn btn-sm" style="width:100%;" onclick={() => backdropUploadEl?.click()}>
							🖼️ Đổi ảnh nền 2K
						</button>
					</div>
				</div>
			</div>

			<!-- Branching Choices Editor -->
			<div class="sub-box">
				<div class="row-between">
					<span class="section-label">LỰA CHỌN RẼ NHÁNH ({selectedNode.choices.length})</span>
					<button class="btn btn-sm" onclick={addChoiceToSelectedNode}>+ Nhánh</button>
				</div>
				{#each selectedNode.choices as ch, idx (ch.id)}
					<div style="margin-top:6px; padding-top:6px; border-top:1px solid rgba(255,255,255,0.06);">
						<input class="input" placeholder="Lựa chọn VI" bind:value={ch.label_vi} />
						<input class="input" style="margin-top:4px;" placeholder="Choice EN" bind:value={ch.label_en} />
						<div class="row-between" style="margin-top:4px;">
							<select class="select" bind:value={ch.target_node_id}>
								{#each episode.nodes as n (n.id)}
									<option value={n.id}>→ {n.id}</option>
								{/each}
							</select>
							<button
								class="btn btn-sm btn-ghost"
								onclick={() => {
									if (selectedNode) {
										selectedNode.choices = selectedNode.choices.filter((_, i) => i !== idx);
									}
								}}
							>
								✕
							</button>
						</div>
					</div>
				{/each}
			</div>

			<!-- Hotspots Editor -->
			<div class="sub-box">
				<div class="row-between">
					<span class="section-label">ĐIỂM CHẠM SOI CỔ VẬT ({selectedNode.hotspots.length})</span>
					<button class="btn btn-sm" onclick={addHotspotToSelectedNode}>+ Hotspot</button>
				</div>
				{#each selectedNode.hotspots as hs, idx (hs.id)}
					<div style="margin-top:6px; padding-top:6px; border-top:1px solid rgba(255,255,255,0.06);">
						<div class="row-between">
							<input class="input" bind:value={hs.label_vi} />
							<button
								class="btn btn-sm btn-ghost"
								onclick={() => {
									if (selectedNode) {
										selectedNode.hotspots = selectedNode.hotspots.filter((_, i) => i !== idx);
									}
								}}
							>
								✕
							</button>
						</div>
						<textarea class="input" style="margin-top:4px;" rows="2" bind:value={hs.inspect_vi}></textarea>
					</div>
				{/each}
			</div>
		{:else if episode && rightTab === 'cast'}
			{#each episode.cast as c, idx (c.id)}
				<div class="sub-box">
					<div class="row-between">
						<strong style="color:{c.accent_color}">{c.name_vi} ({c.id})</strong>
						<button
							class="btn btn-sm"
							onclick={() => {
								uploadingCastIdx = idx;
								portraitUploadEl?.click();
							}}
						>
							🖼️ Chân dung
						</button>
					</div>
					<div class="grid-2" style="margin-top:6px;">
						<label class="field-lbl">
							<span>Giọng VieNeu-TTS (VI)</span>
							<select class="select" bind:value={c.voice_vi}>
								{#each VI_PRESET_VOICES as vv (vv)}
									<option value={vv}>{vv}</option>
								{/each}
							</select>
						</label>
						<label class="field-lbl">
							<span>Giọng OmniVoice (EN)</span>
							<select class="select" bind:value={c.voice_en}>
								{#each EN_PRESET_VOICES as ev (ev)}
									<option value={ev}>{ev}</option>
								{/each}
							</select>
						</label>
					</div>
				</div>
			{/each}
		{:else if episode && rightTab === 'codex'}
			<div class="sub-box">
				<div class="section-label">THẺ BÁCH KHOA TIPS ({episode.tips.length})</div>
				{#each episode.tips as tip (tip.id)}
					<div style="margin-top:6px;">
						<input class="input" bind:value={tip.term_vi} />
						<textarea class="input" style="margin-top:4px;" rows="2" bind:value={tip.body_vi}></textarea>
					</div>
				{/each}
			</div>
			<div class="sub-box">
				<div class="section-label">MẢNH KÝ ỨC MEMORY SHARDS ({episode.memory_shards.length})</div>
				{#each episode.memory_shards as sh (sh.id)}
					<div style="margin-top:6px;">
						<input class="input" bind:value={sh.title_vi} />
						<textarea class="input" style="margin-top:4px;" rows="2" bind:value={sh.echo_vi}></textarea>
					</div>
				{/each}
			</div>
		{/if}
	</aside>
</div>

<style>
	.vn-workbench {
		display: grid;
		grid-template-columns: 270px 1fr 315px;
		gap: 10px;
		height: 100%;
		min-height: 0;
	}
	.vn-left,
	.vn-right {
		display: flex;
		flex-direction: column;
		gap: 8px;
		overflow-y: auto;
		min-height: 0;
	}
	.vn-center {
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
	.node-list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		overflow-y: auto;
	}
	.node-card {
		text-align: left;
		padding: 8px 10px;
		border-radius: var(--radius-md);
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.07);
		cursor: pointer;
	}
	.node-card.active {
		border-color: var(--brass-bright);
		background: rgba(212, 168, 83, 0.14);
	}
	.node-snippet {
		font-size: 11.5px;
		color: var(--text-secondary);
		margin-top: 3px;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.vn-player-stage,
	.rig-stage-wrap {
		position: relative;
		flex: 1;
		min-height: 380px;
		border-radius: var(--radius-md);
		overflow: hidden;
		border: 1px solid var(--brass-line-strong);
		background: #080d16;
	}
	.rig-canvas {
		width: 100%;
		height: 100%;
	}
	.rig-controls-bar {
		position: absolute;
		left: 10px;
		right: 10px;
		bottom: 10px;
		display: flex;
		align-items: flex-end;
		gap: 10px;
		padding: 10px 12px;
		border-radius: 10px;
		background: rgba(9, 13, 22, 0.88);
		border: 1px solid var(--brass-line);
	}
	.vn-backdrop {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.vn-backdrop-fallback {
		width: 100%;
		height: 100%;
		background: radial-gradient(circle at 50% 35%, #1d2d44 0%, #090d16 75%);
	}
	.vn-vignette {
		position: absolute;
		inset: 0;
		background: linear-gradient(180deg, rgba(6, 9, 15, 0.18) 0%, rgba(6, 9, 15, 0.84) 100%);
		pointer-events: none;
	}
	.vn-portrait {
		position: absolute;
		right: 6%;
		bottom: 130px;
		max-height: 62%;
		object-fit: contain;
		filter: drop-shadow(0 12px 24px rgba(0, 0, 0, 0.7));
		pointer-events: none;
	}
	.vn-hotspot-pin {
		position: absolute;
		transform: translate(-50%, -50%);
		padding: 5px 11px;
		border-radius: 999px;
		background: rgba(16, 24, 38, 0.88);
		border: 1px solid var(--brass-bright);
		color: #f2cb7c;
		font-size: 12px;
		font-weight: 600;
		cursor: pointer;
		box-shadow: 0 0 18px rgba(212, 168, 83, 0.45);
	}
	.vn-hotspot-modal {
		position: absolute;
		top: 16px;
		left: 16px;
		max-width: 380px;
		padding: 12px 14px;
		border-radius: 10px;
		background: rgba(10, 15, 25, 0.94);
		border: 1px solid var(--brass-bright);
		z-index: 15;
	}
	.vn-codex-drawer {
		position: absolute;
		top: 16px;
		right: 16px;
		width: 340px;
		max-height: 65%;
		overflow-y: auto;
		padding: 12px;
		border-radius: 10px;
		background: rgba(10, 15, 25, 0.95);
		border: 1px solid var(--cyan-arcane);
		z-index: 16;
	}
	.codex-entry {
		margin-top: 8px;
		padding-top: 8px;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
		font-size: 12px;
	}
	.codex-entry p {
		margin: 4px 0 0;
		color: var(--text-secondary);
	}
	.vn-choices-stack {
		position: absolute;
		left: 50%;
		bottom: 168px;
		transform: translateX(-50%);
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: min(560px, 88%);
		z-index: 12;
	}
	.vn-choice-btn {
		padding: 11px 16px;
		border-radius: 10px;
		background: rgba(16, 22, 36, 0.92);
		border: 1px solid var(--brass-bright);
		color: #fff3d6;
		font-size: 13.5px;
		font-weight: 600;
		cursor: pointer;
		text-align: left;
		transition: transform 0.12s ease, background 0.12s ease;
	}
	.vn-choice-btn:hover {
		background: rgba(212, 168, 83, 0.24);
		transform: translateY(-1px);
	}
	.vn-dialogue-box {
		position: absolute;
		left: 16px;
		right: 16px;
		bottom: 14px;
		padding: 14px 18px;
		border-radius: 12px;
		background: rgba(9, 13, 22, 0.9);
		border: 1px solid var(--brass-line-strong);
		backdrop-filter: blur(8px);
		z-index: 10;
	}
	.vn-speaker-pill {
		padding: 2px 10px;
		border-radius: 999px;
		border: 1px solid;
		font-size: 12.5px;
		font-weight: 700;
		background: rgba(255, 255, 255, 0.04);
	}
	.vn-dialogue-text {
		font-size: 14.5px;
		line-height: 1.62;
		color: #f1f3f5;
		min-height: 44px;
	}
</style>
