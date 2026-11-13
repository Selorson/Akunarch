/**
 * Một WebGLRenderer + một <canvas> dùng chung cho CẢ app Akunarch (Kế hoạch VRAM v2 · Đợt A · A2).
 *
 * Vì sao: mỗi lần khởi tạo một WebGLRenderer là một context WebGL2 mới; `renderer.dispose()` không trả context
 * (chỉ GC mới trả), còn `forceContextLoss()` thì bị Chromium/WebView2 tính "lỗi" và khóa WebGL theo origin.
 * Chromium chỉ giữ ~16 context sống — tạo/hủy renderer mỗi lần đổi dự án sẽ chạm giới hạn đó.
 * Giải pháp: context được tạo đúng 1 lần, các sân khấu chỉ "mượn" canvas rồi trả lại.
 *
 * Quy ước cho sân khấu mượn renderer:
 * - Gỡ MỌI event listener tự gắn lên canvas khi trả (canvas sống suốt đời app).
 * - Dọn tài nguyên (`disposeObject3DDeep`, `disposeComposer`…) TRƯỚC khi gọi `release()`.
 * - Không bao giờ gọi `renderer.dispose()` / `forceContextLoss()`.
 */
import type { ColorSpace, ShadowMapType, ToneMapping, WebGLRenderer } from 'three';

export interface StageOptions {
	toneMapping: ToneMapping;
	toneMappingExposure: number;
	outputColorSpace?: ColorSpace;
	shadowMapEnabled?: boolean;
	shadowMapType?: ShadowMapType;
	pixelRatio: number;
	width: number;
	height: number;
}

export interface StageLease {
	readonly renderer: WebGLRenderer;
	readonly canvas: HTMLCanvasElement;
	/** Còn giữ quyền dùng canvas hay đã bị sân khấu khác lấy mất. */
	readonly active: boolean;
	/** Trả canvas về kho ẩn, thu swapchain về 1×1. Gọi nhiều lần vô hại. */
	release(): void;
}

interface Owner {
	id: number;
	onEvict: () => void;
}

const WEBGL_PREF_STORAGE_KEY = 'akunarch_webgl_pref';

let rendererPromise: Promise<WebGLRenderer> | null = null;
let sharedRenderer: WebGLRenderer | null = null;
let current: Owner | null = null;
let nextOwnerId = 1;
let holder: HTMLDivElement | null = null;
const stats = { contextsCreated: 0, contextLost: 0, contextRestored: 0, acquires: 0, releases: 0 };

function getHolder(): HTMLDivElement {
	if (!holder) {
		holder = document.createElement('div');
		holder.setAttribute('aria-hidden', 'true');
		holder.style.cssText = 'position:fixed;width:0;height:0;overflow:hidden;visibility:hidden;pointer-events:none;';
		document.body.appendChild(holder);
	}
	return holder;
}

function readStoredPowerPreference(): WebGLPowerPreference {
	try {
		const v = window.sessionStorage?.getItem(WEBGL_PREF_STORAGE_KEY);
		if (v === 'default' || v === 'high-performance') return v;
	} catch {
		// sessionStorage có thể bị chặn
	}
	return 'high-performance';
}

function acquireContext(canvas: HTMLCanvasElement): { gl: WebGL2RenderingContext; pref: WebGLPowerPreference } {
	const base: WebGLContextAttributes = {
		alpha: false,
		antialias: false, // khử răng cưa bằng render target MSAA của từng sân khấu, không phải swapchain
		depth: true,
		stencil: true,
		premultipliedAlpha: true,
		preserveDrawingBuffer: false
	};
	const first = readStoredPowerPreference();
	const order: WebGLPowerPreference[] = first === 'high-performance' ? ['high-performance', 'default'] : ['default'];
	for (const pref of order) {
		const gl = canvas.getContext('webgl2', { ...base, powerPreference: pref }) as WebGL2RenderingContext | null;
		if (gl) {
			try {
				window.sessionStorage?.setItem(WEBGL_PREF_STORAGE_KEY, pref);
			} catch {
				// bỏ qua
			}
			return { gl, pref };
		}
	}
	throw new Error('WebGL2 không khả dụng trên WebView2 này.');
}

async function getRenderer(): Promise<WebGLRenderer> {
	if (!rendererPromise) {
		rendererPromise = (async () => {
			const THREE = await import('three');
			const canvas = document.createElement('canvas');
			canvas.style.display = 'block';
			canvas.addEventListener('webglcontextlost', () => {
				stats.contextLost++;
				console.warn('[webgl-stage] Mất context WebGL2 — chờ khôi phục.');
			});
			canvas.addEventListener('webglcontextrestored', () => {
				stats.contextRestored++;
				console.info('[webgl-stage] Context WebGL2 đã khôi phục.');
			});
			const { gl, pref } = acquireContext(canvas);
			const renderer = new THREE.WebGLRenderer({
				canvas,
				context: gl,
				antialias: false,
				alpha: false,
				powerPreference: pref,
				preserveDrawingBuffer: false
			});
			stats.contextsCreated++;
			sharedRenderer = renderer;
			getHolder().appendChild(canvas);
			return renderer;
		})();
		rendererPromise.catch(() => {
			rendererPromise = null;
		});
	}
	return rendererPromise;
}

/**
 * Mượn renderer dùng chung cho `host`. Nếu sân khấu khác đang giữ, nó bị gọi `onEvict()`
 * (phải tự dọn tài nguyên rồi `release()`) trước khi canvas chuyển sang `host`.
 */
export async function acquireStage(
	host: HTMLElement,
	opts: StageOptions,
	onEvict: () => void
): Promise<StageLease> {
	const renderer = await getRenderer();
	if (current) {
		const prev = current;
		current = null;
		try {
			prev.onEvict();
		} catch (err) {
			console.error('[webgl-stage] Lỗi khi sân khấu cũ trả renderer:', err);
		}
	}
	const owner: Owner = { id: nextOwnerId++, onEvict };
	current = owner;
	stats.acquires++;

	const canvas = renderer.domElement;
	renderer.setRenderTarget(null);
	renderer.toneMapping = opts.toneMapping;
	renderer.toneMappingExposure = opts.toneMappingExposure;
	if (opts.outputColorSpace) renderer.outputColorSpace = opts.outputColorSpace;
	renderer.shadowMap.enabled = Boolean(opts.shadowMapEnabled);
	if (opts.shadowMapType !== undefined) renderer.shadowMap.type = opts.shadowMapType;
	renderer.shadowMap.needsUpdate = true;
	renderer.setPixelRatio(opts.pixelRatio);
	renderer.setSize(opts.width, opts.height);
	host.appendChild(canvas);

	let released = false;
	return {
		renderer,
		canvas,
		get active() {
			return !released && current === owner;
		},
		release() {
			if (released) return;
			released = true;
			stats.releases++;
			if (current !== owner) return; // đã bị sân khấu khác lấy canvas — không đụng vào
			current = null;
			renderer.setAnimationLoop(null);
			renderer.setRenderTarget(null);
			renderer.renderLists.dispose();
			renderer.setPixelRatio(1);
			renderer.setSize(1, 1, false);
			getHolder().appendChild(canvas);
		}
	};
}

/** Số liệu chẩn đoán (CDP / walkthrough): context đã tạo, mất, và tài nguyên GPU đang sống. */
export function getStageStats() {
	const r = sharedRenderer;
	return {
		...stats,
		owned: current !== null,
		memory: r
			? { geometries: r.info.memory.geometries, textures: r.info.memory.textures, programs: r.info.programs?.length ?? 0 }
			: null
	};
}

if (typeof window !== 'undefined') {
	(window as unknown as { __akunarchWebglStage?: () => ReturnType<typeof getStageStats> }).__akunarchWebglStage = getStageStats;
}

/**
 * Kế hoạch VRAM v2 · B2 — yêu cầu mọi sân khấu 3D đang mở tháo renderer (về thẻ 2D) để nhường VRAM:
 * phát khi bấm 🧹 và khi hàng đợi GPU sắp chạy job nặng (`akunarch://gpu-job-starting`).
 */
export const RELEASE_WEBGL_VRAM_EVENT = 'akunarch:release-webgl-vram';

export function requestWebglVramRelease(reason: 'manual' | 'gpu-job'): void {
	window.dispatchEvent(new CustomEvent(RELEASE_WEBGL_VRAM_EVENT, { detail: { reason } }));
}
