import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const UI_ROOT = path.resolve(HERE, '..');
const TAURI_ROOT = path.resolve(UI_ROOT, '..', 'src-tauri');

function walkFiles(dir, exts) {
	const out = [];
	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory()) {
			out.push(...walkFiles(full, exts));
		} else if (exts.some((ext) => entry.name.endsWith(ext))) {
			out.push(full);
		}
	}
	return out;
}

test('Rule #1: UI uses 100% Svelte 5 Runes, 0 Svelte 4 stores, and 0 React imports', () => {
	const srcDir = path.join(UI_ROOT, 'src');
	const files = walkFiles(srcDir, ['.svelte', '.ts', '.js']);
	assert.ok(files.length >= 7, 'Expected UI source files');

	for (const file of files) {
		const code = fs.readFileSync(file, 'utf8');
		assert.ok(
			!code.includes('svelte/store'),
			`Forbidden Svelte 4 svelte/store import in ${file}`
		);
		assert.ok(!/from\s+['"]react['"]/.test(code), `Forbidden React import in ${file}`);
		assert.ok(!code.includes('<slot'), `Deprecated Svelte 4 <slot> in ${file}`);
	}

	const pkg = JSON.parse(fs.readFileSync(path.join(UI_ROOT, 'package.json'), 'utf8'));
	assert.ok(pkg.dependencies['three'], 'three must be installed');
	assert.ok(pkg.dependencies['@sparkjsdev/spark'], '@sparkjsdev/spark must be installed');
	assert.ok(pkg.dependencies['3d-tiles-renderer'], '3d-tiles-renderer must be installed');
	assert.equal(pkg.dependencies['react'], undefined, 'react must NOT be installed');
});

test('Rule #2: Co-Writer bridge enforces SQLITE_OPEN_READ_ONLY and query_only = ON', () => {
	const bridgeRust = fs.readFileSync(
		path.join(TAURI_ROOT, 'src', 'cowriter_bridge.rs'),
		'utf8'
	);
	assert.ok(bridgeRust.includes('SQLITE_OPEN_READ_ONLY'));
	assert.ok(bridgeRust.includes('?mode=ro'));
	assert.ok(bridgeRust.includes('PRAGMA query_only = ON'));
	assert.ok(!bridgeRust.includes('SQLITE_OPEN_READ_WRITE'));
	assert.ok(!bridgeRust.includes('SQLITE_OPEN_CREATE'));
});

test('Rule #3: Zero-OOM Cargo.toml isolates heavy wgpu/ort/craft crates as external sidecars', () => {
	const cargoToml = fs.readFileSync(path.join(TAURI_ROOT, 'Cargo.toml'), 'utf8');
	for (const forbidden of ['wgpu', 'egui', 'ort =', 'materialcraft', 'effectcraft', 'filmcraft']) {
		assert.ok(
			!cargoToml.includes(forbidden),
			`Heavy crate '${forbidden}' must not be embedded in src-tauri/Cargo.toml`
		);
	}
	assert.ok(cargoToml.includes('custom-protocol = ["tauri/custom-protocol"]'));
});

test('CSP preserves WebGL2 blob/worker/wasm-unsafe-eval and akunmedia custom protocol', () => {
	const conf = JSON.parse(
		fs.readFileSync(path.join(TAURI_ROOT, 'tauri.conf.json'), 'utf8')
	);
	const csp = conf.app.security.csp;
	assert.ok(csp.includes('blob: data:'), 'connect-src must allow blob: data:');
	assert.ok(csp.includes("worker-src 'self' blob:"), 'worker-src must allow blob:');
	assert.ok(csp.includes("'wasm-unsafe-eval'"), 'script-src must allow wasm-unsafe-eval');
	assert.ok(csp.includes('http://akunmedia.localhost'), 'CSP must allow akunmedia.localhost');
});

test('All Tauri IPC commands are async so SQLite/FS/ZIP/nvidia-smi never block WebView2 UI thread', () => {
	const libRust = fs.readFileSync(path.join(TAURI_ROOT, 'src', 'lib.rs'), 'utf8');
	const syncCmdMatches = [...libRust.matchAll(/#\[tauri::command\]\s*\r?\n\s*fn\s+(\w+)/g)];
	assert.equal(
		syncCmdMatches.length,
		0,
		`Found synchronous #[tauri::command] fn(s) blocking main UI thread: ${syncCmdMatches.map((m) => m[1]).join(', ')}`
	);
});

test('akunmedia protocol isolates akunarch_data_dir (akunarch.db) and enforces strict media extension + Studio CORS', () => {
	const mediaRust = fs.readFileSync(path.join(TAURI_ROOT, 'src', 'media_protocol.rs'), 'utf8');
	assert.ok(
		!mediaRust.includes('akunarch_data_dir'),
		'media_protocol.rs must never expose akunarch_data_dir() where akunarch.db/JWTs live'
	);
	assert.ok(mediaRust.includes('ALLOWED_MEDIA_EXTS'), 'media extension allowlist required');
	assert.ok(mediaRust.includes('PARTIAL_CONTENT'), 'HTTP 206 Range streaming required');
	assert.ok(
		!mediaRust.includes('("Access-Control-Allow-Origin", "*")'),
		'Wildcard CORS on akunmedia:// is forbidden'
	);
});

test('v2.0 Law #1 & #4: AstrolabeStageViewport is permanently deleted, Zero Toy Primitives in UI, and offline Draco decoders exist', () => {
	assert.equal(
		fs.existsSync(path.join(UI_ROOT, 'src', 'lib', 'components', 'AstrolabeStageViewport.svelte')),
		false,
		'AstrolabeStageViewport.svelte must be permanently deleted'
	);
	assert.equal(
		fs.existsSync(path.join(UI_ROOT, 'src', 'lib', 'components', 'RealPbrStageViewport.svelte')),
		true,
		'RealPbrStageViewport.svelte must exist'
	);

	const srcFiles = walkFiles(path.join(UI_ROOT, 'src'), ['.svelte', '.ts', '.js']);
	const forbiddenPrimitives = [
		'CylinderGeometry',
		'BoxGeometry',
		'OctahedronGeometry',
		'TorusGeometry',
		'ConeGeometry'
	];
	for (const file of srcFiles) {
		const code = fs.readFileSync(file, 'utf8');
		for (const prim of forbiddenPrimitives) {
			assert.ok(!code.includes(prim), `Forbidden toy primitive '${prim}' found in ${file}`);
		}
	}

	for (const dracoFile of ['draco_decoder.js', 'draco_decoder.wasm', 'draco_wasm_wrapper.js']) {
		const dp = path.join(UI_ROOT, 'static', 'draco', dracoFile);
		assert.ok(
			fs.existsSync(dp) && fs.statSync(dp).size > 10_000,
			`Offline Draco file missing: ${dp}`
		);
	}
});

test('v2.0 Law #2 & #5: materialcraft-cli.exe sidecar and 3+ live AAA .glb monuments exist on disk', () => {
	const sidecar = 'E:\\Akunarch\\bin\\materialcraft-cli.exe';
	assert.ok(fs.existsSync(sidecar), `Sidecar missing at ${sidecar}`);

	for (const slug of [
		'temple-of-zyberon',
		'singularity-stonehenge-avalon',
		'singularity-samos-olympus'
	]) {
		const glb = path.join('E:\\Akunarch\\projects', slug, 'clockwork', `${slug}.glb`);
		const manifest = path.join('E:\\Akunarch\\projects', slug, 'project.akun.json');
		assert.ok(
			fs.existsSync(glb) && fs.statSync(glb).size > 500_000,
			`Real AAA .glb missing for ${slug}: ${glb}`
		);
		assert.ok(fs.existsSync(manifest), `Manifest missing for ${slug}: ${manifest}`);
	}
});
