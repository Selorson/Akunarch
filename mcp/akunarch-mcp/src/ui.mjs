// Điều hướng giao diện + chụp ảnh nghiệm thu (dùng đúng data-testid mà app/ui/tests/vram-scenarios.mjs đang dùng).
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { osWindowControl } from './app.mjs';

export const SHOT_DIR = 'E:\\Akunarch\\docs\\p0\\screenshots';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// Chuỗi JS nháy đơn: giữ nguyên dấu " của selector, thoát \ và ' (an toàn cả với selector tuỳ ý)
const q = (sel) => `document.querySelector('${String(sel).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')`;

export function screenshotPath(name, dir = SHOT_DIR) {
	const base = String(name).replace(/\.png$/i, '').replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_');
	return join(dir, `${base}.png`);
}

const PROBE = (slug) => `(() => { const __probeState = 1;
	const stage = ${q('[data-testid="real-pbr-stage"]')};
	const toggle = ${q('[data-testid="stage-variant-toggle"]')};
	return {
		cardFound: Boolean(${q(`[data-testid="project-card-${slug}"]`)}),
		standby: Boolean(${q('[data-testid="pbr-2d-standby-card"]')}),
		partsCount: Number(stage?.dataset.partsCount || 0),
		canvas: Boolean(stage?.querySelector('canvas')),
		variant: toggle ? (toggle.textContent.includes('cơ khí') ? 'mechanism' : 'real') : null,
		clips: window.__akunarchStage?.clips ?? []
	}; })()`;

/** Mở tab Dự án → chọn thẻ dự án; tuỳ chọn bật sân khấu 3D và chờ canvas.
 *  `variant: 'mechanism'` bấm công tắc sang bản cơ khí và chờ clip; `seekSec` dừng animation ở giây đó để chụp tất định. */
export async function uiOpenProject(s, slug, { stage3d = false, variant, seekSec, settleMs = 600, timeoutMs = 20000 } = {}) {
	await s.evaluate(`${q('[data-testid="nav-projects"]')}?.click(), true`);
	await sleep(settleMs);
	let st = await s.evaluate(PROBE(slug));
	if (!st?.cardFound) throw new Error(`Không thấy thẻ dự án '${slug}' trong tab Dự án.`);
	await s.evaluate(`${q(`[data-testid="project-card-${slug}"]`)}?.click(), true`);
	await sleep(settleMs);
	if (stage3d) {
		await s.evaluate(`${q('[data-testid="activate-3d-stage-btn"]')}?.click(), true`);
		const deadline = Date.now() + timeoutMs;
		do {
			await sleep(Math.max(settleMs, 300));
			st = await s.evaluate(PROBE(slug));
		} while (!st.canvas && Date.now() < deadline);
		if (!st.canvas) throw new Error(`Sân khấu 3D của '${slug}' chưa lên hình sau ${timeoutMs / 1000} s.`);
		if (variant && st.variant !== variant) {
			if (st.variant === null) throw new Error(`Dự án '${slug}' chưa có bản cơ khí (manifest thiếu mechanism_glb_path).`);
			await s.evaluate(`${q('[data-testid="stage-variant-toggle"]')}?.click(), true`);
			const deadline = Date.now() + timeoutMs;
			do {
				await sleep(Math.max(settleMs, 300));
				st = await s.evaluate(PROBE(slug));
			} while ((st.variant !== variant || !st.canvas || (variant === 'mechanism' && !st.clips?.length)) && Date.now() < deadline);
			if (st.variant !== variant) throw new Error(`Không chuyển được sân khấu sang '${variant}'.`);
		}
		if (seekSec != null) await s.evaluate(`(() => { const h = window.__akunarchStage; if (!h) return false; h.pause(); h.seek(${Number(seekSec)}); return true; })()`);
		await sleep(1500); // để texture / bóng đổ nạp xong trước khi chụp
	}
	return { standby: Boolean(st.standby), partsCount: st.partsCount ?? 0, canvas: Boolean(st.canvas), variant: st.variant ?? null, clips: st.clips ?? [] };
}

const WIN = 'window.__TAURI__.window.getCurrentWindow()';

/** Chụp cả cửa sổ hoặc riêng vùng `selector`; ghi PNG và trả buffer để xem ngay.
 *  Cửa sổ đang thu nhỏ thì WebView2 không vẽ nội dung GPU (ảnh WebGL ra đen) → tạm bung ra, chụp, thu nhỏ lại. */
export async function uiScreenshot(s, name, { selector, dir, settleMs = 1500, win = osWindowControl } = {}) {
	const wasMinimized = await s.evaluate(`${WIN}.isMinimized()`).catch(() => false);
	if (wasMinimized) {
		await win.restore();
		await sleep(settleMs);
	}
	try {
		return await captureTo(s, name, { selector, dir });
	} finally {
		if (wasMinimized) await win.minimize().catch(() => {});
	}
}

async function captureTo(s, name, { selector, dir }) {
	let clip;
	if (selector) {
		clip = await s.evaluate(`(() => { const e = ${q(selector)}; if (!e) return null;
			const b = e.getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; })()`);
		if (!clip || clip.width < 2) throw new Error(`Không thấy phần tử '${selector}' để chụp.`);
	}
	const buffer = await s.screenshot({ clip });
	const path = screenshotPath(name, dir);
	mkdirSync(dirname(path), { recursive: true });
	writeFileSync(path, buffer);
	return { path, bytes: buffer.length, buffer };
}
