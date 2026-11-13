<script lang="ts">
	import { untrack } from 'svelte';
	import { api, isTauriRuntime, mediaUrl } from '$lib/ipc';
	import type { ClockworkPartMeta, MangaPlateCapture } from '$lib/types';
	import { acquireStage, type StageLease } from '$lib/webgl/webgl-stage';
	import { createOnDemandLoop, type OnDemandLoop } from '$lib/webgl/on-demand-loop';
	import { disposeComposer, disposeObject3DDeep } from '$lib/webgl/dispose';
	import { getSharedKtx2Loader } from '$lib/webgl/ktx2';
	import { pbrPixelRatio } from '$lib/webgl/stage-quality';
	import { stageMode } from '$lib/webgl/stage-mode.svelte';
	import { pickClockworkClips, pickStageGlb, type StageVariant } from '$lib/webgl/stage-variant';

	/** P0: điều khiển tất định cho agent chụp ảnh (window.__akunarchStage) khi .glb có animation. */
	interface StageAnimHook {
		clips: string[];
		seek: (sec: number) => void;
		play: () => void;
		pause: () => void;
	}

	interface RuntimePartItem {
		id: string;
		nameVi: string;
		nameEn: string;
		summaryVi: string;
		dir: [number, number, number];
		visible: boolean;
		yMin: number;
		yMax: number;
		polyCount: number;
	}

	interface Props {
		slug: string;
		title: string;
		titleEn?: string;
		planet?: string;
		kind?: string;
		era?: string;
		unlockChapter?: number;
		glbPath: string | null;
		partsMeta?: ClockworkPartMeta[];
		localImagePath: string | null;
		conceptPaths?: string[];
		bgmAudioPath?: string | null;
		introVideoPath?: string | null;
		mangaPlates?: MangaPlateCapture[];
		/** C2: ảnh xem trước Blender 1920×1080 (ưu tiên số 1 của thẻ Chờ 2D). */
		previewRenderPath?: string | null;
		/** P0: bản cơ khí (clip `assemble` + `idle`) — có thì hiện công tắc Bản thật / Bản cơ khí. */
		mechanismGlbPath?: string | null;
		onSculptFromConcept: (conceptPath: string | null) => void;
		onRequestImportGlb: () => void;
		onRequestPickAiMesh: () => void;
		onRequestImportConcept: () => void;
		onRequestImportAudio: () => void;
		onExportMangaPlates: (
			width: number,
			height: number,
			beautyPngDataUrl: string,
			depthPngDataUrl: string,
			label: string
		) => Promise<void>;
		onOpenSubfolder: (subfolder: string) => void;
	}

	let {
		slug,
		title,
		titleEn = '',
		planet = 'akunalia',
		kind = 'clockwork',
		era = '',
		unlockChapter = 1,
		glbPath,
		partsMeta = [],
		localImagePath,
		conceptPaths = [],
		bgmAudioPath = null,
		introVideoPath = null,
		mangaPlates = [],
		previewRenderPath = null,
		mechanismGlbPath = null,
		onSculptFromConcept,
		onRequestImportGlb,
		onRequestPickAiMesh,
		onRequestImportConcept,
		onRequestImportAudio,
		onExportMangaPlates,
		onOpenSubfolder
	}: Props = $props();

	let canvasHost = $state<HTMLDivElement | null>(null);
	let loadingGlb = $state(false);
	let loadError = $state('');
	let webglReady = $state(false);

	let explodePct = $state(0);
	let autoRotate = $state(false);
	// HD: DPR ≤ 1.0 + shadow 1536 (nhẹ VRAM) · Ultra: DPR ≤ 1.5 + shadow 2048. Chụp Manga 2K luôn ở độ phân giải gốc.
	let qualityTier = $state<'hd' | 'ultra'>('hd');
	let showWireframe = $state(false);
	let showGrid = $state(true);
	let showPartsDrawer = $state(true);
	let showIntroModal = $state(false);
	let langMode = $state<'vi' | 'en'>('vi');

	let runtimeParts = $state<RuntimePartItem[]>([]);
	let selectedPartId = $state<string | null>(null);
	let minYGapMeters = $state(0);
	let minYGap100Meters = $state(0);
	let totalPolys = $state(0);
	let activeConceptIdx = $state(0);

	// Manga 2K Reverse Export state
	let mangaPreset = $state<'landscape_2k' | 'vertical_2k'>('landscape_2k');
	let exportingPlates = $state(false);
	let latestPreview = $state<{ beauty: string; depth: string; res: string } | null>(null);

	// BGM Audio state
	let audioEl = $state<HTMLAudioElement | null>(null);
	let audioPlaying = $state(false);
	let audioLoop = $state(true);

	let allConceptList = $derived.by(() => {
		const out: string[] = [];
		if (localImagePath && localImagePath.trim()) out.push(localImagePath.trim());
		for (const cp of conceptPaths) {
			if (cp && cp.trim() && !out.includes(cp.trim())) out.push(cp.trim());
		}
		return out;
	});

	let activeConceptPath = $derived(allConceptList[activeConceptIdx] ?? allConceptList[0] ?? null);

	$effect(() => {
		// Reset concept index & transient modals when switching projects
		const _s = slug;
		untrack(() => {
			activeConceptIdx = 0;
			showIntroModal = false;
			latestPreview = null;
			audioPlaying = false;
		});
	});

	// Imperative handles into live Three.js stage so slider/visibility/export never recreate WebGL2 context
	let stageApi: {
		applyExplode: (pct: number, reframeCamera: boolean) => void;
		setPartVisible: (partId: string, visible: boolean) => void;
		highlightPart: (partId: string | null, focusCamera: boolean) => void;
		setWireframe: (wf: boolean) => void;
		setGridVisible: (gv: boolean) => void;
		setAutoRotate: (on: boolean) => void;
		resetCamera: () => void;
		captureMangaPlates2K: (w: number, h: number) => { beauty: string; depth: string } | null;
	} | null = null;

	function formatPolyCount(n: number): string {
		if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
		if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
		return String(n);
	}

	function fileBaseName(p: string | null | undefined): string {
		if (!p) return '';
		const parts = p.replace(/\\/g, '/').split('/');
		return parts[parts.length - 1] || p;
	}

	function setExplodePreset(pct: number) {
		explodePct = pct;
		stageApi?.applyExplode(pct, true);
	}

	function handleSliderInput(e: Event) {
		const val = Number((e.currentTarget as HTMLInputElement).value);
		explodePct = val;
		stageApi?.applyExplode(val, true);
	}

	function togglePartVisibility(partId: string, ev: MouseEvent) {
		ev.stopPropagation();
		const target = runtimeParts.find((p) => p.id === partId);
		if (!target) return;
		const nextVis = !target.visible;
		runtimeParts = runtimeParts.map((p) => (p.id === partId ? { ...p, visible: nextVis } : p));
		stageApi?.setPartVisible(partId, nextVis);
	}

	function selectAndFocusPart(partId: string, focusCam = false) {
		const next = selectedPartId === partId && !focusCam ? null : partId;
		selectedPartId = next;
		stageApi?.highlightPart(next, focusCam);
	}

	function toggleAudioPlay() {
		if (!audioEl) return;
		if (audioEl.paused) {
			audioEl
				.play()
				.then(() => {
					audioPlaying = true;
				})
				.catch(() => {
					audioPlaying = false;
				});
		} else {
			audioEl.pause();
			audioPlaying = false;
		}
	}

	async function handleExportManga2K() {
		if (!stageApi || exportingPlates) return;
		exportingPlates = true;
		try {
			const [w, h] = mangaPreset === 'landscape_2k' ? [2048, 1152] : [1440, 2048];
			const captured = stageApi.captureMangaPlates2K(w, h);
			if (!captured) return;
			const label = `${title} · Explode ${explodePct}% (${w}×${h})`;
			await onExportMangaPlates(w, h, captured.beauty, captured.depth, label);
			latestPreview = {
				beauty: captured.beauty,
				depth: captured.depth,
				res: `${w}×${h}`
			};
		} finally {
			exportingPlates = false;
		}
	}

	// Kế hoạch VRAM v2 · C2: thẻ Chờ 2D — ảnh preview Blender › Phông Manga mới nhất › Concept
	let standbyShowConcept = $state(false);
	let standbyConcept = $derived(localImagePath || conceptPaths[0] || null);
	let standbyPrimary = $derived(previewRenderPath || mangaPlates[0]?.beauty_path || standbyConcept);
	let standbyImage = $derived(standbyShowConcept && standbyConcept ? standbyConcept : standbyPrimary);
	let standbySource = $derived(
		standbyImage === standbyConcept && (standbyShowConcept || !previewRenderPath && !mangaPlates[0])
			? 'Ảnh Concept gốc'
			: standbyImage === previewRenderPath
				? 'Ảnh xem trước Blender (1920×1080)'
				: 'Phông nền Manga 2K mới nhất'
	);

	// C2 (b): người dùng bấm "Tạo ảnh xem trước"
	let previewQueued = $state(false);
	async function requestPreviewCard() {
		if (!activeGlbPath || previewQueued) return;
		previewQueued = true;
		try {
			await api.gpuEnqueueJob(null, 'blender', {
				mode: 'render_preview_card',
				project_slug: slug,
				glb_path: activeGlbPath
			});
		} catch {
			previewQueued = false;
		}
	}
	$effect(() => {
		void slug;
		previewQueued = false;
	});

	// C2 (c): mở dự án → ảnh xem trước thiếu hoặc cũ hơn .glb thì xếp hàng render nền (1 lần/dự án/.glb/phiên)
	const ensuredPreview = new Set<string>();
	$effect(() => {
		const key = `${slug}|${activeGlbPath}`;
		if (!activeGlbPath || !isTauriRuntime() || ensuredPreview.has(key)) return;
		ensuredPreview.add(key);
		void api.projectsEnsurePreviewCard(slug).catch(() => {});
	});

	// Đọc state TRƯỚC `stageApi?.` — nếu không, lần chạy đầu (stageApi = null) sẽ không đăng ký phụ thuộc
	// và effect không bao giờ chạy lại. Giá trị ban đầu được áp khi nạp xong qua `untrack(...)` bên dưới.
	$effect(() => {
		const wf = showWireframe;
		stageApi?.setWireframe(wf);
	});

	$effect(() => {
		const gv = showGrid;
		stageApi?.setGridVisible(gv);
	});

	$effect(() => {
		const on = autoRotate;
		stageApi?.setAutoRotate(on);
	});

	// P0: bản thật ↔ bản cơ khí (chỉ khi dự án có mechanismGlbPath)
	let stageVariant = $state<StageVariant>('real');
	let hasMechanism = $derived(Boolean(mechanismGlbPath?.trim()));

	// Chuỗi đường dẫn ổn định: chỉ lan truyền khi giá trị đổi thật (không theo danh tính object manifest cha)
	let activeGlbPath = $derived(
		pickStageGlb(
			{ glb_path: glbPath, mechanism_glb_path: mechanismGlbPath },
			hasMechanism ? stageVariant : 'real'
		) ?? ''
	);

	// Lifecycle: Mount / Load Real PBR .glb + Studio HDRI + Offline Draco + Selective Bloom
	$effect(() => {
		const host = canvasHost;
		const activeGlb = activeGlbPath;
		// C2: Chờ 2D mặc định → không mượn renderer (0 context WebGL) cho tới khi bấm ▶
		const active3d = stageMode.pbr3d;
		if (!host || !activeGlb || !active3d) {
			webglReady = false;
			loadingGlb = false;
			stageApi = null;
			return;
		}

		const tier = qualityTier;
		let disposed = false;
		let cleanupFn: (() => void) | null = null;

		loadingGlb = true;
		loadError = '';

		(async () => {
			try {
				const THREE = await import('three');
				const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
				const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
				const { DRACOLoader } = await import('three/examples/jsm/loaders/DRACOLoader.js');
				const { RoomEnvironment } = await import(
					'three/examples/jsm/environments/RoomEnvironment.js'
				);
				const { EffectComposer } = await import(
					'three/examples/jsm/postprocessing/EffectComposer.js'
				);
				const { RenderPass } = await import('three/examples/jsm/postprocessing/RenderPass.js');
				const { UnrealBloomPass } = await import(
					'three/examples/jsm/postprocessing/UnrealBloomPass.js'
				);
				const { OutputPass } = await import('three/examples/jsm/postprocessing/OutputPass.js');

				if (disposed || !host) return;

				const initW = Math.max(host.clientWidth, 480);
				const initH = Math.max(host.clientHeight, 340);
				// HD: đúng DPR màn hình (tối đa 1.0) · Ultra: luôn siêu lấy mẫu 1.5 (B0: trước đây Ultra = HD trên màn DPR 1). MSAA 4× của render target lo khử răng cưa.
				const getTargetDpr = () => pbrPixelRatio(tier, window.devicePixelRatio || 1);
				let currentDpr = getTargetDpr();

				// Mượn renderer dùng chung của app (không tạo context WebGL2 mới, không bao giờ forceContextLoss)
				host.innerHTML = '';
				const lease: StageLease = await acquireStage(
					host,
					{
						toneMapping: THREE.ACESFilmicToneMapping,
						toneMappingExposure: 1.08,
						outputColorSpace: THREE.SRGBColorSpace,
						shadowMapEnabled: true,
						shadowMapType: THREE.PCFSoftShadowMap,
						pixelRatio: currentDpr,
						width: initW,
						height: initH
					},
					() => cleanupFn?.()
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
				const studioBg = new THREE.Color(planet === 'earth' ? 0x0b1019 : 0x090c14);
				scene.background = studioBg;

				// Studio HDRI Environment via PMREMGenerator
				const pmrem = new THREE.PMREMGenerator(renderer);
				pmrem.compileEquirectangularShader();
				const roomEnv = new RoomEnvironment();
				const envRT = pmrem.fromScene(roomEnv, 0.035);
				scene.environment = envRT.texture;
				scene.environmentIntensity = 1.05;
				roomEnv.dispose();

				const camera = new THREE.PerspectiveCamera(38, initW / initH, 0.08, 280);
				camera.position.set(6.8, 4.4, 7.6);

				const controls = new OrbitControls(camera, renderer.domElement);
				controls.enableDamping = true;
				controls.dampingFactor = 0.07;
				controls.minDistance = 1.4;
				controls.maxDistance = 68.0;
				controls.maxPolarAngle = Math.PI * 0.495;
				controls.target.set(0, 1.8, 0);

				// 3-Point Physical Architectural Lighting Rig + 2048 PCFSoftShadowMap
				const keyLight = new THREE.DirectionalLight(0xfff1d6, 2.55);
				keyLight.position.set(8.5, 14.5, 9.2);
				keyLight.castShadow = true;
				const shadowRes = tier === 'ultra' ? 2048 : 1536;
				keyLight.shadow.mapSize.set(shadowRes, shadowRes);
				keyLight.shadow.camera.near = 0.5;
				keyLight.shadow.camera.far = 48;
				keyLight.shadow.camera.left = -10;
				keyLight.shadow.camera.right = 10;
				keyLight.shadow.camera.top = 18;
				keyLight.shadow.camera.bottom = -4;
				keyLight.shadow.bias = -0.00035;
				keyLight.shadow.normalBias = 0.022;
				scene.add(keyLight);

				const rimLight = new THREE.DirectionalLight(0x8fd3ff, 1.18);
				rimLight.position.set(-9.5, 8.2, -8.5);
				scene.add(rimLight);

				const hemiLight = new THREE.HemisphereLight(0xdce8ff, 0x181d2a, 0.62);
				scene.add(hemiLight);

				// Matte Shadow-Catcher Studio Floor + Metric Reference Grid (Zero Toy Primitives!)
				const shadowFloorMat = new THREE.ShadowMaterial({ opacity: 0.42 });
				const shadowFloor = new THREE.Mesh(new THREE.PlaneGeometry(44, 44), shadowFloorMat);
				shadowFloor.rotation.x = -Math.PI / 2;
				shadowFloor.position.y = -0.004;
				shadowFloor.receiveShadow = true;
				scene.add(shadowFloor);

				const gridHelper = new THREE.GridHelper(16, 16, 0x705728, 0x1c2333);
				gridHelper.position.y = -0.002;
				gridHelper.visible = untrack(() => showGrid);
				scene.add(gridHelper);

				// WebGL2 4x MSAA HDR EffectComposer + High-Threshold Selective Bloom
				const msaaSamples = renderer.capabilities.isWebGL2 ? 4 : 0;
				const msaaTarget = new THREE.WebGLRenderTarget(
					Math.round(initW * currentDpr),
					Math.round(initH * currentDpr),
					{
						type: THREE.HalfFloatType,
						samples: msaaSamples
					}
				);
				const composer = new EffectComposer(renderer, msaaTarget);
				// EffectComposer clone msaaTarget thành renderTarget2 (thêm 1 bộ đệm MSAA RGBA16F full-res).
				// Chuỗi pass ở đây không cần bộ đệm thứ hai: RenderPass & UnrealBloomPass có needsSwap = false,
				// OutputPass vẽ thẳng ra màn hình (needsSwap = false bên dưới) → renderTarget2 không bao giờ được ghi.
				// Thu nó về 1×1 và khóa setSize. Nếu sau này thêm pass có needsSwap = true, phải bỏ đoạn này.
				// RenderPass vẽ vào readBuffer (constructor đặt readBuffer = renderTarget2) → trỏ readBuffer về target MSAA.
				composer.renderTarget2.dispose();
				const idleTarget = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType });
				idleTarget.setSize = () => {};
				composer.renderTarget2 = idleTarget;
				composer.readBuffer = msaaTarget;
				composer.writeBuffer = idleTarget;
				composer.setPixelRatio(currentDpr);
				composer.setSize(initW, initH);

				const renderPass = new RenderPass(scene, camera);
				const bloomPass = new UnrealBloomPass(
					new THREE.Vector2(initW, initH),
					0.16,
					0.32,
					1.42
				);
				const outputPass = new OutputPass();
				outputPass.needsSwap = false;
				composer.addPass(renderPass);
				composer.addPass(bloomPass);
				composer.addPass(outputPass);

				// Offline DRACOLoader + GLTFLoader
				const dracoLoader = new DRACOLoader();
				dracoLoader.setDecoderPath('/draco/');
				const gltfLoader = new GLTFLoader();
				gltfLoader.setDRACOLoader(dracoLoader);
				gltfLoader.setKTX2Loader(ktx2Loader);

				// P0: bộ trộn animation của bản cơ khí (null với .glb tĩnh)
				let mixer: InstanceType<typeof THREE.AnimationMixer> | null = null;
				let animHook: StageAnimHook | null = null;
				const animClock = new THREE.Clock();

				// Vòng render theo nhu cầu: đứng yên → 0 rAF. Tạo trước khi nạp để cleanup luôn dọn được.
				const loop: OnDemandLoop = createOnDemandLoop(() => {
					if (mixer) mixer.update(Math.min(animClock.getDelta(), 0.1));
					const moving = controls.update();
					composer.render();
					return moving;
				});
				const requestRender = () => loop.invalidate();
				controls.addEventListener('change', requestRender);
				let resizeObs: ResizeObserver | null = null;
				let detachCanvasListeners: (() => void) | null = null;
				let tornDown = false;

				// Dọn sạch mọi tài nguyên GPU rồi trả canvas — dùng chung cho unmount, đổi dự án, nạp muộn, bị sân khấu khác lấy renderer.
				cleanupFn = () => {
					if (tornDown) return;
					tornDown = true;
					loop.dispose();
					if (mixer) {
						mixer.stopAllAction();
						mixer.uncacheRoot(mixer.getRoot());
						mixer = null;
					}
					const w = window as unknown as { __akunarchStage?: StageAnimHook };
					if (animHook && w.__akunarchStage === animHook) delete w.__akunarchStage;
					animHook = null;
					resizeObs?.disconnect();
					detachCanvasListeners?.();
					controls.removeEventListener('change', requestRender);
					controls.dispose();
					disposeObject3DDeep(scene);
					disposeComposer(composer);
					msaaTarget.dispose();
					idleTarget.dispose();
					envRT.dispose();
					pmrem.dispose();
					dracoLoader.dispose();
					lease.release();
				};

				const gltfUrl = mediaUrl(activeGlb);
				const gltf = await gltfLoader.loadAsync(gltfUrl);
				if (disposed) {
					// Nạp xong sau khi sân khấu đã đóng: cleanupFn đã chạy, chỉ còn cây .glb vừa về
					disposeObject3DDeep(gltf.scene);
					return;
				}

				const maxAniso = Math.min(16, renderer.capabilities.getMaxAnisotropy());
				const allMeshes: InstanceType<typeof THREE.Mesh>[] = [];
				let countedTriangles = 0;

				gltf.scene.traverse((obj) => {
					if ((obj as InstanceType<typeof THREE.Mesh>).isMesh) {
						const mesh = obj as InstanceType<typeof THREE.Mesh>;
						mesh.castShadow = true;
						mesh.receiveShadow = true;
						allMeshes.push(mesh);

						const geom = mesh.geometry;
						if (geom) {
							const idxCount = geom.index
								? geom.index.count
								: (geom.attributes.position?.count ?? 0);
							countedTriangles += Math.floor(idxCount / 3);
						}

						const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
						for (const m of mats) {
							if (!m) continue;
							const std = m as InstanceType<typeof THREE.MeshStandardMaterial>;
							const texSlots = [
								std.map,
								std.normalMap,
								std.roughnessMap,
								std.metalnessMap,
								std.aoMap,
								std.emissiveMap
							];
							for (const tex of texSlots) {
								if (tex) {
									// Chưa upload lần nào → không cần needsUpdate (tránh đẩy lại texture 2K lên GPU)
									tex.anisotropy = maxAniso;
								}
							}
							if (untrack(() => showWireframe)) {
								std.wireframe = true;
							}
						}
					}
				});

				// Normalize monument onto Studio Turntable (`largestDim -> 6.2m`, resting cleanly at Y = 0)
				const modelPivot = new THREE.Group();
				modelPivot.add(gltf.scene);
				scene.add(modelPivot);
				modelPivot.updateMatrixWorld(true);

				const rawBox = new THREE.Box3().setFromObject(gltf.scene);
				const rawSize = new THREE.Vector3();
				const rawCenter = new THREE.Vector3();
				rawBox.getSize(rawSize);
				rawBox.getCenter(rawCenter);
				const largestRawDim = Math.max(rawSize.x, rawSize.y, rawSize.z, 0.001);
				const dioramaFit = 6.2 / largestRawDim;

				modelPivot.scale.setScalar(dioramaFit);
				modelPivot.position.set(
					-rawCenter.x * dioramaFit,
					-rawBox.min.y * dioramaFit,
					-rawCenter.z * dioramaFit
				);
				modelPivot.updateMatrixWorld(true);

				// Discover top-level part nodes directly from the real .glb hierarchy
				let candidateNodes = [...gltf.scene.children];
				if (
					candidateNodes.length === 1 &&
					!(candidateNodes[0] as InstanceType<typeof THREE.Mesh>).isMesh &&
					candidateNodes[0].children.length > 1
				) {
					candidateNodes = [...candidateNodes[0].children];
				}
				// Keep nodes that actually contain geometry
				const partNodes = candidateNodes.filter((n) => {
					let hasGeom = false;
					n.traverse((c) => {
						if ((c as InstanceType<typeof THREE.Mesh>).isMesh) hasGeom = true;
					});
					return hasGeom;
				});

				const currentPartsMeta = untrack(() => partsMeta ?? []);
				const metaById = new Map<string, ClockworkPartMeta>();
				for (const pm of currentPartsMeta) {
					if (pm && pm.id) metaById.set(pm.id, pm);
				}

				interface BoundPart {
					id: string;
					node: InstanceType<typeof THREE.Object3D>;
					basePos: InstanceType<typeof THREE.Vector3>;
					dir: [number, number, number];
					nameVi: string;
					nameEn: string;
					summaryVi: string;
					polyCount: number;
					assembledBox: InstanceType<typeof THREE.Box3>;
				}

				const boundParts: BoundPart[] = partNodes.map((node, idx) => {
					const rawId = node.name || `part_${idx + 1}`;
					const meta = metaById.get(rawId);
					let pTris = 0;
					node.traverse((c) => {
						if ((c as InstanceType<typeof THREE.Mesh>).isMesh) {
							const g = (c as InstanceType<typeof THREE.Mesh>).geometry;
							if (g) {
								pTris += Math.floor(
									(g.index ? g.index.count : (g.attributes.position?.count ?? 0)) / 3
								);
							}
						}
					});
					const pBox = new THREE.Box3().setFromObject(node);
					const prettyLabel = rawId
						.replace(/[_-]+/g, ' ')
						.replace(/\b\w/g, (m) => m.toUpperCase());
					const dirTuple: [number, number, number] =
						meta?.dir && meta.dir.length === 3
							? [Number(meta.dir[0]) || 0, Number(meta.dir[1]) || 0, Number(meta.dir[2]) || 0]
							: [0, 0, 0];

					return {
						id: rawId,
						node,
						basePos: node.position.clone(),
						dir: dirTuple,
						nameVi: meta?.name_vi || prettyLabel,
						nameEn: meta?.name_en || prettyLabel,
						summaryVi: meta?.summary_vi || '',
						polyCount: pTris,
						assembledBox: pBox
					};
				});

				// If any multi-part .glb lacks explicit coaxial `dir` vectors (e.g., BYOA external .glb),
				// synthesize clean bottom-to-top coaxial Y-offsets guaranteeing >= +0.58m gap at 50% explode!
				const hasExplicitDirs = boundParts.some(
					(bp) => Math.abs(bp.dir[0]) + Math.abs(bp.dir[1]) + Math.abs(bp.dir[2]) > 0.01
				);
				if (!hasExplicitDirs && boundParts.length > 1) {
					const sortedByBase = [...boundParts].sort((a, b) => {
						const ay = a.assembledBox.min.y * 0.65 + a.assembledBox.max.y * 0.35;
						const by = b.assembledBox.min.y * 0.65 + b.assembledBox.max.y * 0.35;
						return ay - by;
					});
					let prevTopAtHalf = sortedByBase[0].assembledBox.max.y;
					sortedByBase[0].dir = [0, 0, 0];
					for (let i = 1; i < sortedByBase.length; i++) {
						const cur = sortedByBase[i];
						const neededMinAtHalf = prevTopAtHalf + 0.62;
						const deltaHalf = Math.max(0.62, neededMinAtHalf - cur.assembledBox.min.y);
						const dyFull = Number((deltaHalf * 2.0).toFixed(2));
						cur.dir = [0, dyFull, 0];
						prevTopAtHalf = cur.assembledBox.max.y + deltaHalf;
					}
				}

				// Order UI part list from bottom foundation (index 0) to top crown
				boundParts.sort((a, b) => a.dir[1] - b.dir[1] || a.assembledBox.min.y - b.assembledBox.min.y);

				function frameSceneBounds(box: InstanceType<typeof THREE.Box3>, preserveAngles: boolean) {
					if (box.isEmpty()) return;
					const bSize = new THREE.Vector3();
					const bCenter = new THREE.Vector3();
					box.getSize(bSize);
					box.getCenter(bCenter);

					const vFovRad = THREE.MathUtils.degToRad(camera.fov);
					const hFovRad = 2 * Math.atan(Math.tan(vFovRad / 2) * camera.aspect);
					const distV = (bSize.y * 0.58) / Math.tan(vFovRad / 2);
					const radiusXZ = Math.max(bSize.x, bSize.z) * 0.58;
					const distH = radiusXZ / Math.tan(hFovRad / 2);
					const idealDist = Math.max(distV, distH, 5.8) * 1.16;

					const viewDir = preserveAngles
						? camera.position.clone().sub(controls.target).normalize()
						: new THREE.Vector3(0.56, 0.32, 0.76).normalize();
					if (viewDir.lengthSq() < 0.001) viewDir.set(0.56, 0.32, 0.76).normalize();

					controls.target.set(bCenter.x, bCenter.y * 0.96, bCenter.z);
					camera.position.copy(controls.target).addScaledVector(viewDir, idealDist);
					controls.update();

					// Expand shadow frustum vertically when exploded up to 16m+
					keyLight.shadow.camera.top = Math.max(16, box.max.y + 4);
					keyLight.shadow.camera.updateProjectionMatrix();
				}

				function recomputeBoxesAndState(pct: number, reframeCamera: boolean) {
					const t = Math.max(0, Math.min(1, pct / 100));
					for (const bp of boundParts) {
						bp.node.position.set(
							bp.basePos.x + (t * bp.dir[0]) / dioramaFit,
							bp.basePos.y + (t * bp.dir[1]) / dioramaFit,
							bp.basePos.z + (t * bp.dir[2]) / dioramaFit
						);
					}
					modelPivot.updateMatrixWorld(true);

					const visibleBoxes: { id: string; box: InstanceType<typeof THREE.Box3>; midY: number }[] =
						[];
					const totalBox = new THREE.Box3();
					const nextRuntime: RuntimePartItem[] = [];

					for (const bp of boundParts) {
						const wBox = new THREE.Box3().setFromObject(bp.node);
						const yMin = wBox.isEmpty() ? 0 : wBox.min.y;
						const yMax = wBox.isEmpty() ? 0 : wBox.max.y;
						if (bp.node.visible && !wBox.isEmpty()) {
							visibleBoxes.push({ id: bp.id, box: wBox, midY: 0.5 * (yMin + yMax) });
							totalBox.union(wBox);
						}
						nextRuntime.push({
							id: bp.id,
							nameVi: bp.nameVi,
							nameEn: bp.nameEn,
							summaryVi: bp.summaryVi,
							dir: bp.dir,
							visible: bp.node.visible,
							yMin,
							yMax,
							polyCount: bp.polyCount
						});
					}

					if (visibleBoxes.length >= 2) {
						visibleBoxes.sort((a, b) => a.midY - b.midY);
						let minGap = Infinity;
						for (let i = 0; i < visibleBoxes.length - 1; i++) {
							const gap = visibleBoxes[i + 1].box.min.y - visibleBoxes[i].box.max.y;
							if (gap < minGap) minGap = gap;
						}
						minYGapMeters = Number.isFinite(minGap) ? minGap : 0;

						const fullBoxes = boundParts
							.filter((bp) => bp.node.visible && !bp.assembledBox.isEmpty())
							.map((bp) => {
								const yMin100 = bp.assembledBox.min.y + bp.dir[1];
								const yMax100 = bp.assembledBox.max.y + bp.dir[1];
								return { yMin100, yMax100, midY: 0.5 * (yMin100 + yMax100) };
							})
							.sort((a, b) => a.midY - b.midY);
						let minGap100 = Infinity;
						for (let i = 0; i < fullBoxes.length - 1; i++) {
							const gap100 = fullBoxes[i + 1].yMin100 - fullBoxes[i].yMax100;
							if (gap100 < minGap100) minGap100 = gap100;
						}
						minYGap100Meters = Number.isFinite(minGap100) ? minGap100 : 0;
					} else {
						minYGapMeters = 0;
						minYGap100Meters = 0;
					}

					runtimeParts = nextRuntime;
					if (reframeCamera && !totalBox.isEmpty()) {
						frameSceneBounds(totalBox, true);
					}
				}

				// Store original emissive values for non-destructive part selection highlight
				const origEmissive = new Map<
					InstanceType<typeof THREE.Material>,
					{ hex: number; intensity: number }
				>();
				for (const mesh of allMeshes) {
					const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
					for (const m of mats) {
						const std = m as InstanceType<typeof THREE.MeshStandardMaterial>;
						if (std && std.emissive && !origEmissive.has(std)) {
							origEmissive.set(std, {
								hex: std.emissive.getHex(),
								intensity: std.emissiveIntensity ?? 1
							});
						}
					}
				}

				function highlightPart(partId: string | null, focusCam: boolean) {
					requestRender();
					for (const [mat, orig] of origEmissive.entries()) {
						const std = mat as InstanceType<typeof THREE.MeshStandardMaterial>;
						std.emissive.setHex(orig.hex);
						std.emissiveIntensity = orig.intensity;
					}
					if (!partId) return;
					const target = boundParts.find((b) => b.id === partId);
					if (!target) return;
					target.node.traverse((c) => {
						if ((c as InstanceType<typeof THREE.Mesh>).isMesh) {
							const mList = Array.isArray((c as InstanceType<typeof THREE.Mesh>).material)
								? ((c as InstanceType<typeof THREE.Mesh>).material as InstanceType<
										typeof THREE.Material
									>[])
								: [(c as InstanceType<typeof THREE.Mesh>).material];
							for (const m of mList) {
								const std = m as InstanceType<typeof THREE.MeshStandardMaterial>;
								if (std && std.emissive) {
									std.emissive.setHex(0x523c14);
									std.emissiveIntensity = 0.75;
								}
							}
						}
					});
					if (focusCam) {
						const pBox = new THREE.Box3().setFromObject(target.node);
						frameSceneBounds(pBox, true);
					}
				}

				// Raycast click on 3D canvas to pick top-level part directly
				const raycaster = new THREE.Raycaster();
				const pointerDownPos = { x: 0, y: 0 };
				const onPointerDown = (ev: PointerEvent) => {
					pointerDownPos.x = ev.clientX;
					pointerDownPos.y = ev.clientY;
				};
				const onPointerUp = (ev: PointerEvent) => {
					const moved = Math.hypot(ev.clientX - pointerDownPos.x, ev.clientY - pointerDownPos.y);
					if (moved > 5 || ev.button !== 0) return;
					const rect = renderer.domElement.getBoundingClientRect();
					const ndc = new THREE.Vector2(
						((ev.clientX - rect.left) / rect.width) * 2 - 1,
						-((ev.clientY - rect.top) / rect.height) * 2 + 1
					);
					raycaster.setFromCamera(ndc, camera);
					const hits = raycaster.intersectObjects(allMeshes, false);
					const hit = hits.find((h) => h.object.visible);
					if (!hit) {
						selectedPartId = null;
						highlightPart(null, false);
						return;
					}
					let cur: InstanceType<typeof THREE.Object3D> | null = hit.object;
					let matchedId: string | null = null;
					while (cur) {
						const found = boundParts.find((bp) => bp.node === cur);
						if (found) {
							matchedId = found.id;
							break;
						}
						cur = cur.parent;
					}
					selectedPartId = matchedId;
					highlightPart(matchedId, false);
				};
				renderer.domElement.addEventListener('pointerdown', onPointerDown);
				renderer.domElement.addEventListener('pointerup', onPointerUp);
				// Canvas dùng chung sống suốt đời app → phải gỡ listener khi trả renderer
				detachCanvasListeners = () => {
					renderer.domElement.removeEventListener('pointerdown', onPointerDown);
					renderer.domElement.removeEventListener('pointerup', onPointerUp);
				};

				// Initial framing & state sync
				totalPolys = countedTriangles;
				const initPct = untrack(() => explodePct);
				const initBox = new THREE.Box3().setFromObject(modelPivot);
				frameSceneBounds(initBox, false);
				recomputeBoxesAndState(initPct, initPct > 0);

				// P0: bản cơ khí — phát `assemble` 1 lần rồi lặp `idle`; vòng render chạy liên tục khi đang phát
				const clipNames = gltf.animations.map((a) => a.name);
				const clips = pickClockworkClips(clipNames);
				if (clips.intro || clips.loop) {
					const m = new THREE.AnimationMixer(gltf.scene);
					mixer = m;
					const clip = (n: string | null) => (n ? THREE.AnimationClip.findByName(gltf.animations, n) : null);
					const introClip = clip(clips.intro);
					const idleClip = clip(clips.loop);
					const introAct = introClip ? m.clipAction(introClip) : null;
					const idleAct = idleClip ? m.clipAction(idleClip) : null;
					if (introAct) {
						introAct.setLoop(THREE.LoopOnce, 1);
						introAct.clampWhenFinished = true;
					}
					const startIdle = () => {
						if (!idleAct) return;
						introAct?.stop();
						idleAct.reset().play();
					};
					m.addEventListener('finished', (e) => {
						if (e.action === introAct) startIdle();
					});
					if (introAct) introAct.play();
					else startIdle();
					animClock.getDelta();
					loop.setContinuous('mixer', true);
					animHook = {
						clips: clipNames,
						seek: (sec: number) => {
							m.stopAllAction();
							const introDur = introClip?.duration ?? 0;
							if (introAct && sec <= introDur) {
								introAct.reset().play();
								introAct.time = sec;
							} else if (idleAct) {
								idleAct.reset().play();
								idleAct.time = (sec - introDur) % Math.max(idleClip!.duration, 1e-3);
							}
							m.update(0);
							loop.setContinuous('mixer', false);
							requestRender();
						},
						play: () => {
							animClock.getDelta();
							loop.setContinuous('mixer', true);
						},
						pause: () => loop.setContinuous('mixer', false)
					};
					(window as unknown as { __akunarchStage?: StageAnimHook }).__akunarchStage = animHook;
				}

				// Resize observer keeps viewport crisp across any window size
				resizeObs = new ResizeObserver(() => {
					if (disposed || !host || !lease.active) return;
					const nw = Math.max(host.clientWidth, 320);
					const nh = Math.max(host.clientHeight, 240);
					currentDpr = getTargetDpr();
					camera.aspect = nw / nh;
					camera.updateProjectionMatrix();
					renderer.setPixelRatio(currentDpr);
					renderer.setSize(nw, nh);
					composer.setPixelRatio(currentDpr);
					composer.setSize(nw, nh);
					bloomPass.resolution.set(nw, nh);
					requestRender();
				});
				resizeObs.observe(host);

				// Expose imperative API — mọi thao tác đều xin vẽ lại vì vòng render ngủ khi đứng yên
				stageApi = {
					applyExplode: (pct, reframe) => {
						recomputeBoxesAndState(pct, reframe);
						requestRender();
					},
					setPartVisible: (partId, visible) => {
						const bp = boundParts.find((b) => b.id === partId);
						if (bp) {
							bp.node.visible = visible;
							recomputeBoxesAndState(explodePct, false);
							requestRender();
						}
					},
					highlightPart,
					setWireframe: (wf) => {
						for (const mesh of allMeshes) {
							const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
							for (const m of mats) {
								if (m && 'wireframe' in m) {
									(m as InstanceType<typeof THREE.MeshStandardMaterial>).wireframe = wf;
								}
							}
						}
						requestRender();
					},
					setGridVisible: (gv) => {
						gridHelper.visible = gv;
						requestRender();
					},
					setAutoRotate: (on) => {
						controls.autoRotate = on;
						controls.autoRotateSpeed = 1.1;
						loop.setContinuous('autoRotate', on);
					},
					resetCamera: () => {
						const curBox = new THREE.Box3().setFromObject(modelPivot);
						frameSceneBounds(curBox, false);
						requestRender();
					},
					captureMangaPlates2K: (exportW: number, exportH: number) => {
						const prevW = Math.max(host.clientWidth, 320);
						const prevH = Math.max(host.clientHeight, 240);
						const prevAspect = camera.aspect;
						const prevGrid = gridHelper.visible;
						const prevFloor = shadowFloor.visible;
						const prevBg = scene.background;
						const prevTone = renderer.toneMapping;

						// Linear Camera-Space Normalized Depth Shader (`white = near foreground`, `black = far`)
						const worldBox = new THREE.Box3().setFromObject(modelPivot);
						let minViewZ = Infinity;
						let maxViewZ = -Infinity;

						try {
							gridHelper.visible = false;
							camera.aspect = exportW / exportH;
							camera.updateProjectionMatrix();
							camera.updateMatrixWorld(true);

							if (!worldBox.isEmpty()) {
								const corners = [
									new THREE.Vector3(worldBox.min.x, worldBox.min.y, worldBox.min.z),
									new THREE.Vector3(worldBox.min.x, worldBox.min.y, worldBox.max.z),
									new THREE.Vector3(worldBox.min.x, worldBox.max.y, worldBox.min.z),
									new THREE.Vector3(worldBox.min.x, worldBox.max.y, worldBox.max.z),
									new THREE.Vector3(worldBox.max.x, worldBox.min.y, worldBox.min.z),
									new THREE.Vector3(worldBox.max.x, worldBox.min.y, worldBox.max.z),
									new THREE.Vector3(worldBox.max.x, worldBox.max.y, worldBox.min.z),
									new THREE.Vector3(worldBox.max.x, worldBox.max.y, worldBox.max.z)
								];
								for (const c of corners) {
									c.applyMatrix4(camera.matrixWorldInverse);
									const vz = -c.z;
									if (vz < minViewZ) minViewZ = vz;
									if (vz > maxViewZ) maxViewZ = vz;
								}
							}
							if (!Number.isFinite(minViewZ) || maxViewZ <= minViewZ + 0.05) {
								minViewZ = 1.0;
								maxViewZ = 28.0;
							} else {
								const pad = (maxViewZ - minViewZ) * 0.04;
								minViewZ = Math.max(0.1, minViewZ - pad);
								maxViewZ = maxViewZ + pad;
							}

							renderer.setPixelRatio(1);
							renderer.setSize(exportW, exportH, false);
							composer.setPixelRatio(1);
							composer.setSize(exportW, exportH);
							bloomPass.resolution.set(exportW, exportH);

							// 1. 2K Beauty Plate (ACES Filmic + HDRI + Shadows + Selective Bloom)
							composer.render();
							const beauty = renderer.domElement.toDataURL('image/png');

							// 2. 2K Normalized Depth Map Plate (ControlNet / Manga Line-Art Ready)
							shadowFloor.visible = false;
							scene.background = new THREE.Color(0x000000);
							renderer.toneMapping = THREE.NoToneMapping;

							const depthShader = new THREE.ShaderMaterial({
								uniforms: {
									uNear: { value: minViewZ },
									uFar: { value: maxViewZ }
								},
								vertexShader: `
									varying float vViewZ;
									void main() {
										vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
										vViewZ = -mvPos.z;
										gl_Position = projectionMatrix * mvPos;
									}
								`,
								fragmentShader: `
									uniform float uNear;
									uniform float uFar;
									varying float vViewZ;
									void main() {
										float d = clamp((uFar - vViewZ) / max(0.0001, (uFar - uNear)), 0.0, 1.0);
										gl_FragColor = vec4(vec3(d), 1.0);
									}
								`
							});
							scene.overrideMaterial = depthShader;
							renderer.setRenderTarget(null);
							renderer.clear();
							renderer.render(scene, camera);
							const depth = renderer.domElement.toDataURL('image/png');
							depthShader.dispose();

							return { beauty, depth };
						} finally {
							scene.overrideMaterial = null;
							scene.background = prevBg;
							renderer.toneMapping = prevTone;
							shadowFloor.visible = prevFloor;
							gridHelper.visible = prevGrid;

							camera.aspect = prevAspect;
							camera.updateProjectionMatrix();
							renderer.setPixelRatio(currentDpr);
							renderer.setSize(prevW, prevH);
							composer.setPixelRatio(currentDpr);
							composer.setSize(prevW, prevH);
							bloomPass.resolution.set(prevW, prevH);
							composer.render();
							requestRender();
						}
					}
				};

				const initAutoRotate = untrack(() => autoRotate);
				controls.autoRotate = initAutoRotate;
				controls.autoRotateSpeed = 1.1;
				loop.setContinuous('autoRotate', initAutoRotate);
				requestRender();

				webglReady = true;
				loadingGlb = false;
			} catch (err) {
				// Lỗi nạp (.glb hỏng/thiếu) → trả renderer & tài nguyên ngay, không giữ VRAM chờ unmount
				cleanupFn?.();
				if (!disposed) {
					loadError = err instanceof Error ? err.message : String(err);
					loadingGlb = false;
					webglReady = false;
				}
			}
		})();

		return () => {
			disposed = true;
			stageApi = null;
			if (cleanupFn) cleanupFn();
		};
	});
</script>

{#if glbPath && glbPath.trim()}
	<!-- REAL AAA PBR / HDRI 3D STAGE -->
	<div
		class="pbr-stage-shell card"
		data-testid="real-pbr-stage"
		data-min-y-gap={minYGapMeters.toFixed(3)}
		data-explode-pct={explodePct}
		data-parts-count={runtimeParts.length}
	>
		<!-- Top Architectural Telemetry & Manga 2K Toolbar -->
		<div class="stage-topbar">
			<div class="stage-title-cluster">
				<div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
					<span class="badge badge-ok">AAA PBR · HDRI · DRACO</span>
					<span class="badge {planet === 'earth' ? 'badge-warn' : 'badge-cyan'}">
						{planet === 'earth' ? 'Trái Đất' : 'Akunalia'}
					</span>
					{#if era}
						<span class="badge">{era}</span>
					{/if}
					<span class="badge tabular">Ch.{unlockChapter}</span>
					<span class="badge mono tabular" title="Tổng số đa giác tam giác thật trong file .glb">
						▲ {formatPolyCount(totalPolys)} tris · {runtimeParts.length} cụm
					</span>
				</div>
				<div class="stage-main-title" title={titleEn || title}>{title}</div>
			</div>

			<div class="stage-toolbar-right">
				<div class="manga-export-group">
					<select
						class="select select-compact"
						aria-label="Tỉ lệ khung hình Manga 2K"
						bind:value={mangaPreset}
					>
						<option value="landscape_2k">2K Ngang (2048×1152)</option>
						<option value="vertical_2k">2K Dọc (1440×2048)</option>
					</select>
					<button
						class="btn btn-sm btn-brass"
						data-testid="export-manga-2k-btn"
						onclick={handleExportManga2K}
						disabled={!webglReady || exportingPlates}
						title="Kết xuất góc quay hiện tại thành beauty_plate.png + depth_map.png vào manga_plates\"
					>
						{exportingPlates ? '⏳ Đang kết xuất 2K...' : '📸 Chụp Phông Nền Manga 2K'}
					</button>
				</div>

				{#if introVideoPath}
					<button
						class="btn btn-sm btn-cyan"
						onclick={() => (showIntroModal = !showIntroModal)}
						title="Xem phim Intro xoay/trồi sa bàn .mp4 đã render"
					>
						🎬 Intro .mp4
					</button>
				{/if}

				<button
					class="btn btn-sm {qualityTier === 'ultra' ? 'btn-brass' : ''}"
					data-testid="pbr-quality-toggle"
					onclick={() => (qualityTier = qualityTier === 'hd' ? 'ultra' : 'hd')}
					title="HD: nhẹ VRAM (DPR ≤ 1.0, bóng 1536) · Ultra: siêu lấy mẫu 1.5×, bóng 2048. Chụp Manga 2K luôn ở độ phân giải gốc."
				>
					{qualityTier === 'hd' ? 'HD' : 'Ultra'}
				</button>
				{#if hasMechanism}
					<button
						class="btn btn-sm {stageVariant === 'mechanism' ? 'btn-brass' : ''}"
						data-testid="stage-variant-toggle"
						onclick={() => (stageVariant = stageVariant === 'real' ? 'mechanism' : 'real')}
						title="Bản thật (thế giới mở, phim trường) ↔ Bản cơ khí (sa bàn đồng hồ, có animation lắp ráp)"
					>
						{stageVariant === 'real' ? 'Bản thật' : '⚙ Bản cơ khí'}
					</button>
				{/if}
				{#if stageMode.pbr3d}
					<button
						class="btn btn-sm"
						data-testid="deactivate-3d-stage-btn"
						onclick={() => (stageMode.pbr3d = false)}
						title="Tháo sân khấu 3D, trả VRAM — về thẻ Chờ 2D"
					>
						⏹ Ngắt 3D
					</button>
				{/if}
			</div>
		</div>

		<!-- Center WebGL2 Viewport + Interactive .glb Parts Overlay -->
		<div class="canvas-viewport">
			<div class="webgl-mount" bind:this={canvasHost}></div>

			{#if !stageMode.pbr3d}
				<div class="pbr-2d-standby-card" data-testid="pbr-2d-standby-card">
					{#if standbyImage}
						<img class="standby-img" src={mediaUrl(standbyImage)} alt={title} />
					{/if}
					<div class="standby-panel">
						<span class="badge badge-cyan">CHỜ 2D · 3D ĐANG NGẮT (0 MB VRAM)</span>
						<strong class="standby-title">{title}</strong>
						<span class="standby-src mono">{standbySource}</span>
						{#if partsMeta.length > 0}
							{@const partsLine = partsMeta.map((p) => p.name_vi || p.id).join(' · ')}
							<span class="standby-parts" title={partsLine}>
								{partsMeta.length} cụm: {partsLine}
							</span>
						{/if}
						<div class="standby-actions">
							<button
								class="btn btn-brass"
								data-testid="activate-3d-stage-btn"
								onclick={() => (stageMode.pbr3d = true)}
							>
								▶ Bật Sân Khấu 3D
							</button>
							<button
								class="btn btn-sm"
								data-testid="render-preview-card-btn"
								disabled={previewQueued}
								onclick={requestPreviewCard}
								title="Blender 5.2 render ảnh 1920×1080 từ .glb gốc qua hàng đợi GPU"
							>
								{previewQueued ? '⏳ Đã xếp hàng' : '📷 Tạo ảnh xem trước'}
							</button>
							{#if standbyConcept && standbyConcept !== standbyPrimary}
								<button class="btn btn-sm" onclick={() => (standbyShowConcept = !standbyShowConcept)}>
									{standbyShowConcept ? '🖼️ Ảnh xem trước' : '🖼️ Concept gốc'}
								</button>
							{/if}
						</div>
					</div>
				</div>
			{/if}

			{#if loadingGlb}
				<div class="stage-overlay-msg">
					<div class="spinner-ring"></div>
					<div>Đang giải mã Draco &amp; nạp vật liệu PBR 2K từ <code>{fileBaseName(glbPath)}</code>...</div>
				</div>
			{:else if loadError}
				<div class="stage-overlay-msg webgl-fallback">
					<strong>Không nạp được mô hình .glb:</strong>
					<div class="mono" style="margin-top: 6px; color: #ffa8a8;">{loadError}</div>
					<div style="margin-top: 10px; display: flex; gap: 8px;">
						<button class="btn btn-sm btn-brass" onclick={onRequestImportGlb}>
							📥 Chọn lại file .glb
						</button>
						<button class="btn btn-sm" onclick={onRequestPickAiMesh}>
							🗿 Kho 47 Mesh Điêu Khắc
						</button>
					</div>
				</div>
			{/if}

			<!-- Collapsible Top-Level .glb Node Inspector Drawer -->
			{#if webglReady && runtimeParts.length > 0}
				<aside class="parts-floating-drawer {showPartsDrawer ? 'open' : 'collapsed'}">
					<div class="parts-drawer-hdr">
						<button
							class="btn-plain"
							onclick={() => (showPartsDrawer = !showPartsDrawer)}
							title="Đóng/mở danh sách cụm chi tiết .glb"
						>
							<strong>🔩 CỤM CHI TIẾT .GLB ({runtimeParts.length})</strong>
							<span>{showPartsDrawer ? '▾' : '▸'}</span>
						</button>
						{#if showPartsDrawer}
							<button
								class="lang-pill mono"
								onclick={() => (langMode = langMode === 'vi' ? 'en' : 'vi')}
								title="Chuyển ngôn ngữ tên bộ phận VI / EN"
							>
								{langMode.toUpperCase()}
							</button>
						{/if}
					</div>

					{#if showPartsDrawer}
						<div class="parts-list-scroll">
							{#each runtimeParts as part, idx (part.id)}
								<div
									class="part-chip-row {selectedPartId === part.id ? 'selected' : ''} {!part.visible
										? 'hidden-part'
										: ''}"
								>
									<button
										class="part-select-btn"
										onclick={() => selectAndFocusPart(part.id, false)}
										ondblclick={() => selectAndFocusPart(part.id, true)}
										title={part.summaryVi || part.id}
									>
										<span class="part-idx mono tabular">{idx + 1}</span>
										<div class="part-txt">
											<div class="part-name">
												{langMode === 'vi' ? part.nameVi : part.nameEn}
											</div>
											<div class="part-meta mono tabular">
												Y: {part.yMin.toFixed(1)}→{part.yMax.toFixed(1)}m · ▲{formatPolyCount(
													part.polyCount
												)}
											</div>
										</div>
									</button>
									<button
										class="part-vis-btn"
										onclick={(ev) => togglePartVisibility(part.id, ev)}
										title={part.visible ? 'Ẩn cụm này' : 'Hiện cụm này'}
									>
										{part.visible ? '👁' : '🚫'}
									</button>
								</div>
							{/each}
						</div>
					{/if}
				</aside>
			{/if}

			<!-- Manga 2K Latest Capture Preview Toast inside Stage -->
			{#if latestPreview}
				<div class="manga-preview-card" data-testid="manga-2k-preview">
					<div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
						<strong style="font-size: 11.5px; color: var(--brass-bright);">
							✓ Đã xuất Phông Nền Manga ({latestPreview.res})
						</strong>
						<div style="display: flex; gap: 4px;">
							<button
								class="btn btn-sm"
								style="padding: 2px 7px; font-size: 10.5px;"
								onclick={() => onOpenSubfolder('manga_plates')}
							>
								📂 manga_plates\
							</button>
							<button
								class="btn btn-sm"
								style="padding: 2px 6px; font-size: 10.5px;"
								onclick={() => (latestPreview = null)}
							>
								✕
							</button>
						</div>
					</div>
					<div class="manga-preview-thumbs">
						<figure>
							<img src={latestPreview.beauty} alt="Beauty Plate 2K" />
							<figcaption class="mono">beauty_plate.png</figcaption>
						</figure>
						<figure>
							<img src={latestPreview.depth} alt="Depth Map 2K" />
							<figcaption class="mono">depth_map.png</figcaption>
						</figure>
					</div>
				</div>
			{/if}

			<!-- Optional Rendered Intro .mp4 Overlay Player -->
			{#if showIntroModal && introVideoPath}
				<div class="intro-video-modal">
					<div class="intro-video-box card">
						<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
							<div>
								<div class="section-label">PHIM INTRO XOAY/TRỒI SA BÀN (.MP4)</div>
								<div class="mono" style="font-size: 11px; color: var(--text-muted);">
									{fileBaseName(introVideoPath)}
								</div>
							</div>
							<button class="btn btn-sm" onclick={() => (showIntroModal = false)}>✕ Đóng</button>
						</div>
						<!-- svelte-ignore a11y_media_has_caption -->
						<video
							src={mediaUrl(introVideoPath)}
							controls
							autoplay
							loop
							style="width: 100%; max-height: 360px; border-radius: 6px; background: #000;"
						></video>
					</div>
				</div>
			{/if}
		</div>

		<!-- Bottom Coaxial Explode Controls (0% -> 50% -> 100% + THREE.Box3 Y-Band Gap + BGM Player) -->
		<div class="stage-bottom-bar">
			<div class="explode-controls">
				<span class="section-label" style="white-space: nowrap;">THÁO LẮP ĐỒNG TRỤC:</span>
				<button
					class="btn btn-sm tabular {explodePct === 0 ? 'btn-brass' : ''}"
					data-testid="explode-0-btn"
					onclick={() => setExplodePreset(0)}
				>
					0%
				</button>
				<button
					class="btn btn-sm tabular {explodePct === 50 ? 'btn-brass' : ''}"
					data-testid="explode-50-btn"
					onclick={() => setExplodePreset(50)}
				>
					50%
				</button>
				<button
					class="btn btn-sm tabular {explodePct === 100 ? 'btn-brass' : ''}"
					data-testid="explode-100-btn"
					onclick={() => setExplodePreset(100)}
				>
					100%
				</button>
				<input
					type="range"
					min="0"
					max="100"
					step="1"
					value={explodePct}
					oninput={handleSliderInput}
					aria-label="Thanh trượt tháo lắp đồng trục 0 đến 100 phần trăm"
					class="explode-slider"
				/>
				<span class="mono tabular explode-pct-readout">{explodePct}%</span>

				{#if runtimeParts.length >= 2}
					{@const shownGap = explodePct === 0 ? minYGap100Meters : minYGapMeters}
					<span
						class="badge tabular {shownGap >= 0.35 ? 'badge-ok' : 'badge-warn'}"
						data-testid="y-band-gap-badge"
						title="Khoảng hở dọc nhỏ nhất giữa 2 tầng kế tiếp đo trực tiếp bằng THREE.Box3"
					>
						{explodePct === 0 ? 'Y-Gap (100%)' : 'Y-Gap'}: {shownGap >= 0 ? '+' : ''}{shownGap.toFixed(2)}m
					</span>
				{/if}
			</div>

			<div class="viewport-toggles">
				{#if bgmAudioPath}
					<div class="bgm-mini-bar" data-testid="bgm-audio-bar">
						<audio
							bind:this={audioEl}
							src={mediaUrl(bgmAudioPath)}
							loop={audioLoop}
							onended={() => (audioPlaying = false)}
						></audio>
						<button
							class="btn btn-sm {audioPlaying ? 'btn-cyan' : ''}"
							onclick={toggleAudioPlay}
							title={`Nghe thử BGM: ${fileBaseName(bgmAudioPath)}`}
						>
							{audioPlaying ? '⏸ BGM' : '▶ BGM'}
						</button>
						<span class="mono bgm-name" title={bgmAudioPath}>{fileBaseName(bgmAudioPath)}</span>
					</div>
				{:else}
					<button class="btn btn-sm" onclick={onRequestImportAudio} title="Gắn nhạc nền .mp3/.wav/.ogg/.flac">
						🎵 +BGM
					</button>
				{/if}

				<button
					class="btn btn-sm {autoRotate ? 'btn-cyan' : ''}"
					onclick={() => (autoRotate = !autoRotate)}
					title="Tự động xoay bàn trưng bày 360°"
				>
					↻ Xoay
				</button>
				<button
					class="btn btn-sm {showWireframe ? 'btn-cyan' : ''}"
					onclick={() => (showWireframe = !showWireframe)}
					title="Soi lưới đa giác Wireframe"
				>
					🕸 Lưới
				</button>
				<button
					class="btn btn-sm {showGrid ? 'btn-cyan' : ''}"
					onclick={() => (showGrid = !showGrid)}
					title="Ẩn/hiện mặt phẳng thước mét"
				>
					⊞ Thước
				</button>
				<button
					class="btn btn-sm"
					onclick={() => stageApi?.resetCamera()}
					title="Đưa góc quay camera về chính diện chuẩn"
				>
					🎯 Khung chuẩn
				</button>
			</div>
		</div>
	</div>
{:else}
	<!-- ZERO-PLACEHOLDER CONCEPT BLUEPRINT LAUNCHPAD (LUẬT #1: TUYỆT ĐỐI KHÔNG VẼ MÔ HÌNH 3D GIẢ!) -->
	<div class="concept-launchpad card" data-testid="concept-blueprint-launchpad">
		<div class="launchpad-header">
			<div>
				<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
					<span class="badge badge-brass">BÀN PHÓNG CONCEPT · CHƯA CÓ .GLB</span>
					<span class="badge {planet === 'earth' ? 'badge-warn' : 'badge-cyan'}">
						{planet === 'earth' ? 'Trái Đất' : 'Akunalia'}
					</span>
					<span class="badge">{kind}</span>
				</div>
				<h2 class="launchpad-title">{title}</h2>
			</div>

			<div style="display: flex; gap: 6px; flex-wrap: wrap;">
				<button
					class="btn btn-sm btn-brass"
					data-testid="sculpt-from-concept-btn"
					onclick={() => onSculptFromConcept(activeConceptPath)}
				>
					⚒️ Đúc 3D từ Ảnh này
				</button>
				<button
					class="btn btn-sm btn-cyan"
					data-testid="launchpad-import-glb-btn"
					onclick={onRequestImportGlb}
				>
					📥 Nhập file .glb có sẵn
				</button>
				<button
					class="btn btn-sm"
					data-testid="launchpad-pick-aimesh-btn"
					onclick={onRequestPickAiMesh}
				>
					🗿 Kho 47 Mesh Điêu Khắc
				</button>
			</div>
		</div>

		<div class="launchpad-canvas-area">
			{#if activeConceptPath}
				<div class="concept-hero-frame">
					<img
						src={mediaUrl(activeConceptPath)}
						alt={title}
						class="concept-hero-img"
					/>
					<div class="concept-caption-bar mono">
						<span>🖼️ {fileBaseName(activeConceptPath)}</span>
						<span>Kéo-thả trực tiếp .glb / .png / .mp3 / .flac vào cửa sổ để nạp ngay</span>
					</div>
				</div>

				{#if allConceptList.length > 1}
					<div class="concept-strip">
						{#each allConceptList as cp, idx (cp)}
							<button
								class="concept-thumb-btn {idx === activeConceptIdx ? 'active' : ''}"
								onclick={() => (activeConceptIdx = idx)}
							>
								<img src={mediaUrl(cp)} alt={`Concept ${idx + 1}`} />
							</button>
						{/each}
					</div>
				{/if}
			{:else}
				<div class="empty-blueprint-dropzone">
					<div style="font-size: 28px; margin-bottom: 8px;">📐</div>
					<strong>Dự án độc lập (World-First) sẵn sàng nhận tài nguyên thật</strong>
					<p>
						Theo Luật Chống Hình Giả (Zero-Placeholder Law), Akunarch không vẽ khối 3D giả lập.
						Hãy nạp Ảnh Concept để đúc bằng <strong>Hunyuan3D-2 fp16</strong> hoặc nhập trực tiếp file <code>.glb</code> PBR.
					</p>
					<div style="display: flex; gap: 8px; justify-content: center; margin-top: 8px;">
						<button class="btn btn-brass" onclick={onRequestImportConcept}>
							🖼️ Nhập Ảnh Concept (.png/.jpg/.webp)
						</button>
						<button class="btn btn-cyan" onclick={onRequestImportGlb}>
							📥 Nhập file .glb có sẵn
						</button>
					</div>
				</div>
			{/if}
		</div>

		{#if bgmAudioPath}
			<div class="launchpad-bgm-footer">
				<span class="badge badge-cyan">🎵 BGM Đã gắn: {fileBaseName(bgmAudioPath)}</span>
				<!-- svelte-ignore a11y_media_has_caption -->
				<audio src={mediaUrl(bgmAudioPath)} controls style="height: 28px; flex: 1;"></audio>
			</div>
		{/if}
	</div>
{/if}

<style>
	.pbr-stage-shell,
	.concept-launchpad {
		display: flex;
		flex-direction: column;
		width: 100%;
		height: 100%;
		min-height: 0;
		padding: 10px 12px;
		gap: 8px;
		overflow: hidden;
	}
	.stage-topbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
		flex-shrink: 0;
	}
	.stage-title-cluster {
		display: flex;
		flex-direction: column;
		gap: 3px;
		min-width: 0;
	}
	.stage-main-title {
		font-size: 14.5px;
		font-weight: 700;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.stage-toolbar-right {
		display: flex;
		align-items: center;
		gap: 7px;
		flex-wrap: wrap;
	}
	.manga-export-group {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 3px 5px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
	}
	.select-compact {
		padding: 4px 7px;
		font-size: 11.5px;
		width: auto;
	}
	.pbr-2d-standby-card {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: flex-end;
		background: #090d16;
	}
	.standby-img {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
	.standby-panel {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 10px;
		padding: 8px 10px;
		max-width: min(56%, 420px);
		border-radius: var(--radius-sm);
		background: rgba(9, 13, 22, 0.82);
		border: 1px solid var(--brass-line);
	}
	.standby-title {
		font-size: 14px;
	}
	.standby-src,
	.standby-parts {
		font-size: 11.5px;
		color: var(--text-secondary);
	}
	/* Tên cụm dài (vd. Avalon 6 cụm) không được che ảnh xem trước: tối đa 2 dòng, rê chuột xem đủ */
	.standby-parts {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.standby-actions {
		display: flex;
		gap: 6px;
		margin-top: 4px;
	}
	.canvas-viewport {
		position: relative;
		flex: 1;
		min-height: 260px;
		border-radius: var(--radius-sm);
		overflow: hidden;
		border: 1px solid var(--brass-line-strong);
		background: #080b12;
	}
	.webgl-mount {
		width: 100%;
		height: 100%;
	}
	.webgl-mount :global(canvas) {
		display: block;
		width: 100% !important;
		height: 100% !important;
	}
	.stage-overlay-msg {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 10px;
		background: rgba(8, 11, 18, 0.84);
		padding: 20px;
		text-align: center;
		z-index: 12;
	}
	.spinner-ring {
		width: 28px;
		height: 28px;
		border-radius: 50%;
		border: 3px solid rgba(212, 168, 83, 0.25);
		border-top-color: var(--brass-bright);
		animation: spin 0.85s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	/* Floating Top-Level .glb Parts Drawer */
	.parts-floating-drawer {
		position: absolute;
		top: 10px;
		left: 10px;
		width: 268px;
		max-height: calc(100% - 20px);
		display: flex;
		flex-direction: column;
		background: rgba(11, 14, 22, 0.88);
		backdrop-filter: blur(8px);
		border: 1px solid var(--brass-line-strong);
		border-radius: var(--radius-sm);
		z-index: 8;
		overflow: hidden;
	}
	.parts-floating-drawer.collapsed {
		width: auto;
	}
	.parts-drawer-hdr {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
		padding: 6px 9px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.07);
	}
	.btn-plain {
		display: flex;
		align-items: center;
		gap: 7px;
		background: transparent;
		border: none;
		color: var(--brass-bright);
		font-size: 11px;
		letter-spacing: 0.05em;
		cursor: pointer;
		padding: 0;
	}
	.lang-pill {
		background: rgba(212, 168, 83, 0.16);
		border: 1px solid var(--brass-line);
		color: var(--brass-bright);
		border-radius: 4px;
		font-size: 10px;
		padding: 1px 6px;
		cursor: pointer;
	}
	.parts-list-scroll {
		overflow-y: auto;
		padding: 5px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.part-chip-row {
		display: flex;
		align-items: center;
		gap: 4px;
		border-radius: 5px;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.06);
		padding: 3px 5px;
	}
	.part-chip-row.selected {
		border-color: var(--brass-bright);
		background: rgba(212, 168, 83, 0.16);
	}
	.part-chip-row.hidden-part {
		opacity: 0.48;
	}
	.part-select-btn {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 6px;
		background: transparent;
		border: none;
		color: inherit;
		text-align: left;
		cursor: pointer;
		padding: 2px;
	}
	.part-idx {
		font-size: 10px;
		padding: 1px 5px;
		border-radius: 3px;
		background: rgba(59, 201, 219, 0.14);
		color: var(--cyan-arcane);
		flex-shrink: 0;
	}
	.part-txt {
		min-width: 0;
		flex: 1;
	}
	.part-name {
		font-size: 11.2px;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.part-meta {
		font-size: 9.8px;
		color: var(--text-muted);
	}
	.part-vis-btn {
		background: transparent;
		border: none;
		cursor: pointer;
		font-size: 12px;
		padding: 2px 4px;
		border-radius: 4px;
	}
	.part-vis-btn:hover {
		background: rgba(255, 255, 255, 0.08);
	}

	/* Manga 2K Preview Floating Card */
	.manga-preview-card {
		position: absolute;
		right: 10px;
		bottom: 10px;
		width: 310px;
		padding: 8px 10px;
		border-radius: var(--radius-sm);
		background: rgba(11, 15, 24, 0.94);
		border: 1px solid var(--brass-bright);
		box-shadow: 0 10px 28px rgba(0, 0, 0, 0.7);
		z-index: 10;
	}
	.manga-preview-thumbs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 7px;
		margin-top: 6px;
	}
	.manga-preview-thumbs figure {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.manga-preview-thumbs img {
		width: 100%;
		height: 76px;
		object-fit: cover;
		border-radius: 4px;
		border: 1px solid rgba(255, 255, 255, 0.14);
	}
	.manga-preview-thumbs figcaption {
		font-size: 10px;
		color: var(--text-muted);
		text-align: center;
	}

	.intro-video-modal {
		position: absolute;
		inset: 0;
		background: rgba(5, 8, 14, 0.82);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 20px;
		z-index: 15;
	}
	.intro-video-box {
		width: min(680px, 95%);
		padding: 12px;
	}

	/* Bottom Bar */
	.stage-bottom-bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
		flex-shrink: 0;
	}
	.explode-controls {
		display: flex;
		align-items: center;
		gap: 6px;
		flex: 1;
		min-width: 320px;
	}
	.explode-slider {
		flex: 1;
		min-width: 90px;
		max-width: 190px;
		accent-color: var(--brass-bright);
		cursor: pointer;
	}
	.explode-pct-readout {
		font-size: 12px;
		font-weight: 700;
		color: var(--brass-bright);
		min-width: 36px;
	}
	.viewport-toggles {
		display: flex;
		align-items: center;
		gap: 5px;
		flex-wrap: wrap;
	}
	.bgm-mini-bar {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 2px 7px 2px 3px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
	}
	.bgm-name {
		max-width: 135px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		font-size: 10.5px;
		color: var(--text-secondary);
	}

	/* Zero-Placeholder Concept Blueprint Launchpad */
	.launchpad-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 12px;
		flex-wrap: wrap;
	}
	.launchpad-title {
		margin: 0;
		font-size: 16px;
		font-weight: 700;
	}
	.launchpad-canvas-area {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px;
		border-radius: var(--radius-sm);
		border: 1px solid var(--brass-line-strong);
		background:
			linear-gradient(rgba(212, 168, 83, 0.05) 1px, transparent 1px),
			linear-gradient(90deg, rgba(212, 168, 83, 0.05) 1px, transparent 1px),
			radial-gradient(circle at center, #101726 0%, #080b12 100%);
		background-size:
			28px 28px,
			28px 28px,
			100% 100%;
	}
	.concept-hero-frame {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 6px;
		overflow: hidden;
	}
	.concept-hero-img {
		max-width: 100%;
		max-height: calc(100% - 26px);
		object-fit: contain;
		border-radius: 6px;
		border: 1px solid var(--brass-bright);
		box-shadow: 0 12px 36px rgba(0, 0, 0, 0.65);
	}
	.concept-caption-bar {
		width: 100%;
		display: flex;
		justify-content: space-between;
		gap: 10px;
		font-size: 11px;
		color: var(--text-secondary);
	}
	.concept-strip {
		display: flex;
		gap: 7px;
		overflow-x: auto;
		padding-bottom: 2px;
		flex-shrink: 0;
	}
	.concept-thumb-btn {
		padding: 0;
		width: 74px;
		height: 48px;
		border-radius: 5px;
		overflow: hidden;
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: #000;
		cursor: pointer;
		flex-shrink: 0;
	}
	.concept-thumb-btn.active {
		border: 2px solid var(--brass-bright);
	}
	.concept-thumb-btn img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.empty-blueprint-dropzone {
		margin: auto;
		max-width: 520px;
		text-align: center;
		padding: 24px;
		border-radius: var(--radius-md);
		border: 1px dashed var(--brass-bright);
		background: rgba(11, 15, 24, 0.85);
	}
	.empty-blueprint-dropzone p {
		color: var(--text-secondary);
		font-size: 12.5px;
		line-height: 1.55;
	}
	.launchpad-bgm-footer {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 6px 10px;
		border-radius: var(--radius-sm);
		background: var(--obs-base);
		border: 1px solid var(--brass-line);
	}
</style>
