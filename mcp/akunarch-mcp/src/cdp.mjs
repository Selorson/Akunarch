// Client CDP tối thiểu — tách từ app/ui/tests/vram-scenarios.mjs (lớp Cdp), bỏ phần đo VRAM.
import WebSocket from 'ws';

export class Cdp {
	constructor(url) {
		this.url = url;
		this.ws = null;
		this.seq = 0;
		this.pending = new Map();
	}

	async connect() {
		// Không gửi header Origin → WebView2 chấp nhận mà không cần --remote-allow-origins
		this.ws = new WebSocket(this.url);
		await new Promise((res, rej) => {
			this.ws.once('open', res);
			this.ws.once('error', rej);
		});
		this.ws.on('message', (data) => {
			const msg = JSON.parse(String(data));
			if (msg.id && this.pending.has(msg.id)) {
				const { resolve, reject } = this.pending.get(msg.id);
				this.pending.delete(msg.id);
				msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
			}
		});
		this.ws.on('close', () => {
			for (const { reject } of this.pending.values()) reject(new Error('CDP đã đóng kết nối'));
			this.pending.clear();
		});
		return this;
	}

	get open() {
		return this.ws?.readyState === WebSocket.OPEN;
	}

	send(method, params = {}, timeoutMs = 30000) {
		const id = ++this.seq;
		return new Promise((resolve, reject) => {
			const t = setTimeout(() => {
				this.pending.delete(id);
				reject(new Error(`CDP quá hạn: ${method}`));
			}, timeoutMs);
			this.pending.set(id, {
				resolve: (v) => (clearTimeout(t), resolve(v)),
				reject: (e) => (clearTimeout(t), reject(e))
			});
			this.ws.send(JSON.stringify({ id, method, params }));
		});
	}

	async eval(expression, timeoutMs = 30000) {
		const r = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }, timeoutMs);
		if (r.exceptionDetails) {
			const d = r.exceptionDetails;
			const msg = d.exception?.value ?? d.exception?.description ?? d.text ?? JSON.stringify(d);
			throw new Error(String(msg).slice(0, 2000));
		}
		return r.result?.value;
	}

	close() {
		try {
			this.ws?.close();
		} catch {
			// đã đóng
		}
	}
}
