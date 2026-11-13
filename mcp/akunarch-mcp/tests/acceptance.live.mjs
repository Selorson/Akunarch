// Nghiệm thu Đợt 0 qua giao thức MCP thật (stdio). Chạy: node tests/acceptance.live.mjs
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';

const SERVER = fileURLToPath(new URL('../src/server.mjs', import.meta.url));
const client = new Client({ name: 'acceptance-dot0', version: '0' });
await client.connect(new StdioClientTransport({ command: process.execPath, args: ['--disable-warning=ExperimentalWarning', SERVER] }));

const results = [];
async function step(label, name, args, check) {
	const t0 = Date.now();
	const r = await client.callTool({ name, arguments: args }, undefined, { timeout: 600000 });
	const txt = r.content.find((c) => c.type === 'text')?.text ?? '';
	const ok = !r.isError && check(txt, r);
	results.push({ label, tool: name, ok, ms: Date.now() - t0, note: txt.slice(0, 160).replace(/\s+/g, ' ') });
	return txt;
}

try {
	await step('1. project_get Eryndor (tự mở app nếu cần)', 'project_get', { slug: 'eryndor-clocktower-concept' }, (t) => JSON.parse(t).slug === 'eryndor-clocktower-concept');
	await step('2. app_status', 'app_status', {}, (t) => JSON.parse(t).running && JSON.parse(t).cdp);
	const job = JSON.parse(await step('3a. gpu_enqueue probe', 'gpu_enqueue', { worker_kind: 'blender', payload: { mode: 'probe', simulate_ms: 500 } }, (t) => JSON.parse(t).status === 'queued' || JSON.parse(t).id > 0));
	await step('3b. gpu_wait', 'gpu_wait', { job_id: job.id, timeout_sec: 120 }, (t) => JSON.parse(t).status === 'completed');
	await step('4a. ui_open_project', 'ui_open_project', { slug: 'eryndor-clocktower-concept' }, (t) => 'standby' in JSON.parse(t));
	await step('4b. ui_screenshot', 'ui_screenshot', { name: 'D0_acceptance' }, (t, r) => r.content.some((c) => c.type === 'image' && c.data.length > 50000));
} finally {
	await client.close();
}
console.table(results);
process.exitCode = results.every((r) => r.ok) ? 0 : 1;
