/**
 * Kế hoạch VRAM v2 · B3 — giải mã sẵn (offline) mọi texture KTX2 Basis trong .glb sang KTX2 BC7 + zstd.
 *
 * Vì sao: transcoder Basis của three (Emscripten embind) cần `new Function` → bị CSP của Akunarch chặn
 * (script-src không có 'unsafe-eval'). KTX2 BC7 thì KTX2Loader nạp thẳng (createRawTexture), chỉ cần zstd wasm
 * ('wasm-unsafe-eval' đã có) → không phải nới CSP. Akunarch chỉ chạy Windows desktop (BPTC có sẵn trên WebGL2).
 *
 * Chạy: node ktx2_to_bc7.mjs <in.glb> <out.glb>
 * Kiểm: mọi texture phải là KTX2 vkFormat BC7; slot màu (baseColor/emissive) = BC7_SRGB, dữ liệu = BC7_UNORM.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';

const TOOLS = 'E:\\Akunarch\\bin\\tools';
const KTX = path.join(TOOLS, 'ktx-software', 'bin', 'ktx.exe');
const req = createRequire(path.join(TOOLS, 'gltf-transform', 'package.json'));
const { NodeIO } = req('@gltf-transform/core');
const { ALL_EXTENSIONS } = req('@gltf-transform/extensions');
const draco3d = req('draco3dgltf');

const VK_BC7_UNORM = 145;
const VK_BC7_SRGB = 146;

const [inPath, outPath] = process.argv.slice(2);
if (!inPath || !outPath) {
	console.error('Cách dùng: node ktx2_to_bc7.mjs <in.glb> <out.glb>');
	process.exit(2);
}

const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
	'draco3d.decoder': await draco3d.createDecoderModule(),
	'draco3d.encoder': await draco3d.createEncoderModule()
});

const doc = await io.read(inPath);
const root = doc.getRoot();
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'akun_bc7_'));

// Slot của từng texture (theo vật liệu) để kiểm không gian màu sau khi giải mã
const colorTex = new Set();
const dataTex = new Set();
for (const m of root.listMaterials()) {
	for (const t of [m.getBaseColorTexture(), m.getEmissiveTexture()]) if (t) colorTex.add(t);
	for (const t of [m.getNormalTexture(), m.getMetallicRoughnessTexture(), m.getOcclusionTexture()]) if (t) dataTex.add(t);
}

const report = [];
try {
	root.listTextures().forEach((tex, i) => {
		if (tex.getMimeType() !== 'image/ktx2') throw new Error(`Texture ${tex.getName()} chưa là KTX2 (${tex.getMimeType()})`);
		const src = path.join(tmp, `${i}_in.ktx2`);
		const dst = path.join(tmp, `${i}_bc7.ktx2`);
		fs.writeFileSync(src, tex.getImage());
		execFileSync(KTX, ['transcode', '--target', 'bc7', '--zstd', '18', src, dst], { stdio: 'pipe' });
		const out = fs.readFileSync(dst);
		const vk = out.readUInt32LE(12);
		const wantSrgb = colorTex.has(tex) && !dataTex.has(tex);
		const wantLinear = dataTex.has(tex) && !colorTex.has(tex);
		if (vk !== VK_BC7_UNORM && vk !== VK_BC7_SRGB) throw new Error(`${tex.getName()}: vkFormat ${vk} không phải BC7`);
		if (wantSrgb && vk !== VK_BC7_SRGB) throw new Error(`${tex.getName()}: slot màu nhưng không phải BC7_SRGB`);
		if (wantLinear && vk !== VK_BC7_UNORM) throw new Error(`${tex.getName()}: slot dữ liệu nhưng không phải BC7_UNORM`);
		tex.setImage(new Uint8Array(out));
		report.push({ name: tex.getName(), vk, bytes: out.length });
	});
	await io.write(outPath, doc);
} finally {
	fs.rmSync(tmp, { recursive: true, force: true });
}
console.log(JSON.stringify({ ok: true, textures: report.length, srgb: report.filter((r) => r.vk === VK_BC7_SRGB).length }));
