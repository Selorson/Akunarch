/** P0: sân khấu PBR hiển thị bản thật hoặc bản cơ khí (sa bàn đồng hồ có animation). */
export type StageVariant = 'real' | 'mechanism';

interface ClockworkGlbs {
	glb_path?: string | null;
	mechanism_glb_path?: string | null;
}

/** Đường dẫn .glb cho biến thể; null nếu biến thể đó chưa có file. */
export function pickStageGlb(cw: ClockworkGlbs | null | undefined, variant: StageVariant): string | null {
	const raw = variant === 'mechanism' ? cw?.mechanism_glb_path : cw?.glb_path;
	const p = raw?.trim();
	return p ? p : null;
}

/** Clip của bản cơ khí: `assemble` phát 1 lần, sau đó lặp `idle`. */
export function pickClockworkClips(names: string[]): { intro: string | null; loop: string | null } {
	return {
		intro: names.includes('assemble') ? 'assemble' : null,
		loop: names.includes('idle') ? 'idle' : null
	};
}
