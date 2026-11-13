/**
 * Kế hoạch VRAM v2 · Đợt B · B3 — một KTX2Loader cho cả app, gắn với renderer dùng chung (webgl-stage).
 * Texture KTX2/Basis trong .glb được giải mã sang BC7/BC1 trên GPU (giảm 4–8× VRAM so với JPEG → RGBA8).
 * Transcoder chạy offline từ static/basis (CSP: 'wasm-unsafe-eval', worker-src 'self' blob:).
 * Không dispose: worker pool sống cùng renderer chung, giống context WebGL.
 */
import type { WebGLRenderer } from 'three';
import type { KTX2Loader } from 'three/examples/jsm/loaders/KTX2Loader.js';

let loaderPromise: Promise<KTX2Loader> | null = null;

export function getSharedKtx2Loader(renderer: WebGLRenderer): Promise<KTX2Loader> {
	if (!loaderPromise) {
		loaderPromise = (async () => {
			const { KTX2Loader } = await import('three/examples/jsm/loaders/KTX2Loader.js');
			const loader = new KTX2Loader();
			loader.setTranscoderPath('/basis/');
			loader.setWorkerLimit(2);
			loader.detectSupport(renderer);
			return loader;
		})();
		loaderPromise.catch(() => {
			loaderPromise = null;
		});
	}
	return loaderPromise;
}
