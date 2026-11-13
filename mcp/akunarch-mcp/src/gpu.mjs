// Công cụ GPU — mọi job đi qua gpu_enqueue_job của app (GpuJobQueue một-model-một-lúc, Luật #5).
import { projectGet } from './projects.mjs';

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

export async function gpuEnqueue(s, slug, workerKind, payload = {}) {
	let projectId = null;
	const body = { ...payload };
	if (slug) {
		projectId = (await projectGet(s, slug)).id;
		body.project_slug = slug;
	}
	return s.invoke('gpu_enqueue_job', { input: { project_id: projectId, worker_kind: workerKind, payload: body } });
}

export function gpuJobs(s, limit = 20) {
	return s.invoke('gpu_list_jobs', { limit });
}

export function gpuCancel(s, jobId) {
	return s.invoke('gpu_cancel_job', { jobId });
}

/** Hỏi trạng thái tới khi job kết thúc hoặc quá hạn. Không bao giờ ném lỗi vì quá hạn. */
export async function pollUntilDone(
	fetchJob,
	{ intervalMs = 3000, timeoutMs = 1_800_000, sleep = (ms) => new Promise((r) => setTimeout(r, ms)), now = Date.now } = {}
) {
	const deadline = now() + timeoutMs;
	for (;;) {
		const job = await fetchJob();
		if (TERMINAL.has(job.status)) {
			return { status: job.status, output_path: job.output_path ?? '', error_log: job.error_log ?? '', vram_peak_mb: job.vram_peak_mb ?? 0 };
		}
		if (now() >= deadline) return { status: 'timeout', last_status: job.status, progress_pct: job.progress_pct ?? 0 };
		await sleep(intervalMs);
	}
}

export function gpuWait(s, jobId, timeoutSec = 1800) {
	return pollUntilDone(
		async () => {
			const job = (await gpuJobs(s, 200)).find((j) => j.id === jobId);
			if (!job) throw new Error(`Không thấy job #${jobId} trong 200 job gần nhất.`);
			return job;
		},
		{ timeoutMs: timeoutSec * 1000 }
	);
}
