/**
 * Kế hoạch VRAM v2 · Đợt C · C2 — chế độ Chờ 2D (Q2: bật mặc định).
 *
 * Trạng thái 3D người dùng chọn được giữ suốt phiên (đổi dự án / đổi tab không phải bấm lại).
 * Mặc định 2D → cold boot không tạo context WebGL nào. Bấm 🧹 hoặc hàng đợi sắp chạy job GPU nặng
 * (`RELEASE_WEBGL_VRAM_EVENT`) → mọi sân khấu về 2D để nhường VRAM.
 */
import { RELEASE_WEBGL_VRAM_EVENT } from './webgl-stage';

export const stageMode = $state({ pbr3d: false, chunk3d: false });

if (typeof window !== 'undefined') {
	window.addEventListener(RELEASE_WEBGL_VRAM_EVENT, () => {
		stageMode.pbr3d = false;
		stageMode.chunk3d = false;
	});
}
