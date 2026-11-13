/**
 * Kế hoạch VRAM v2 · Đợt B · B0 — chất lượng hiển thị của các sân khấu dùng renderer chung.
 */

export type StageQualityTier = 'hd' | 'ultra';

/** HD: đúng DPR màn hình (tối đa 1.0, nhẹ VRAM) · Ultra: luôn siêu lấy mẫu 1.5 (kể cả màn DPR 1.0). */
export function pbrPixelRatio(tier: StageQualityTier, devicePixelRatio: number): number {
	if (tier === 'ultra') return 1.5;
	return Math.min(devicePixelRatio || 1, 1);
}

type Vec3 = [number, number, number];
type Mat3 = [Vec3, Vec3, Vec3];

// Hàng của ma trận ACES trong shader three r178 (tonemapping_pars_fragment, mat3 GLSL theo cột)
const ACES_IN: Mat3 = [
	[0.59719, 0.35458, 0.04823],
	[0.076, 0.90834, 0.01566],
	[0.0284, 0.13383, 0.83777]
];
const ACES_OUT: Mat3 = [
	[1.60475, -0.53108, -0.07367],
	[-0.10208, 1.10813, -0.00605],
	[-0.00327, -0.07276, 1.07602]
];

const mul = (m: Mat3, v: Vec3): Vec3 => [
	m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
	m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
	m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2]
];

function invert(m: Mat3): Mat3 {
	const [[a, b, c], [d, e, f], [g, h, i]] = m;
	const A = e * i - f * h;
	const B = -(d * i - f * g);
	const C = d * h - e * g;
	const det = a * A + b * B + c * C;
	return [
		[A / det, -(b * i - c * h) / det, (b * f - c * e) / det],
		[B / det, (a * i - c * g) / det, -(a * f - c * d) / det],
		[C / det, -(a * h - b * g) / det, (a * e - b * d) / det]
	];
}
const ACES_IN_INV = invert(ACES_IN);
const ACES_OUT_INV = invert(ACES_OUT);

const rrt = (v: number) => (v * (v + 0.0245786) - 0.000090537) / (v * (0.983729 * v + 0.432951) + 0.238081);
/** Nghiệm dương của rrt(x) = y (y ∈ [0, 1)). */
function rrtInverse(y: number): number {
	const A = 0.983729 * y - 1;
	const B = 0.432951 * y - 0.0245786;
	const C = 0.238081 * y + 0.000090537;
	return (-B - Math.sqrt(B * B - 4 * A * C)) / (2 * A);
}
const sat = (x: number) => Math.min(1, Math.max(0, x));

/** ACESFilmicToneMapping của three r178 (đầu vào/ra tuyến tính, trước bước mã hóa sRGB). */
export function acesFilmic(rgb: Vec3 | number[], exposure: number): Vec3 {
	const k = exposure / 0.6;
	const u = mul(ACES_IN, [rgb[0] * k, rgb[1] * k, rgb[2] * k]);
	const o = mul(ACES_OUT, [rrt(u[0]), rrt(u[1]), rrt(u[2])]);
	return [sat(o[0]), sat(o[1]), sat(o[2])].map((x) => (Math.abs(x) < 1e-12 ? 0 : x)) as Vec3;
}

/**
 * Màu tuyến tính c' sao cho acesFilmic(c') ≈ rgb. Dùng cho màu nền khi cảnh vẽ qua composer + OutputPass:
 * vẽ thẳng ra canvas thì clear color KHÔNG bị tone-map, còn qua OutputPass thì có → bù ngược để giữ đúng màu cũ.
 */
export function inverseAcesFilmic(rgb: Vec3 | number[], exposure: number): Vec3 {
	const y = mul(ACES_OUT_INV, [
		Math.min(rgb[0], 0.999),
		Math.min(rgb[1], 0.999),
		Math.min(rgb[2], 0.999)
	]);
	const u: Vec3 = [rrtInverse(Math.max(0, y[0])), rrtInverse(Math.max(0, y[1])), rrtInverse(Math.max(0, y[2]))];
	const c = mul(ACES_IN_INV, u);
	const k = 0.6 / exposure;
	return [Math.max(0, c[0] * k), Math.max(0, c[1] * k), Math.max(0, c[2] * k)];
}
