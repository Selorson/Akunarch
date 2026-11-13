<script lang="ts">
	import { untrack } from 'svelte';
	// Chỉ import KIỂU tĩnh — three / Spark được nạp động khi mở sân khấu 3D (không biên dịch shader splat lúc khởi động)
	import type * as THREE from 'three';
	import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
	import type { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
	import type { SparkRenderer, SplatMesh } from '@sparkjsdev/spark';
	import { api, fileToBase64, mediaUrl } from '$lib/ipc';
	import { acquireStage, type StageLease } from '$lib/webgl/webgl-stage';
	import { createOnDemandLoop, type OnDemandLoop } from '$lib/webgl/on-demand-loop';
	import { disposeObject3DDeep, disposeSparkRenderer } from '$lib/webgl/dispose';
	import { getSharedKtx2Loader } from '$lib/webgl/ktx2';
	import { stageMode } from '$lib/webgl/stage-mode.svelte';

	type ThreeModule = typeof import('three');
	import type {
		AmbientAudioZone,
		ChunkPlacementItem,
		ChunkSpawnPoint,
		ChunkStitchReport,
		ChunkVnTrigger,
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

	const POLYHAVEN_GRASS = 'E:\\Tools-3D\\polyhaven\\textures\\aerial_grass_rock\\Diffuse_2k.jpg';
	const POLYHAVEN_CLIFF = 'E:\\Tools-3D\\polyhaven\\textures\\cliff_side\\Diffuse_2k.jpg';
	const POLYHAVEN_SAND = 'E:\\Tools-3D\\polyhaven\\textures\\aerial_sand\\Diffuse_2k.jpg';
	const POLYHAVEN_FROST = 'E:\\Tools-3D\\polyhaven\\textures\\marble_01\\Diffuse_2k.jpg';

	let chunkProjects = $derived.by(() => projects.filter((p) => p.manifest.kind === 'open_world'));
	let glbCatalogProjects = $derived.by(() =>
		projects.filter((p) => Boolean(p.manifest.clockwork.glb_path))
	);
	let vnCatalogProjects = $derived.by(() =>
		projects.filter(
			(p) => p.manifest.kind === 'vn_episode' || Boolean(p.manifest.stage_vn.episode_zip_path)
		)
	);

	let activeChunk = $derived.by(() => {
		const hit = chunkProjects.find((p) => p.slug === selectedSlug);
		return hit ?? chunkProjects[0] ?? null;
	});

	// Chuỗi slug riêng: activeChunk đổi danh tính mỗi lần `projects` tải lại (sau mỗi nét điêu khắc),
	// còn slug thì không → sân khấu 3D chỉ dựng lại khi thật sự đổi ô.
	let activeChunkSlug = $derived(activeChunk?.slug ?? null);

	let neighborChunks = $derived.by(() => {
		if (!activeChunk) return [];
		return chunkProjects.filter(
			(p) =>
				p.slug !== activeChunk.slug &&
				p.manifest.planet.toLowerCase() === activeChunk.manifest.planet.toLowerCase() &&
				Math.abs(p.manifest.chunk_x - activeChunk.manifest.chunk_x) <= 1 &&
				Math.abs(p.manifest.chunk_z - activeChunk.manifest.chunk_z) <= 1
		);
	});

	// Workbench interaction modes
	type ToolMode = 'orbit' | 'sculpt' | 'place_glb' | 'audio_zone' | 'spawn_point' | 'vn_trigger';
	let toolMode = $state<ToolMode>('orbit');
	let brushMode = $state<'raise' | 'lower' | 'flatten' | 'smooth'>('raise');
	let brushRadius = $state(24);
	let brushStrength = $state(3.5);

	// Placement & Trigger form state
	let chosenMonumentSlug = $state('');
	let placeScale = $state(1.0);
	let placeRotDeg = $state(0);

	let audioZoneLabel = $state('Vùng Nhạc Gió Thung Lũng');
	let audioZoneRadius = $state(48);
	let audioZoneVolume = $state(0.75);

	let vnTriggerLabel = $state('Điểm Tương Tác Ký Ức');
	let vnTriggerEpisodeSlug = $state('');
	let vnTriggerRadius = $state(10);

	// New Chunk quick creator
	let showCreateChunk = $state(false);
	let newChunkPlanet = $state<'akunalia' | 'earth'>('akunalia');
	let newChunkX = $state(0);
	let newChunkZ = $state(0);
	let newChunkBiome = $state('zyberon-basin');
	let newChunkTitle = $state('Lòng Chảo Thánh Tích Zyberon [0, 0]');

	// Telemetry & busy states
	let lastStitchReport = $state<ChunkStitchReport | null>(null);
	let busyOp = $state(false);
	let showNeighbors = $state(true);
	let flyWasdActive = $state(false);
	let pointerCoords = $state<{ x: number; y: number; z: number } | null>(null);
	let loadedSplatCount = $state(0);

	// Hidden BYOA file inputs
	let splatFileInput = $state<HTMLInputElement | null>(null);
	let landscapeImgInput = $state<HTMLInputElement | null>(null);
	let ambientAudioInput = $state<HTMLInputElement | null>(null);
	let customGlbInput = $state<HTMLInputElement | null>(null);

	// Preview audio element
	let previewAudioEl = $state<HTMLAudioElement | null>(null);
	let playingZoneId = $state<string | null>(null);

	// Three.js viewport host & handles
	let viewportHost = $state<HTMLDivElement | null>(null);

	$effect(() => {
		if (!chosenMonumentSlug && glbCatalogProjects.length > 0) {
			chosenMonumentSlug = glbCatalogProjects[0].slug;
		}
		if (!vnTriggerEpisodeSlug && vnCatalogProjects.length > 0) {
			vnTriggerEpisodeSlug = vnCatalogProjects[0].slug;
		}
	});

	function sampleGridHeight(
		values: number[] | undefined,
		res: number,
		localX: number,
		localZ: number
	): number {
		if (!values || values.length !== res * res) return 3.6;
		const u = Math.max(0, Math.min(1, (localX + 128) / 256));
		const v = Math.max(0, Math.min(1, (localZ + 128) / 256));
		const gx = u * (res - 1);
		const gz = v * (res - 1);
		const x0 = Math.floor(gx);
		const z0 = Math.floor(gz);
		const x1 = Math.min(res - 1, x0 + 1);
		const z1 = Math.min(res - 1, z0 + 1);
		const fx = gx - x0;
		const fz = gz - z0;
		const h00 = values[z0 * res + x0] ?? 0;
		const h10 = values[z0 * res + x1] ?? 0;
		const h01 = values[z1 * res + x0] ?? 0;
		const h11 = values[z1 * res + x1] ?? 0;
		const hx0 = h00 + (h10 - h00) * fx;
		const hx1 = h01 + (h11 - h01) * fx;
		return Math.round((hx0 + (hx1 - hx0) * fz) * 100) / 100;
	}

	interface TerrainTextureSet {
		grass: THREE.Texture;
		cliff: THREE.Texture;
		sand: THREE.Texture;
		snow: THREE.Texture;
	}

	// 4 texture Poly Haven 2K nạp MỘT lần cho mỗi sân khấu, dùng chung cho ô chính và mọi ô lân cận
	function loadTerrainTextures(T: ThreeModule, manager: THREE.LoadingManager): TerrainTextureSet {
		const texLoader = new T.TextureLoader(manager);
		const loadTiled = (path: string) => {
			const tex = texLoader.load(mediaUrl(path));
			tex.wrapS = T.RepeatWrapping;
			tex.wrapT = T.RepeatWrapping;
			tex.colorSpace = T.SRGBColorSpace;
			return tex;
		};
		return {
			grass: loadTiled(POLYHAVEN_GRASS),
			cliff: loadTiled(POLYHAVEN_CLIFF),
			sand: loadTiled(POLYHAVEN_SAND),
			snow: loadTiled(POLYHAVEN_FROST)
		};
	}

	function createTriplanarTerrainMaterial(T: ThreeModule, tex: TerrainTextureSet): THREE.ShaderMaterial {
		return new T.ShaderMaterial({
			uniforms: {
				uGrassMap: { value: tex.grass },
				uCliffMap: { value: tex.cliff },
				uSandMap: { value: tex.sand },
				uSnowMap: { value: tex.snow },
				uWaterLevel: { value: 1.8 },
				uSunDir: { value: new T.Vector3(0.56, 0.74, 0.37).normalize() },
				uIsNeighbor: { value: 0.0 }
			},
			vertexShader: `
				varying vec3 vWorldPos;
				varying vec3 vWorldNormal;
				void main() {
					vec4 wp = modelMatrix * vec4(position, 1.0);
					vWorldPos = wp.xyz;
					vWorldNormal = normalize(mat3(modelMatrix) * normal);
					gl_Position = projectionMatrix * viewMatrix * wp;
				}
			`,
			fragmentShader: `
				uniform sampler2D uGrassMap;
				uniform sampler2D uCliffMap;
				uniform sampler2D uSandMap;
				uniform sampler2D uSnowMap;
				uniform float uWaterLevel;
				uniform vec3 uSunDir;
				uniform float uIsNeighbor;

				varying vec3 vWorldPos;
				varying vec3 vWorldNormal;

				vec3 sampleTriplanar(sampler2D tex, vec3 wp, vec3 wn, float scale) {
					vec3 blend = pow(abs(wn), vec3(4.0));
					blend /= max(0.0001, blend.x + blend.y + blend.z);
					vec3 cx = texture2D(tex, wp.zy * scale).rgb;
					vec3 cy = texture2D(tex, wp.xz * scale).rgb;
					vec3 cz = texture2D(tex, wp.xy * scale).rgb;
					return cx * blend.x + cy * blend.y + cz * blend.z;
				}

				void main() {
					vec3 n = normalize(vWorldNormal);
					float slope = 1.0 - clamp(n.y, 0.0, 1.0);
					float h = vWorldPos.y;

					vec3 grass = sampleTriplanar(uGrassMap, vWorldPos, n, 0.055);
					vec3 cliff = sampleTriplanar(uCliffMap, vWorldPos, n, 0.045);
					vec3 sand  = sampleTriplanar(uSandMap,  vWorldPos, n, 0.075);
					vec3 snow  = sampleTriplanar(uSnowMap,  vWorldPos, n, 0.050) * vec3(0.96, 0.99, 1.04);

					float shoreMask = 1.0 - smoothstep(uWaterLevel - 0.5, uWaterLevel + 1.35, h);
					float cliffMask = smoothstep(0.24, 0.56, slope);
					float snowMask  = smoothstep(16.5, 23.0, h) * (1.0 - cliffMask * 0.55);

					vec3 albedo = mix(grass, sand, shoreMask);
					albedo = mix(albedo, cliff, cliffMask);
					albedo = mix(albedo, snow, snowMask);

					float ndl = max(dot(n, uSunDir), 0.0);
					float hemi = 0.34 + 0.22 * (n.y * 0.5 + 0.5);
					vec3 lit = albedo * (hemi + ndl * 0.88 * vec3(1.04, 0.98, 0.90));

					// Subtle atmospheric aerial perspective
					float dist = length(cameraPosition - vWorldPos);
					float fogF = clamp((dist - 140.0) / 520.0, 0.0, 0.52);
					lit = mix(lit, vec3(0.09, 0.14, 0.21), fogF);

					if (uIsNeighbor > 0.5) {
						lit *= vec3(0.88, 0.93, 0.98);
					}
					gl_FragColor = vec4(lit, 1.0);
				}
			`
		});
	}

	function createRippledWaterMaterial(T: ThreeModule): THREE.ShaderMaterial {
		return new T.ShaderMaterial({
			transparent: true,
			depthWrite: false,
			uniforms: {
				uTime: { value: 0 },
				uSunDir: { value: new T.Vector3(0.56, 0.74, 0.37).normalize() }
			},
			vertexShader: `
				uniform float uTime;
				varying vec3 vWorldPos;
				void main() {
					vec3 p = position;
					vec4 wp = modelMatrix * vec4(p, 1.0);
					float wave = sin(wp.x * 0.14 + uTime * 1.35) * 0.06
					           + cos(wp.z * 0.17 - uTime * 1.1) * 0.05;
					wp.y += wave;
					vWorldPos = wp.xyz;
					gl_Position = projectionMatrix * viewMatrix * wp;
				}
			`,
			fragmentShader: `
				uniform float uTime;
				uniform vec3 uSunDir;
				varying vec3 vWorldPos;
				void main() {
					float nx = cos(vWorldPos.x * 0.24 + uTime * 1.5) * 0.08
					         + sin((vWorldPos.x + vWorldPos.z) * 0.19 - uTime * 1.1) * 0.05;
					float nz = -sin(vWorldPos.z * 0.22 - uTime * 1.25) * 0.08;
					vec3 n = normalize(vec3(nx, 1.0, nz));
					vec3 viewDir = normalize(cameraPosition - vWorldPos);
					float fresnel = pow(1.0 - max(dot(viewDir, n), 0.0), 3.2);
					vec3 halfV = normalize(uSunDir + viewDir);
					float spec = pow(max(dot(n, halfV), 0.0), 96.0);

					vec3 deepCol = vec3(0.05, 0.20, 0.28);
					vec3 skyRefl = vec3(0.28, 0.56, 0.70);
					vec3 col = mix(deepCol, skyRefl, clamp(fresnel * 0.85, 0.08, 0.88))
					         + vec3(1.0, 0.95, 0.84) * spec * 0.75;
					gl_FragColor = vec4(col, 0.80);
				}
			`
		});
	}

	function validGridRes(values: number[] | undefined, res: number): number {
		return res >= 2 && values && values.length === res * res ? res : 65;
	}

	function buildTerrainGeometry(T: ThreeModule, values: number[] | undefined, res: number): THREE.BufferGeometry {
		const r = validGridRes(values, res);
		const geo = new T.PlaneGeometry(256, 256, r - 1, r - 1);
		geo.rotateX(-Math.PI / 2);
		writeTerrainHeights(geo, values, r);
		return geo;
	}

	// Cập nhật cao độ TẠI CHỖ sau mỗi nét điêu khắc — không dựng lại geometry/material/renderer
	function writeTerrainHeights(geo: THREE.BufferGeometry, values: number[] | undefined, r: number) {
		const pos = geo.attributes.position as THREE.BufferAttribute;
		if (values && values.length === r * r) {
			for (let i = 0; i < pos.count; i++) {
				pos.setY(i, values[i] ?? 0);
			}
		}
		pos.needsUpdate = true;
		geo.computeVertexNormals();
		geo.computeBoundingBox();
		geo.computeBoundingSphere();
	}

	function buildInstancedGrassTufts(
		T: ThreeModule,
		values: number[] | undefined,
		res: number,
		waterLevel: number,
		density: number,
		placements: ChunkPlacementItem[]
	): THREE.InstancedMesh | null {
		const countTarget = Math.floor(Math.max(0, Math.min(1, density)) * 2200);
		if (countTarget < 10 || !values || values.length !== res * res) return null;

		// Natural curved 3-blade grass tuft geometry (NOT a toy primitive building!)
		const bladeGeo = new T.BufferGeometry();
		const verts: number[] = [];
		const uvs: number[] = [];
		for (let b = 0; b < 3; b++) {
			const ang = (b * Math.PI) / 3;
			const dx = Math.cos(ang) * 0.14;
			const dz = Math.sin(ang) * 0.14;
			const bendX = Math.cos(ang + 0.6) * 0.12;
			const bendZ = Math.sin(ang + 0.6) * 0.12;
			verts.push(-dx, 0, -dz, dx, 0, dz, bendX, 0.78, bendZ);
			uvs.push(0, 0, 1, 0, 0.5, 1);
		}
		bladeGeo.setAttribute('position', new T.Float32BufferAttribute(verts, 3));
		bladeGeo.setAttribute('uv', new T.Float32BufferAttribute(uvs, 2));
		bladeGeo.computeVertexNormals();

		const mat = new T.MeshStandardMaterial({
			color: new T.Color('#4a7c44'),
			roughness: 0.86,
			metalness: 0.0,
			side: T.DoubleSide
		});

		const mesh = new T.InstancedMesh(bladeGeo, mat, countTarget);
		const dummy = new T.Object3D();
		let placed = 0;
		let seed = 1337;
		const rand = () => {
			seed = (seed * 1664525 + 1013904223) >>> 0;
			return seed / 4294967296;
		};

		for (let attempt = 0; attempt < countTarget * 3 && placed < countTarget; attempt++) {
			const lx = (rand() - 0.5) * 246;
			const lz = (rand() - 0.5) * 246;
			const h = sampleGridHeight(values, res, lx, lz);
			if (h < waterLevel + 0.65 || h > 16.0) continue;

			// Keep monument footprints clear
			let nearMonument = false;
			for (const pl of placements) {
				const d2 = (lx - pl.x) ** 2 + (lz - pl.z) ** 2;
				if (d2 < 18 * 18) {
					nearMonument = true;
					break;
				}
			}
			if (nearMonument) continue;

			dummy.position.set(lx, h - 0.03, lz);
			dummy.rotation.set(0, rand() * Math.PI * 2, 0);
			const s = 0.75 + rand() * 0.85;
			dummy.scale.set(s, s * (0.85 + rand() * 0.5), s);
			dummy.updateMatrix();
			mesh.setMatrixAt(placed, dummy.matrix);
			placed++;
		}
		mesh.count = placed;
		mesh.instanceMatrix.needsUpdate = true;
		return mesh;
	}

	let stageCtrl: {
		captureMangaPlates2K: () => { beauty: string; depth: string } | null;
		resetCamera: () => void;
	} | null = null;

	// ---------------------------------------------------------------------------------------------
	// Sân khấu 3D Thế Giới Mở (Kế hoạch VRAM v2 · Đợt A · A5)
	// - Renderer dùng chung (webgl-stage): KHÔNG tạo context mới khi đổi ô / sau mỗi nét điêu khắc.
	// - Effect sân khấu chỉ phụ thuộc slug ô đang mở. Địa hình, cỏ, công trình, vòng nhạc/trigger, splat
	//   được đồng bộ bằng các effect riêng, cập nhật tại chỗ thay vì dựng lại toàn bộ.
	// - Vòng render theo nhu cầu: đứng yên + tắt sóng → 0 rAF.
	// ---------------------------------------------------------------------------------------------
	interface TerrainEntry {
		mesh: THREE.Mesh;
		geo: THREE.BufferGeometry;
		mat: THREE.ShaderMaterial;
		water: THREE.Mesh;
		res: number;
	}
	interface PlacementEntry {
		path: string;
		root: THREE.Object3D | null;
		alive: boolean;
	}
	interface GlbCacheEntry {
		refs: number;
		template: THREE.Object3D | null;
		promise: Promise<THREE.Object3D | null>;
	}
	interface ChunkStage {
		T: ThreeModule;
		renderer: THREE.WebGLRenderer;
		scene: THREE.Scene;
		camera: THREE.PerspectiveCamera;
		controls: OrbitControls;
		loop: OnDemandLoop;
		textures: TerrainTextureSet;
		waterGeo: THREE.PlaneGeometry;
		waterMat: THREE.ShaderMaterial;
		terrain: Map<string, TerrainEntry>;
		mainSlug: string;
		grass: THREE.InstancedMesh | null;
		markers: THREE.Group | null;
		placements: Map<string, PlacementEntry>;
		glbCache: Map<string, GlbCacheEntry>;
		gltfLoader: GLTFLoader;
		spark: SparkRenderer;
		splat: SplatMesh | null;
		splatPath: string;
		splatToken: number;
		splatSettleFrames: number;
		disposed: boolean;
	}

	let stage: ChunkStage | null = null;
	// Tăng mỗi khi dựng xong sân khấu mới → các effect đồng bộ nội dung chạy lại với sân khấu đó
	let stageVersion = $state(0);
	// Sóng nước là hoạt ảnh liên tục → mặc định TẮT để tab 02 về 0% GPU khi đứng yên
	let wavesEnabled = $state(false);

	function acquireGlbTemplate(s: ChunkStage, path: string): Promise<THREE.Object3D | null> {
		let entry = s.glbCache.get(path);
		if (!entry) {
			const created: GlbCacheEntry = {
				refs: 0,
				template: null,
				promise: new Promise<THREE.Object3D | null>((resolve) => {
					s.gltfLoader.load(
						mediaUrl(path),
						(gltf) => resolve(gltf.scene),
						undefined,
						() => resolve(null) // bỏ qua .glb thiếu
					);
				})
			};
			created.promise.then((tpl) => {
				created.template = tpl;
				// Về muộn: sân khấu đã đóng hoặc không còn vị trí nào dùng → dọn ngay
				if (tpl && (s.disposed || created.refs <= 0)) {
					disposeObject3DDeep(tpl);
					if (s.glbCache.get(path) === created) s.glbCache.delete(path);
				}
			});
			s.glbCache.set(path, created);
			entry = created;
		}
		entry.refs++;
		return entry.promise;
	}

	function releaseGlbTemplate(s: ChunkStage, path: string) {
		const entry = s.glbCache.get(path);
		if (!entry) return;
		entry.refs--;
		if (entry.refs > 0) return;
		s.glbCache.delete(path);
		if (entry.template) disposeObject3DDeep(entry.template);
		// chưa nạp xong → promise.then ở trên tự dọn khi về (refs <= 0)
	}

	// (1) Sân khấu: chỉ dựng lại khi đổi ô (slug) hoặc khung chứa — KHÔNG phụ thuộc nội dung manifest
	$effect(() => {
		const host = viewportHost;
		const slug = activeChunkSlug;
		// C2: Chờ 2D mặc định → chỉ mượn renderer khi người dùng bấm ▶
		const active3d = stageMode.chunk3d;
		if (!host || !slug || !active3d) return;

		let disposed = false;
		let teardown: (() => void) | null = null;

		(async () => {
			const T = await import('three');
			const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js');
			const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
			const { DRACOLoader } = await import('three/examples/jsm/loaders/DRACOLoader.js');
			const { SparkRenderer } = await import('@sparkjsdev/spark');
			if (disposed) return;

			const w0 = host.clientWidth || 960;
			const h0 = host.clientHeight || 560;
			const dpr = () => Math.min(window.devicePixelRatio || 1, 2);
			const lease: StageLease = await acquireStage(
				host,
				{
					toneMapping: T.ACESFilmicToneMapping,
					toneMappingExposure: 1.06,
					outputColorSpace: T.SRGBColorSpace,
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

			const scene = new T.Scene();
			scene.background = new T.Color('#0b1320');
			scene.fog = new T.FogExp2('#0e1929', 0.0014);

			// SparkRenderer cho Gaussian Splatting thật (.ply / .spz)
			const spark = new SparkRenderer({ renderer });
			scene.add(spark);

			const camera = new T.PerspectiveCamera(48, w0 / Math.max(1, h0), 0.25, 2200);
			camera.position.set(16, 42, 92);

			const controls = new OrbitControls(camera, renderer.domElement);
			controls.enableDamping = true;
			controls.dampingFactor = 0.07;
			controls.target.set(6, 8, -14);
			controls.maxDistance = 680;
			controls.minDistance = 4;

			scene.add(new T.HemisphereLight('#b8dcff', '#273326', 1.15));
			const sun = new T.DirectionalLight('#fff1d6', 2.45);
			sun.position.set(110, 165, 85);
			scene.add(sun);

			const pressedKeys = new Set<string>();
			const fwd = new T.Vector3();
			const right = new T.Vector3();
			const delta = new T.Vector3();

			let s: ChunkStage;
			const loop = createOnDemandLoop((dt) => {
				let moving = false;
				if (untrack(() => wavesEnabled)) s.waterMat.uniforms.uTime.value += dt;
				if (untrack(() => flyWasdActive) && pressedKeys.size > 0) {
					const speed = (pressedKeys.has('ShiftLeft') || pressedKeys.has('ShiftRight') ? 68 : 28) * dt;
					camera.getWorldDirection(fwd);
					right.crossVectors(fwd, camera.up).normalize();
					delta.set(0, 0, 0);
					if (pressedKeys.has('KeyW')) delta.addScaledVector(fwd, speed);
					if (pressedKeys.has('KeyS')) delta.addScaledVector(fwd, -speed);
					if (pressedKeys.has('KeyD')) delta.addScaledVector(right, speed);
					if (pressedKeys.has('KeyA')) delta.addScaledVector(right, -speed);
					if (pressedKeys.has('KeyE') || pressedKeys.has('Space')) delta.y += speed;
					if (pressedKeys.has('KeyQ')) delta.y -= speed;
					camera.position.add(delta);
					controls.target.add(delta);
					moving = true;
				}
				if (controls.update()) moving = true;
				if (s.splat && s.splatSettleFrames > 0) {
					// Worker của Spark sắp xếp splat bất đồng bộ — vẽ thêm vài khung để kết quả cuối kịp lên hình
					s.splatSettleFrames--;
					moving = true;
				}
				renderer.render(scene, camera);
				return moving;
			});

			const manager = new T.LoadingManager();
			manager.onLoad = () => loop.invalidate();
			manager.onProgress = () => loop.invalidate();

			const draco = new DRACOLoader();
			draco.setDecoderPath('/draco/');
			const gltfLoader = new GLTFLoader();
			gltfLoader.setDRACOLoader(draco);
			gltfLoader.setKTX2Loader(ktx2Loader);

			const waterGeo = new T.PlaneGeometry(256, 256, 48, 48);
			waterGeo.rotateX(-Math.PI / 2);

			s = {
				T,
				renderer,
				scene,
				camera,
				controls,
				loop,
				textures: loadTerrainTextures(T, manager),
				waterGeo,
				waterMat: createRippledWaterMaterial(T),
				terrain: new Map(),
				mainSlug: slug,
				grass: null,
				markers: null,
				placements: new Map(),
				glbCache: new Map(),
				gltfLoader,
				spark,
				splat: null,
				splatPath: '',
				splatToken: 0,
				splatSettleFrames: 0,
				disposed: false
			};

			const onControlsChange = () => {
				s.splatSettleFrames = 30;
				loop.invalidate();
			};
			controls.addEventListener('change', onControlsChange);

			// Pointer raycasting for Sculpt / Monument Placement / Audio Zone / VN Trigger
			const raycaster = new T.Raycaster();
			const ndc = new T.Vector2();
			let pointerDownPos: { x: number; y: number } | null = null;

			const getTerrainHit = (ev: PointerEvent): THREE.Vector3 | null => {
				const main = s.terrain.get(s.mainSlug);
				if (!main) return null;
				const rect = renderer.domElement.getBoundingClientRect();
				ndc.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
				ndc.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
				raycaster.setFromCamera(ndc, camera);
				const hits = raycaster.intersectObject(main.mesh, false);
				return hits.length > 0 ? hits[0].point : null;
			};

			const onPointerMove = (ev: PointerEvent) => {
				const pt = getTerrainHit(ev);
				if (pt) {
					pointerCoords = {
						x: Math.round(pt.x * 10) / 10,
						y: Math.round(pt.y * 100) / 100,
						z: Math.round(pt.z * 10) / 10
					};
				}
			};

			const onPointerDown = (ev: PointerEvent) => {
				if (ev.button === 0) {
					pointerDownPos = { x: ev.clientX, y: ev.clientY };
				}
			};

			const onPointerUp = (ev: PointerEvent) => {
				if (ev.button !== 0 || !pointerDownPos) return;
				const moved = Math.hypot(ev.clientX - pointerDownPos.x, ev.clientY - pointerDownPos.y);
				pointerDownPos = null;
				if (moved > 5) return;
				const modeNow = untrack(() => toolMode);
				if (modeNow === 'orbit') return;
				const pt = getTerrainHit(ev);
				if (!pt) return;
				void handleTerrainClickAction(modeNow, pt.x, pt.y, pt.z);
			};

			renderer.domElement.addEventListener('pointermove', onPointerMove);
			renderer.domElement.addEventListener('pointerdown', onPointerDown);
			renderer.domElement.addEventListener('pointerup', onPointerUp);

			// WASD FreeCam flight inside Open-World Chunk Workbench
			const onKeyDown = (ev: KeyboardEvent) => {
				const tag = (ev.target as HTMLElement | null)?.tagName;
				if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
				pressedKeys.add(ev.code);
				if (untrack(() => flyWasdActive)) loop.setContinuous('wasd', true);
			};
			const onKeyUp = (ev: KeyboardEvent) => {
				pressedKeys.delete(ev.code);
				if (pressedKeys.size === 0) loop.setContinuous('wasd', false);
			};
			const onBlur = () => {
				pressedKeys.clear();
				loop.setContinuous('wasd', false);
			};
			window.addEventListener('keydown', onKeyDown);
			window.addEventListener('keyup', onKeyUp);
			window.addEventListener('blur', onBlur);

			const ro = new ResizeObserver(() => {
				if (s.disposed || !lease.active) return;
				const w = Math.max(320, host.clientWidth);
				const h = Math.max(240, host.clientHeight);
				camera.aspect = w / h;
				camera.updateProjectionMatrix();
				renderer.setSize(w, h);
				loop.invalidate();
			});
			ro.observe(host);

			stageCtrl = {
				resetCamera: () => {
					camera.position.set(0, 74, 156);
					controls.target.set(0, 6, 0);
					controls.update();
					loop.invalidate();
				},
				captureMangaPlates2K: () => {
					const prevAspect = camera.aspect;
					const targetW = 2560;
					const targetH = 1440;

					renderer.setPixelRatio(1);
					renderer.setSize(targetW, targetH, false);
					camera.aspect = targetW / targetH;
					camera.updateProjectionMatrix();

					// render() rồi toDataURL() ngay trong cùng tác vụ → không cần preserveDrawingBuffer
					renderer.render(scene, camera);
					const beauty = renderer.domElement.toDataURL('image/png');

					const prevOverride = scene.overrideMaterial;
					const prevBg = scene.background;
					const depthMat = new T.MeshDepthMaterial();
					scene.overrideMaterial = depthMat;
					scene.background = new T.Color('#000000');
					renderer.render(scene, camera);
					const depth = renderer.domElement.toDataURL('image/png');
					scene.overrideMaterial = prevOverride;
					scene.background = prevBg;
					depthMat.dispose();

					renderer.setPixelRatio(dpr());
					renderer.setSize(Math.max(320, host.clientWidth), Math.max(240, host.clientHeight), false);
					camera.aspect = prevAspect;
					camera.updateProjectionMatrix();
					loop.invalidate();
					return { beauty, depth };
				}
			};

			teardown = () => {
				if (s.disposed) return;
				s.disposed = true;
				stageCtrl = null;
				loop.dispose();
				ro.disconnect();
				window.removeEventListener('keydown', onKeyDown);
				window.removeEventListener('keyup', onKeyUp);
				window.removeEventListener('blur', onBlur);
				// Canvas dùng chung sống suốt đời app → phải gỡ listener
				renderer.domElement.removeEventListener('pointermove', onPointerMove);
				renderer.domElement.removeEventListener('pointerdown', onPointerDown);
				renderer.domElement.removeEventListener('pointerup', onPointerUp);
				controls.removeEventListener('change', onControlsChange);
				controls.dispose();

				const seen = new Set<unknown>();
				s.splatToken++;
				s.splat?.removeFromParent();
				s.splat?.dispose();
				s.splat = null;
				disposeSparkRenderer(spark);
				// Template .glb không nằm trong scene (scene chỉ chứa bản clone dùng chung geometry/material)
				for (const entry of s.glbCache.values()) {
					if (entry.template) disposeObject3DDeep(entry.template, {}, seen);
				}
				s.glbCache.clear();
				// Gồm địa hình ô chính + ô kề, 4 texture Poly Haven dùng chung, nước, cỏ, vòng nhạc/trigger
				disposeObject3DDeep(scene, {}, seen);
				s.waterGeo.dispose();
				s.waterMat.dispose();
				draco.dispose();
				lease.release();
				if (stage === s) stage = null;
			};

			stage = s;
			stageVersion++;
			loop.invalidate();
		})().catch((err) => {
			console.error('[chunk-stage] Lỗi dựng sân khấu 3D:', err);
			teardown?.();
		});

		return () => {
			disposed = true;
			teardown?.();
		};
	});

	// (2) Địa hình ô chính + ô kề: thêm/bớt ô, cập nhật cao độ tại chỗ, mực nước
	$effect(() => {
		const _v = stageVersion;
		const chunk = activeChunk;
		const neighbors = showNeighbors ? neighborChunks : [];
		const s = stage;
		if (!s || !chunk || s.disposed) return;
		const entries = [chunk, ...neighbors].map((c, idx) => ({
			slug: c.slug,
			isNeighbor: idx > 0,
			dx: (c.manifest.chunk_x - chunk.manifest.chunk_x) * 256,
			dz: (c.manifest.chunk_z - chunk.manifest.chunk_z) * 256,
			values: c.manifest.chunks.heightmap_values,
			res: c.manifest.chunks.grid_resolution ?? 65,
			water: c.manifest.chunks.water_level ?? chunk.manifest.chunks.water_level ?? 1.8
		}));
		untrack(() => {
			const T = s.T;
			const want = new Set(entries.map((e) => e.slug));
			for (const [slug, t] of s.terrain) {
				if (want.has(slug)) continue;
				s.scene.remove(t.mesh, t.water);
				t.geo.dispose();
				t.mat.dispose(); // KHÔNG dọn texture: dùng chung với các ô khác
				s.terrain.delete(slug);
			}
			for (const e of entries) {
				const r = validGridRes(e.values, e.res);
				let t = s.terrain.get(e.slug);
				if (!t) {
					const geo = buildTerrainGeometry(T, e.values, r);
					const mat = createTriplanarTerrainMaterial(T, s.textures);
					const mesh = new T.Mesh(geo, mat);
					mesh.name = e.isNeighbor ? `NeighborTerrain:${e.slug}` : 'ActiveChunkTerrain';
					const water = new T.Mesh(s.waterGeo, s.waterMat);
					s.scene.add(mesh, water);
					t = { mesh, geo, mat, water, res: r };
					s.terrain.set(e.slug, t);
				} else if (t.res !== r) {
					const geo = buildTerrainGeometry(T, e.values, r);
					t.geo.dispose();
					t.mesh.geometry = geo;
					t.geo = geo;
					t.res = r;
				} else {
					writeTerrainHeights(t.geo, e.values, r);
				}
				t.mat.uniforms.uIsNeighbor.value = e.isNeighbor ? 1.0 : 0.0;
				t.mat.uniforms.uWaterLevel.value = e.water;
				t.mesh.position.set(e.dx, 0, e.dz);
				t.water.position.set(e.dx, e.water, e.dz);
			}
			s.mainSlug = chunk.slug;
			s.loop.invalidate();
		});
	});

	// (3) Cỏ instanced của ô chính: dựng lại khi cao độ / mật độ / vị trí kỳ quan đổi (rẻ: 1 InstancedMesh)
	$effect(() => {
		const _v = stageVersion;
		const chunk = activeChunk;
		const s = stage;
		if (!s || !chunk || s.disposed) return;
		const c = chunk.manifest.chunks;
		const values = c.heightmap_values;
		const res = c.grid_resolution ?? 65;
		const water = c.water_level ?? 1.8;
		const density = c.foliage_density ?? 0.55;
		const placements = (c.placements ?? []).map((p) => ({ ...p }));
		untrack(() => {
			if (s.grass) {
				s.scene.remove(s.grass);
				disposeObject3DDeep(s.grass);
				s.grass = null;
			}
			const grass = buildInstancedGrassTufts(s.T, values, res, water, density, placements);
			if (grass) {
				s.scene.add(grass);
				s.grass = grass;
			}
			s.loop.invalidate();
		});
	});

	// (4) Kỳ quan .glb trên ô chính + ô kề: đối chiếu theo id, cache .glb theo đường dẫn + đếm tham chiếu
	$effect(() => {
		const _v = stageVersion;
		const chunk = activeChunk;
		const neighbors = showNeighbors ? neighborChunks : [];
		const s = stage;
		if (!s || !chunk || s.disposed) return;
		const desired = [chunk, ...neighbors].flatMap((c) => {
			const dx = (c.manifest.chunk_x - chunk.manifest.chunk_x) * 256;
			const dz = (c.manifest.chunk_z - chunk.manifest.chunk_z) * 256;
			const values = c.manifest.chunks.heightmap_values;
			const res = c.manifest.chunks.grid_resolution ?? 65;
			return (c.manifest.chunks.placements ?? [])
				.filter((pl) => Boolean(pl.glb_path))
				.map((pl) => {
					const groundY = sampleGridHeight(values, res, pl.x, pl.z);
					return {
						key: `${c.slug}:${pl.id}`,
						path: pl.glb_path,
						x: dx + pl.x,
						y: Math.abs(pl.y) < 0.01 ? groundY - 0.12 : pl.y,
						z: dz + pl.z,
						rotY: (pl.rot_y_deg * Math.PI) / 180,
						scale: Math.max(0.05, pl.scale || 1.0)
					};
				});
		});
		untrack(() => {
			const wantByKey = new Map(desired.map((d) => [d.key, d]));
			for (const [key, entry] of s.placements) {
				const want = wantByKey.get(key);
				if (want && want.path === entry.path) continue;
				entry.alive = false;
				if (entry.root) s.scene.remove(entry.root);
				releaseGlbTemplate(s, entry.path);
				s.placements.delete(key);
			}
			const applyTransform = (root: THREE.Object3D, d: (typeof desired)[number]) => {
				root.position.set(d.x, d.y, d.z);
				root.rotation.y = d.rotY;
				root.scale.setScalar(d.scale);
			};
			for (const d of desired) {
				const existing = s.placements.get(d.key);
				if (existing) {
					if (existing.root) applyTransform(existing.root, d);
					continue;
				}
				const entry: PlacementEntry = { path: d.path, root: null, alive: true };
				s.placements.set(d.key, entry);
				void acquireGlbTemplate(s, d.path).then((tpl) => {
					if (!tpl || !entry.alive || s.disposed) return;
					const root = tpl.clone(); // chung geometry/material với template
					entry.root = root;
					applyTransform(root, wantByKey.get(d.key) ?? d);
					s.scene.add(root);
					s.loop.invalidate();
				});
			}
			s.loop.invalidate();
		});
	});

	// (5) Vòng vùng nhạc + điểm VN (LineLoop mảnh) của ô chính
	$effect(() => {
		const _v = stageVersion;
		const chunk = activeChunk;
		const s = stage;
		if (!s || !chunk || s.disposed) return;
		const c = chunk.manifest.chunks;
		const values = c.heightmap_values;
		const gridRes = c.grid_resolution ?? 65;
		const waterLevel = c.water_level ?? 1.8;
		const zones = (c.audio_zones ?? []).map((z) => ({ x: z.x, z: z.z, radius: z.radius }));
		const triggers = (c.vn_triggers ?? []).map((t) => ({ x: t.x, z: t.z, radius: t.radius }));
		untrack(() => {
			const T = s.T;
			if (s.markers) {
				s.scene.remove(s.markers);
				disposeObject3DDeep(s.markers);
			}
			const group = new T.Group();
			group.name = 'ChunkMarkers';
			const ring = (cx: number, cz: number, radius: number, segs: number, lift: number, color: string) => {
				const pts: THREE.Vector3[] = [];
				for (let i = 0; i <= segs; i++) {
					const a = (i / segs) * Math.PI * 2;
					const rx = cx + Math.cos(a) * radius;
					const rz = cz + Math.sin(a) * radius;
					pts.push(new T.Vector3(rx, sampleGridHeight(values, gridRes, rx, rz) + lift, rz));
				}
				group.add(new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color })));
			};
			// Chunk boundary brass hairline frame (pure LineLoop wire, zero solid primitive!)
			const borderPts = [
				new T.Vector3(-128, waterLevel + 0.35, -128),
				new T.Vector3(128, waterLevel + 0.35, -128),
				new T.Vector3(128, waterLevel + 0.35, 128),
				new T.Vector3(-128, waterLevel + 0.35, 128)
			];
			group.add(
				new T.LineLoop(
					new T.BufferGeometry().setFromPoints(borderPts),
					new T.LineBasicMaterial({ color: '#d4a853', transparent: true, opacity: 0.65 })
				)
			);
			for (const az of zones) ring(az.x, az.z, az.radius, 48, 0.35, '#3bc9db');
			for (const vt of triggers) ring(vt.x, vt.z, vt.radius || 8, 36, 0.45, '#f59f00');
			s.scene.add(group);
			s.markers = group;
			s.loop.invalidate();
		});
	});

	// (6) Gaussian Splat (.ply / .spz) qua Spark — token chống nạp muộn
	$effect(() => {
		const _v = stageVersion;
		const chunk = activeChunk;
		const s = stage;
		if (!s || !chunk || s.disposed) return;
		const splatPath = chunk.manifest.chunks.splat_path?.trim() ?? '';
		const waterLevel = chunk.manifest.chunks.water_level ?? 1.8;
		untrack(() => {
			if (splatPath === s.splatPath) return;
			s.splatPath = splatPath;
			const token = ++s.splatToken;
			if (s.splat) {
				s.scene.remove(s.splat);
				s.splat.dispose();
				s.splat = null;
			}
			loadedSplatCount = 0;
			s.loop.invalidate();
			if (!splatPath) return;
			(async () => {
				try {
					const { SplatFileType, SplatMesh } = await import('@sparkjsdev/spark');
					const res = await fetch(mediaUrl(splatPath));
					if (!res.ok || token !== s.splatToken || s.disposed) return;
					const buf = await res.arrayBuffer();
					if (token !== s.splatToken || s.disposed) return;
					const lower = splatPath.toLowerCase();
					const fileType = lower.endsWith('.spz')
						? SplatFileType.SPZ
						: lower.endsWith('.splat')
							? SplatFileType.SPLAT
							: SplatFileType.PLY;
					const fileName = splatPath.split(/[\\/]/).pop() ?? 'scene.ply';
					const sm = new SplatMesh({ fileBytes: new Uint8Array(buf), fileType, fileName });
					await sm.initialized;
					if (token !== s.splatToken || s.disposed) {
						sm.dispose();
						return;
					}
					sm.position.set(-54, waterLevel + 6.5, -78);
					s.scene.add(sm);
					s.splat = sm;
					s.splatSettleFrames = 30;
					loadedSplatCount = sm.packedSplats?.numSplats ?? 0;
					s.loop.invalidate();
				} catch {
					if (token === s.splatToken) loadedSplatCount = 0;
				}
			})();
		});
	});

	// Sóng nước: hoạt ảnh liên tục chỉ khi người dùng bật
	$effect(() => {
		const on = wavesEnabled;
		const _v = stageVersion;
		stage?.loop.setContinuous('waves', on);
	});


	async function handleTerrainClickAction(mode: ToolMode, x: number, y: number, z: number) {
		if (!activeChunk || busyOp) return;
		const rx = Math.round(x * 100) / 100;
		const ry = Math.round(y * 100) / 100;
		const rz = Math.round(z * 100) / 100;

		if (mode === 'sculpt') {
			busyOp = true;
			try {
				const targetOrStrength = brushMode === 'flatten' ? ry : brushStrength;
				const rep = await api.chunksSculptTerrain(
					activeChunk.slug,
					rx,
					rz,
					brushRadius,
					targetOrStrength,
					brushMode
				);
				lastStitchReport = rep;
				await onProjectMutated(
					rep.project,
					`Đã điêu khắc địa hình (${brushMode}) & khâu biên liền mạch (sai số biên: ${rep.max_seam_error_m.toFixed(3)}m).`
				);
			} catch (err) {
				onNotify(err instanceof Error ? err.message : String(err), true);
			} finally {
				busyOp = false;
			}
			return;
		}

		const cloned = JSON.parse(JSON.stringify(activeChunk.manifest)) as ProjectManifest;

		if (mode === 'place_glb') {
			const srcProj = glbCatalogProjects.find((p) => p.slug === chosenMonumentSlug);
			const glbPath = srcProj?.manifest.clockwork.glb_path;
			if (!srcProj || !glbPath) {
				onNotify('Hãy chọn kỳ quan .glb hợp lệ để đặt lên mặt đất Chunk.', true);
				return;
			}
			const item: ChunkPlacementItem = {
				id: `pl_${Date.now()}`,
				slug: srcProj.slug,
				title: srcProj.title,
				glb_path: glbPath,
				x: rx,
				y: ry,
				z: rz,
				rot_y_deg: placeRotDeg,
				scale: placeScale
			};
			cloned.chunks.placements = [...(cloned.chunks.placements ?? []), item];
			await onSaveManifest(cloned, activeChunk.slug);
			toolMode = 'orbit';
			return;
		}

		if (mode === 'audio_zone') {
			const defaultAudio =
				cloned.bgm_audio_path ?? cloned.audio_paths[0] ?? '';
			if (!defaultAudio) {
				onNotify('Hãy nạp tệp nhạc nền (.wav/.mp3/.flac) trước khi đặt Vùng Âm Thanh.', true);
				ambientAudioInput?.click();
				return;
			}
			const zone: AmbientAudioZone = {
				id: `az_${Date.now()}`,
				label: audioZoneLabel.trim() || 'Vùng Nhạc Môi Trường',
				audio_path: defaultAudio,
				x: rx,
				z: rz,
				radius: audioZoneRadius,
				volume: audioZoneVolume
			};
			cloned.chunks.audio_zones = [...(cloned.chunks.audio_zones ?? []), zone];
			await onSaveManifest(cloned, activeChunk.slug);
			toolMode = 'orbit';
			return;
		}

		if (mode === 'spawn_point') {
			const sp: ChunkSpawnPoint = {
				id: `sp_${Date.now()}`,
				label: `Điểm Xuất Phát (${rx}m, ${rz}m)`,
				x: rx,
				y: ry + 1.7,
				z: rz,
				yaw_deg: 0
			};
			cloned.chunks.spawn_points = [...(cloned.chunks.spawn_points ?? []), sp];
			await onSaveManifest(cloned, activeChunk.slug);
			toolMode = 'orbit';
			return;
		}

		if (mode === 'vn_trigger') {
			const epProj = vnCatalogProjects.find((p) => p.slug === vnTriggerEpisodeSlug);
			const trig: ChunkVnTrigger = {
				id: `vnt_${Date.now()}`,
				label: vnTriggerLabel.trim() || 'Điểm Kích Hoạt Visual Novel',
				episode_slug: vnTriggerEpisodeSlug || activeChunk.slug,
				local_episode_path: epProj?.manifest.stage_vn.episode_zip_path ?? null,
				x: rx,
				y: ry + 1.0,
				z: rz,
				radius: vnTriggerRadius
			};
			cloned.chunks.vn_triggers = [...(cloned.chunks.vn_triggers ?? []), trig];
			await onSaveManifest(cloned, activeChunk.slug);
			toolMode = 'orbit';
		}
	}

	async function handleGenerateTerrain() {
		if (!activeChunk) return;
		busyOp = true;
		try {
			const rep = await api.chunksGenerateTerrain(activeChunk.slug, activeChunk.manifest.biome, 1.0);
			lastStitchReport = rep;
			await onProjectMutated(
				rep.project,
				`Đã kiến tạo địa hình 256m×256m & khâu biên 0.000m với ${rep.stitched_neighbors.length} ô lân cận.`
			);
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			busyOp = false;
		}
	}

	async function handleStitchNow() {
		if (!activeChunk) return;
		busyOp = true;
		try {
			const rep = await api.chunksStitchNeighbors(activeChunk.slug);
			lastStitchReport = rep;
			await onProjectMutated(
				rep.project,
				`Khâu biên hoàn tất: sai số tối đa = ${rep.max_seam_error_m.toFixed(4)}m (${rep.stitched_neighbors.join(', ') || 'độc lập'}).`
			);
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			busyOp = false;
		}
	}

	async function handlePackChunkZip() {
		if (!activeChunk) return;
		busyOp = true;
		try {
			const packed = await api.chunksPackZip(activeChunk.slug);
			await onProjectMutated(
				packed.project,
				`Đã đóng gói ${packed.zip_path} (${Math.round(packed.size_bytes / 1024)} KB · seam ${packed.max_seam_error_m.toFixed(3)}m).`
			);
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			busyOp = false;
		}
	}

	async function handleCaptureManga2K() {
		if (!activeChunk || !stageCtrl) return;
		busyOp = true;
		try {
			const cap = stageCtrl.captureMangaPlates2K();
			if (!cap) return;
			const res = await api.projectsSaveMangaPlates(
				activeChunk.slug,
				2560,
				1440,
				cap.beauty,
				cap.depth,
				`openworld_${activeChunk.manifest.chunk_x}_${activeChunk.manifest.chunk_z}`
			);
			await onProjectMutated(
				res.project,
				`Đã xuất Phông nền Đại Cảnh Manga 2K (Beauty + Depth) vào ${res.beauty_plate_path}`
			);
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			busyOp = false;
		}
	}

	async function handleUploadByoaFile(
		files: FileList | null,
		kind: 'splat' | 'concept' | 'audio' | 'glb',
		autoConvertToSplat = false
	) {
		if (!activeChunk || !files || files.length === 0) return;
		busyOp = true;
		try {
			const file = files[0];
			const b64 = await fileToBase64(file);
			const updated = await api.projectsUploadAssetBytes(activeChunk.slug, kind, file.name, b64, true);
			await onProjectMutated(updated, `Đã nhập '${file.name}' vào ô Chunk '${activeChunk.slug}'.`);
			if (autoConvertToSplat) {
				await onEnqueueGpuForProject(
					updated,
					'worldgen',
					{
						mode: 'image_to_splat',
						project_slug: updated.slug,
						max_splats: 140000,
						world_span: 110.0,
						relief_scale: 28.0
					},
					'Chuyển Ảnh Phong Cảnh BYOA sang 3D Gaussian Splat (.ply)'
				);
			}
		} catch (err) {
			onNotify(err instanceof Error ? err.message : String(err), true);
		} finally {
			busyOp = false;
		}
	}

	async function handleUpdateEnvironmentSliders(water: number, foliage: number) {
		if (!activeChunk) return;
		const cloned = JSON.parse(JSON.stringify(activeChunk.manifest)) as ProjectManifest;
		cloned.chunks.water_level = water;
		cloned.chunks.foliage_density = foliage;
		await onSaveManifest(cloned, activeChunk.slug);
	}

	async function removePlacement(id: string) {
		if (!activeChunk) return;
		const cloned = JSON.parse(JSON.stringify(activeChunk.manifest)) as ProjectManifest;
		cloned.chunks.placements = (cloned.chunks.placements ?? []).filter((p) => p.id !== id);
		await onSaveManifest(cloned, activeChunk.slug);
	}

	async function removeAudioZone(id: string) {
		if (!activeChunk) return;
		const cloned = JSON.parse(JSON.stringify(activeChunk.manifest)) as ProjectManifest;
		cloned.chunks.audio_zones = (cloned.chunks.audio_zones ?? []).filter((z) => z.id !== id);
		await onSaveManifest(cloned, activeChunk.slug);
	}

	function toggleZonePreview(zone: AmbientAudioZone) {
		if (!previewAudioEl) return;
		if (playingZoneId === zone.id) {
			previewAudioEl.pause();
			playingZoneId = null;
			return;
		}
		previewAudioEl.src = mediaUrl(zone.audio_path);
		previewAudioEl.volume = Math.max(0.05, Math.min(1, zone.volume));
		void previewAudioEl.play();
		playingZoneId = zone.id;
	}

	async function handleCreateNewChunk() {
		const slug = `chunk-${newChunkPlanet}-${newChunkX}-${newChunkZ}`.replace(/[^a-z0-9-]+/g, '-');
		await onCreateProject({
			slug,
			title: newChunkTitle.trim() || `Ô Địa Hình [${newChunkX}, ${newChunkZ}]`,
			title_en: `Open-World Chunk [${newChunkX}, ${newChunkZ}]`,
			kind: 'open_world',
			planet: newChunkPlanet,
			region_slug: newChunkBiome,
			era: 'Kỷ Nguyên Hiện Tại',
			era_year: null,
			lat: null,
			lng: null,
			biome: newChunkBiome,
			chunk_x: newChunkX,
			chunk_z: newChunkZ,
			cowriter_entity_id: null,
			cowriter_key: '',
			unlock_chapter: 1,
			description_vi: `Ô địa hình thế giới mở 256m×256m tọa độ [${newChunkX}, ${newChunkZ}].`,
			description_en: `Seamless 256m×256m open-world terrain chunk at [${newChunkX}, ${newChunkZ}].`,
			local_image_path: null,
			concept_paths: []
		});
		showCreateChunk = false;
	}
</script>

<audio bind:this={previewAudioEl} onended={() => (playingZoneId = null)}></audio>
<input
	bind:this={splatFileInput}
	type="file"
	accept=".ply,.spz,.splat"
	style="display:none"
	onchange={(e) => handleUploadByoaFile((e.currentTarget as HTMLInputElement).files, 'splat')}
/>
<input
	bind:this={landscapeImgInput}
	type="file"
	accept=".png,.jpg,.jpeg,.webp"
	style="display:none"
	onchange={(e) =>
		handleUploadByoaFile((e.currentTarget as HTMLInputElement).files, 'concept', true)}
/>
<input
	bind:this={ambientAudioInput}
	type="file"
	accept=".wav,.mp3,.ogg,.flac"
	style="display:none"
	onchange={(e) => handleUploadByoaFile((e.currentTarget as HTMLInputElement).files, 'audio')}
/>
<input
	bind:this={customGlbInput}
	type="file"
	accept=".glb,.gltf"
	style="display:none"
	onchange={(e) => handleUploadByoaFile((e.currentTarget as HTMLInputElement).files, 'glb')}
/>

<div class="chunk-workbench" data-testid="open-world-workbench">
	<!-- Left Column: Chunk Grid Navigator & Create -->
	<aside class="chunk-sidebar card">
		<div class="row-between">
			<div>
				<div class="section-label">CHẶNG 3 · OPEN WORLD</div>
				<h3 style="margin: 2px 0 0; font-size: 15px;">Lưới Ô Chunk 256m×256m</h3>
			</div>
			<button class="btn btn-sm btn-brass" onclick={() => (showCreateChunk = !showCreateChunk)}>
				+ Ô Mới
			</button>
		</div>

		{#if showCreateChunk}
			<div class="sub-box">
				<div class="grid-2">
					<label class="field-lbl">
						<span>Hành tinh</span>
						<select class="select" bind:value={newChunkPlanet}>
							<option value="akunalia">Akunalia</option>
							<option value="earth">Earth</option>
						</select>
					</label>
					<label class="field-lbl">
						<span>Quần xã (Biome)</span>
						<select class="select" bind:value={newChunkBiome}>
							<option value="zyberon-basin">Lòng chảo Zyberon</option>
							<option value="highland-cliff">Núi đá cao nguyên</option>
							<option value="temperate-meadow">Thảo nguyên</option>
							<option value="desert-sand">Sa mạc cổ</option>
							<option value="snow-peak">Đỉnh tuyết</option>
						</select>
					</label>
				</div>
				<div class="grid-2" style="margin-top:6px;">
					<label class="field-lbl">
						<span>Tọa độ X</span>
						<input class="input" type="number" bind:value={newChunkX} />
					</label>
					<label class="field-lbl">
						<span>Tọa độ Z</span>
						<input class="input" type="number" bind:value={newChunkZ} />
					</label>
				</div>
				<label class="field-lbl" style="margin-top:6px;">
					<span>Tên hiển thị</span>
					<input class="input" bind:value={newChunkTitle} />
				</label>
				<button class="btn btn-sm btn-brass" style="width:100%; margin-top:8px;" onclick={handleCreateNewChunk}>
					Tạo Ô Chunk [{newChunkX}, {newChunkZ}]
				</button>
			</div>
		{/if}

		<div class="chunk-list">
			{#if chunkProjects.length === 0}
				<div class="empty-hint">
					Chưa có ô <code>open_world</code> nào. Bấm <strong>+ Ô Mới</strong> để khởi tạo địa hình 256m×256m.
				</div>
			{:else}
				{#each chunkProjects as cp (cp.slug)}
					<button
						class="chunk-item {activeChunk?.slug === cp.slug ? 'active' : ''}"
						onclick={() => onSelectSlug(cp.slug)}
					>
						<div class="row-between">
							<span class="badge badge-cyan mono">
								[{cp.manifest.chunk_x}, {cp.manifest.chunk_z}]
							</span>
							<span class="mono" style="font-size:10.5px; color:var(--text-muted)">
								{cp.manifest.planet}
							</span>
						</div>
						<strong style="font-size:12.5px; margin-top:4px; display:block;">{cp.title}</strong>
						<small style="color:var(--text-muted)">
							{(cp.manifest.chunks.placements ?? []).length} kỳ quan ·
							{(cp.manifest.chunks.audio_zones ?? []).length} vùng nhạc
							{cp.manifest.chunks.splat_path ? ' · 3DGS' : ''}
						</small>
					</button>
				{/each}
			{/if}
		</div>

		{#if activeChunk}
			<div class="sub-box" style="margin-top:auto;">
				<div class="section-label">KHÂU BIÊN LIỀN MẠCH (EDGE-STITCH)</div>
				<div style="font-size:11.5px; margin: 4px 0 8px; color: var(--text-secondary);">
					Ô kề bên:
					<strong>{neighborChunks.map((n) => `[${n.manifest.chunk_x},${n.manifest.chunk_z}]`).join(', ') || 'Chưa có'}</strong>
					{#if lastStitchReport}
						<div class="badge badge-ok" style="margin-top:5px;">
							Seam Error: {lastStitchReport.max_seam_error_m.toFixed(4)}m
						</div>
					{/if}
				</div>
				<div style="display:flex; gap:6px; flex-wrap:wrap;">
					<button class="btn btn-sm" onclick={handleGenerateTerrain} disabled={busyOp}>
						⛰️ Tái tạo Heightmap
					</button>
					<button class="btn btn-sm btn-cyan" onclick={handleStitchNow} disabled={busyOp}>
						🪡 Khâu biên 0.000m
					</button>
				</div>
			</div>
		{/if}
	</aside>

	<!-- Center: Live Three.js + @sparkjsdev/spark 3D Open-World Stage -->
	<section class="chunk-stage card">
		{#if activeChunk}
			<div class="stage-toolbar">
				<div style="display:flex; gap:5px; flex-wrap:wrap; align-items:center;">
					<button
						class="btn btn-sm {toolMode === 'orbit' ? 'btn-brass' : ''}"
						onclick={() => (toolMode = 'orbit')}
					>
						🎥 Xoay / Bay
					</button>
					<button
						class="btn btn-sm {toolMode === 'sculpt' ? 'btn-brass' : ''}"
						onclick={() => (toolMode = 'sculpt')}
					>
						⛏️ Điêu khắc Đất
					</button>
					<button
						class="btn btn-sm {toolMode === 'place_glb' ? 'btn-brass' : ''}"
						onclick={() => (toolMode = 'place_glb')}
					>
						🏛️ Đặt Kỳ Quan .GLB
					</button>
					<button
						class="btn btn-sm {toolMode === 'audio_zone' ? 'btn-brass' : ''}"
						onclick={() => (toolMode = 'audio_zone')}
					>
						🎵 Đặt Vùng Nhạc
					</button>
					<button
						class="btn btn-sm {toolMode === 'spawn_point' ? 'btn-brass' : ''}"
						onclick={() => (toolMode = 'spawn_point')}
					>
						🧭 Spawn
					</button>
					<button
						class="btn btn-sm {toolMode === 'vn_trigger' ? 'btn-brass' : ''}"
						onclick={() => (toolMode = 'vn_trigger')}
					>
						📖 Điểm VN
					</button>
				</div>

				<div style="display:flex; gap:6px; align-items:center;">
					<label style="display:inline-flex; align-items:center; gap:5px; font-size:11.5px; cursor:pointer;">
						<input type="checkbox" bind:checked={showNeighbors} />
						<span>Hiện ô kề</span>
					</label>
					<button
						class="btn btn-sm {wavesEnabled ? 'btn-cyan' : ''}"
						data-testid="chunk-waves-toggle"
						onclick={() => (wavesEnabled = !wavesEnabled)}
						title="Sóng nước là hoạt ảnh liên tục. Tắt để sân khấu ngủ (0% GPU) khi đứng yên."
					>
						🌊 Sóng {wavesEnabled ? 'ON' : 'OFF'}
					</button>
					<button
						class="btn btn-sm {flyWasdActive ? 'btn-cyan' : ''}"
						onclick={() => (flyWasdActive = !flyWasdActive)}
						title="Bật điều khiển bay WASD + Shift + Q/E"
					>
						🕹️ WASD {flyWasdActive ? 'ON' : 'OFF'}
					</button>
					<button class="btn btn-sm" onclick={() => stageCtrl?.resetCamera()}>🎯 Reset</button>
					{#if stageMode.chunk3d}
						<button
							class="btn btn-sm"
							data-testid="deactivate-chunk-3d-btn"
							onclick={() => (stageMode.chunk3d = false)}
							title="Tháo sân khấu 3D, trả VRAM — về thẻ Chờ 2D"
						>
							⏹ Ngắt 3D
						</button>
					{/if}
				</div>
			</div>

			<div class="viewport-wrap">
				<div class="viewport-canvas" bind:this={viewportHost}></div>

				{#if !stageMode.chunk3d}
					{@const plate = activeChunk.manifest.manga_plates?.[0]?.beauty_path ?? activeChunk.manifest.local_image_path ?? null}
					<div class="chunk-2d-standby-card" data-testid="chunk-2d-standby-card">
						{#if plate}
							<img class="chunk-standby-img" src={mediaUrl(plate)} alt={activeChunk.title} />
						{/if}
						<div class="chunk-standby-panel">
							<span class="badge badge-cyan">CHỜ 2D · 3D ĐANG NGẮT (0 MB VRAM)</span>
							<strong>{activeChunk.title}</strong>
							<span class="mono" style="font-size:11.5px; color: var(--text-secondary);">
								Ô [{activeChunk.manifest.chunk_x}, {activeChunk.manifest.chunk_z}] ·
								{(activeChunk.manifest.chunks.placements ?? []).length} kỳ quan ·
								{(activeChunk.manifest.chunks.audio_zones ?? []).length} vùng nhạc
							</span>
							<button
								class="btn btn-brass"
								data-testid="activate-chunk-3d-btn"
								onclick={() => (stageMode.chunk3d = true)}
							>
								▶ Bật Sân Khấu 3D
							</button>
						</div>
					</div>
				{/if}

				<div class="hud-overlay-bottom">
					<span class="badge badge-ok">
						Triplanar PBR Poly Haven · 256m×256m ({activeChunk.manifest.chunks.grid_resolution ?? 65}×{activeChunk.manifest.chunks.grid_resolution ?? 65})
					</span>
					{#if activeChunk.manifest.chunks.splat_path}
						<span class="badge badge-cyan">
							✨ Spark 3DGS: {loadedSplatCount > 0 ? `${loadedSplatCount.toLocaleString()} splats` : 'Đang nạp .ply'}
						</span>
					{/if}
					{#if pointerCoords}
						<span class="mono" style="font-size:11px; color:#e9ecef;">
							Con trỏ: X={pointerCoords.x}m · Y={pointerCoords.y}m · Z={pointerCoords.z}m
						</span>
					{/if}
					{#if toolMode !== 'orbit'}
						<span class="badge badge-brass">
							Bấm chuột trái lên mặt đất để thực hiện: {toolMode}
						</span>
					{/if}
				</div>
			</div>

			<div class="stage-footer">
				<div style="display:flex; gap:6px; flex-wrap:wrap;">
					<button class="btn btn-sm" onclick={() => splatFileInput?.click()}>
						✨ Nhập .PLY / .SPZ
					</button>
					<button class="btn btn-sm btn-cyan" onclick={() => landscapeImgInput?.click()}>
						🖼️ Ảnh Phong Cảnh BYOA → 3D Splat (GPU)
					</button>
					<button class="btn btn-sm" onclick={handleCaptureManga2K} disabled={busyOp}>
						📸 Chụp Đại Cảnh Manga 2K (Beauty+Depth)
					</button>
				</div>
				<div style="display:flex; gap:6px;">
					<button class="btn btn-sm btn-brass" onclick={handlePackChunkZip} disabled={busyOp}>
						📦 Đóng gói chunk_{activeChunk.manifest.planet}_{activeChunk.manifest.chunk_x}_{activeChunk.manifest.chunk_z}.zip
					</button>
					<button class="btn btn-sm btn-cyan" onclick={() => onJumpToSync(activeChunk.slug)}>
						🚀 Đồng bộ Selorson
					</button>
				</div>
			</div>
		{:else}
			<div class="empty-stage">
				<h3>Phân xưởng Thế Giới Mở Song Song (Chunks 256m × 256m)</h3>
				<p>Tạo hoặc chọn một ô Chunk ở cột trái để điêu khắc địa hình, nạp Gaussian Splat và đặt kỳ quan .glb.</p>
			</div>
		{/if}
	</section>

	<!-- Right: Inspector for Terrain Brush, Monuments, Audio Zones & Triggers -->
	<aside class="chunk-inspector card">
		{#if activeChunk}
			<div class="section-label">ĐIỀU KHIỂN Ô [{activeChunk.manifest.chunk_x}, {activeChunk.manifest.chunk_z}]</div>
			<h3 style="margin: 2px 0 8px; font-size: 14.5px;">{activeChunk.title}</h3>

			<!-- Water & Foliage -->
			<div class="sub-box">
				<div class="section-label">MẶT NƯỚC &amp; THẢM CỎ INSTANCED</div>
				<label class="field-lbl" style="margin-top:5px;">
					<span>Mực nước gợn sóng: <strong>{(activeChunk.manifest.chunks.water_level ?? 1.8).toFixed(1)}m</strong></span>
					<input
						type="range"
						min="-2"
						max="12"
						step="0.2"
						value={activeChunk.manifest.chunks.water_level ?? 1.8}
						onchange={(e) =>
							handleUpdateEnvironmentSliders(
								Number((e.currentTarget as HTMLInputElement).value),
								activeChunk.manifest.chunks.foliage_density ?? 0.55
							)}
					/>
				</label>
				<label class="field-lbl" style="margin-top:5px;">
					<span>Mật độ cỏ tự nhiên: <strong>{Math.round((activeChunk.manifest.chunks.foliage_density ?? 0.55) * 100)}%</strong></span>
					<input
						type="range"
						min="0"
						max="1"
						step="0.05"
						value={activeChunk.manifest.chunks.foliage_density ?? 0.55}
						onchange={(e) =>
							handleUpdateEnvironmentSliders(
								activeChunk.manifest.chunks.water_level ?? 1.8,
								Number((e.currentTarget as HTMLInputElement).value)
							)}
					/>
				</label>
			</div>

			<!-- Active Tool Parameters -->
			{#if toolMode === 'sculpt'}
				<div class="sub-box highlight">
					<div class="section-label">CỌ ĐIÊU KHẮC ĐỊA HÌNH</div>
					<div class="grid-2" style="margin-top:5px;">
						<label class="field-lbl">
							<span>Chế độ cọ</span>
							<select class="select" bind:value={brushMode}>
								<option value="raise">Nâng đồi (Raise)</option>
								<option value="lower">Hạ thung lũng (Lower)</option>
								<option value="flatten">San phẳng bệ (Flatten)</option>
								<option value="smooth">Làm mượt (Smooth)</option>
							</select>
						</label>
						<label class="field-lbl">
							<span>Bán kính ({brushRadius}m)</span>
							<input class="input" type="number" min="5" max="90" bind:value={brushRadius} />
						</label>
					</div>
					<label class="field-lbl" style="margin-top:5px;">
						<span>Cường độ ({brushStrength}m)</span>
						<input type="range" min="0.5" max="12" step="0.5" bind:value={brushStrength} />
					</label>
				</div>
			{:else if toolMode === 'place_glb'}
				<div class="sub-box highlight">
					<div class="section-label">CHỌN KỲ QUAN .GLB ĐỂ ĐẶT</div>
					<select class="select" style="margin-top:5px;" bind:value={chosenMonumentSlug}>
						{#each glbCatalogProjects as gp (gp.slug)}
							<option value={gp.slug}>{gp.title} ({gp.slug})</option>
						{/each}
					</select>
					<div class="grid-2" style="margin-top:6px;">
						<label class="field-lbl">
							<span>Tỷ lệ (Scale)</span>
							<input class="input" type="number" step="0.1" min="0.1" max="10" bind:value={placeScale} />
						</label>
						<label class="field-lbl">
							<span>Góc xoay Y (°)</span>
							<input class="input" type="number" step="15" bind:value={placeRotDeg} />
						</label>
					</div>
					<button class="btn btn-sm" style="margin-top:6px; width:100%;" onclick={() => customGlbInput?.click()}>
						📂 Nhập .GLB ngoài vào dự án
					</button>
				</div>
			{:else if toolMode === 'audio_zone'}
				<div class="sub-box highlight">
					<div class="section-label">VÙNG NHẠC AMBIENT (FL STUDIO)</div>
					<label class="field-lbl" style="margin-top:5px;">
						<span>Nhãn vùng nhạc</span>
						<input class="input" bind:value={audioZoneLabel} />
					</label>
					<div class="grid-2" style="margin-top:5px;">
						<label class="field-lbl">
							<span>Bán kính (m)</span>
							<input class="input" type="number" bind:value={audioZoneRadius} />
						</label>
						<label class="field-lbl">
							<span>Âm lượng</span>
							<input class="input" type="number" step="0.05" min="0.1" max="1" bind:value={audioZoneVolume} />
						</label>
					</div>
					<button class="btn btn-sm" style="margin-top:6px; width:100%;" onclick={() => ambientAudioInput?.click()}>
						🎵 Nạp tệp .WAV / .MP3 / .FLAC
					</button>
				</div>
			{:else if toolMode === 'vn_trigger'}
				<div class="sub-box highlight">
					<div class="section-label">ĐIỂM TƯƠNG TÁC VISUAL NOVEL</div>
					<label class="field-lbl" style="margin-top:5px;">
						<span>Nhãn hiển thị [E]</span>
						<input class="input" bind:value={vnTriggerLabel} />
					</label>
					<label class="field-lbl" style="margin-top:5px;">
						<span>Tập kịch bản VN</span>
						<select class="select" bind:value={vnTriggerEpisodeSlug}>
							{#each vnCatalogProjects as vp (vp.slug)}
								<option value={vp.slug}>{vp.title} ({vp.slug})</option>
							{/each}
						</select>
					</label>
				</div>
			{/if}

			<!-- Placed Monuments List -->
			<div class="sub-box">
				<div class="row-between">
					<span class="section-label">KỲ QUAN ĐÃ ĐẶT ({(activeChunk.manifest.chunks.placements ?? []).length})</span>
				</div>
				{#if (activeChunk.manifest.chunks.placements ?? []).length === 0}
					<div class="empty-hint">Chưa đặt công trình .glb nào trên ô này.</div>
				{:else}
					{#each activeChunk.manifest.chunks.placements ?? [] as pl (pl.id)}
						<div class="mini-row">
							<div>
								<strong>{pl.title}</strong>
								<div class="mono" style="font-size:10.5px; color:var(--text-muted)">
									({pl.x}m, {pl.y}m, {pl.z}m) · rot {pl.rot_y_deg}° · ×{pl.scale}
								</div>
							</div>
							<button class="btn btn-sm btn-ghost" onclick={() => removePlacement(pl.id)}>✕</button>
						</div>
					{/each}
				{/if}
			</div>

			<!-- Ambient Audio Zones List -->
			<div class="sub-box">
				<div class="row-between">
					<span class="section-label">AMBIENT AUDIO ZONES ({(activeChunk.manifest.chunks.audio_zones ?? []).length})</span>
					<button class="btn btn-sm btn-ghost" onclick={() => ambientAudioInput?.click()}>+ Audio</button>
				</div>
				{#if (activeChunk.manifest.chunks.audio_zones ?? []).length === 0}
					<div class="empty-hint">Chưa gắn vùng nhạc môi trường.</div>
				{:else}
					{#each activeChunk.manifest.chunks.audio_zones ?? [] as az (az.id)}
						<div class="mini-row">
							<div>
								<strong>{az.label}</strong>
								<div class="mono" style="font-size:10.5px; color:var(--text-muted)">
									({az.x}m, {az.z}m) · R={az.radius}m · Vol {Math.round(az.volume * 100)}%
								</div>
							</div>
							<div style="display:flex; gap:4px;">
								<button class="btn btn-sm" onclick={() => toggleZonePreview(az)}>
									{playingZoneId === az.id ? '⏹' : '▶'}
								</button>
								<button class="btn btn-sm btn-ghost" onclick={() => removeAudioZone(az.id)}>✕</button>
							</div>
						</div>
					{/each}
				{/if}
			</div>

			<!-- Spawn & VN Triggers Summary -->
			<div class="sub-box">
				<div class="section-label">
					SPAWN ({(activeChunk.manifest.chunks.spawn_points ?? []).length}) &amp; VN TRIGGERS ({(activeChunk.manifest.chunks.vn_triggers ?? []).length})
				</div>
				{#each activeChunk.manifest.chunks.vn_triggers ?? [] as vt (vt.id)}
					<div class="mini-row">
						<div>
							<span class="badge badge-brass">VN</span> <strong>{vt.label}</strong>
							<div class="mono" style="font-size:10.5px; color:var(--text-muted)">
								→ {vt.episode_slug} ({vt.x}m, {vt.z}m)
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</aside>
</div>

<style>
	.chunk-workbench {
		display: grid;
		grid-template-columns: 265px 1fr 295px;
		gap: 10px;
		height: 100%;
		min-height: 0;
	}
	.chunk-sidebar,
	.chunk-inspector {
		display: flex;
		flex-direction: column;
		gap: 8px;
		overflow-y: auto;
		min-height: 0;
	}
	.chunk-stage {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
		padding: 10px;
	}
	.stage-toolbar,
	.stage-footer,
	.row-between {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		flex-wrap: wrap;
	}
	.chunk-2d-standby-card {
		position: absolute;
		inset: 0;
		z-index: 2;
		display: flex;
		align-items: flex-end;
		background: #090d16;
	}
	.chunk-standby-img {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.chunk-standby-panel {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 5px;
		margin: 12px;
		padding: 10px 12px;
		border-radius: var(--radius-sm);
		background: rgba(9, 13, 22, 0.82);
		border: 1px solid var(--brass-line);
	}
	.viewport-wrap {
		position: relative;
		flex: 1;
		min-height: 360px;
		border-radius: var(--radius-md);
		overflow: hidden;
		border: 1px solid var(--brass-line);
		background: #080f1a;
	}
	.viewport-canvas {
		width: 100%;
		height: 100%;
	}
	.hud-overlay-bottom {
		position: absolute;
		left: 10px;
		right: 10px;
		bottom: 10px;
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		padding: 6px 10px;
		border-radius: 8px;
		background: rgba(8, 12, 20, 0.82);
		border: 1px solid var(--brass-line);
		pointer-events: none;
	}
	.chunk-list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		overflow-y: auto;
	}
	.chunk-item {
		text-align: left;
		padding: 8px 10px;
		border-radius: var(--radius-md);
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.07);
		cursor: pointer;
	}
	.chunk-item.active {
		border-color: var(--brass-bright);
		background: rgba(212, 168, 83, 0.14);
	}
	.sub-box {
		padding: 9px;
		border-radius: var(--radius-md);
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid rgba(255, 255, 255, 0.07);
	}
	.sub-box.highlight {
		border-color: var(--brass-primary);
		background: rgba(212, 168, 83, 0.08);
	}
	.grid-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
	}
	.mini-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
		padding: 6px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.05);
		font-size: 12px;
	}
	.empty-hint {
		font-size: 11.5px;
		color: var(--text-muted);
		padding: 6px 0;
	}
	.empty-stage {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		color: var(--text-muted);
		text-align: center;
	}
</style>
