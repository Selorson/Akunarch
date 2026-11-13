import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';

const SERVER = fileURLToPath(new URL('../src/server.mjs', import.meta.url));
const EXPECTED = [
	'app_status',
	'project_list', 'project_get', 'project_patch', 'project_create', 'project_import_file',
	'gpu_enqueue', 'gpu_jobs', 'gpu_wait', 'gpu_cancel',
	'ui_open_project', 'ui_screenshot',
	'cowriter_entity', 'cowriter_search',
	'selorson_audit', 'selorson_push_draft'
];

test('server liệt kê đúng 16 tool và kiểm tham số bằng zod', async () => {
	const client = new Client({ name: 'test', version: '0' });
	await client.connect(new StdioClientTransport({ command: process.execPath, args: ['--disable-warning=ExperimentalWarning', SERVER] }));
	try {
		const { tools } = await client.listTools();
		assert.deepEqual(tools.map((t) => t.name).sort(), [...EXPECTED].sort());
		assert.match(tools.find((t) => t.name === 'selorson_push_draft').description, /anh đồng ý/);
		const r = await client.callTool({ name: 'project_patch', arguments: { patch: {} } });
		assert.equal(r.isError, true);
		assert.match(JSON.stringify(r.content), /slug/);
	} finally {
		await client.close();
	}
});
