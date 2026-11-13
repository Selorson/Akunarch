/**
 * Vòng render theo nhu cầu (Kế hoạch VRAM v2 · Đợt A · A3).
 *
 * Không có lý do chạy liên tục và hết khung chờ → không còn requestAnimationFrame nào (0 FPS, GPU về nghỉ).
 * - `invalidate(n)`: xin vẽ thêm n khung (thao tác chuột, slider, tài nguyên vừa nạp xong…).
 * - `setContinuous(lý do, bật/tắt)`: giữ vòng chạy khi có hoạt ảnh thật (autoRotate, WASD, sóng nước, splat đang sắp xếp).
 * - `step(dt)` trả về `true` nếu cần thêm khung (vd. `OrbitControls.update()` còn quán tính damping).
 */
export interface OnDemandLoop {
	invalidate(frames?: number): void;
	setContinuous(reason: string, on: boolean): void;
	dispose(): void;
	readonly running: boolean;
}

export interface LoopScheduler {
	request: (cb: (t: number) => void) => number;
	cancel: (id: number) => void;
	now: () => number;
}

// Tạm ngưng toàn cục khi cửa sổ bị thu nhỏ: WebView2 trong Tauri KHÔNG báo document.hidden lúc thu nhỏ
// và rAF vẫn chạy 60 lần/giây (đã đo thực tế) → các vòng liên tục (autoRotate, sóng, WASD) phải tự dừng.
let suspended = false;
const resumeHooks = new Set<() => void>();

export function setAllLoopsSuspended(on: boolean) {
	if (suspended === on) return;
	suspended = on;
	if (!on) for (const resume of [...resumeHooks]) resume();
}

const browserScheduler: LoopScheduler = {
	request: (cb) => requestAnimationFrame(cb),
	cancel: (id) => cancelAnimationFrame(id),
	now: () => performance.now()
};

export function createOnDemandLoop(
	step: (dt: number) => boolean | void,
	scheduler: LoopScheduler = browserScheduler
): OnDemandLoop {
	let rafId = 0;
	let pending = 0;
	let lastTime = 0;
	let disposed = false;
	const reasons = new Set<string>();

	const schedule = () => {
		if (disposed || rafId || suspended) return;
		lastTime = lastTime || scheduler.now();
		rafId = scheduler.request(frame);
	};

	const resume = () => {
		lastTime = 0;
		pending = Math.max(pending, 1);
		schedule();
	};
	resumeHooks.add(resume);

	function frame(t: number) {
		rafId = 0;
		if (disposed || suspended) return;
		const dt = Math.min(0.05, Math.max(0, (t - lastTime) / 1000));
		lastTime = t;
		const wantsMore = step(dt) === true;
		pending = Math.max(0, pending - 1);
		if (wantsMore) pending = Math.max(pending, 1);
		if (reasons.size > 0 || pending > 0) schedule();
		else lastTime = 0;
	}

	return {
		invalidate(frames = 2) {
			pending = Math.max(pending, frames);
			schedule();
		},
		setContinuous(reason, on) {
			if (on) reasons.add(reason);
			else reasons.delete(reason);
			if (on) schedule();
		},
		dispose() {
			disposed = true;
			resumeHooks.delete(resume);
			reasons.clear();
			pending = 0;
			if (rafId) scheduler.cancel(rafId);
			rafId = 0;
		},
		get running() {
			return rafId !== 0;
		}
	};
}
