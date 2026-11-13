// Đồng bộ sang Selorson — Luật #6: luôn Nháp (is_active = false). Agent phải hỏi tác giả trước mỗi lần đẩy.

/** Tham số đẩy: forceDraft luôn true, baseUrl luôn theo cấu hình đã lưu trong app — bỏ qua mọi giá trị truyền vào. */
export function buildPushArgs(slug, _opts) {
	return { slug, forceDraft: true, baseUrl: null };
}

export function selorsonAudit(s, slug) {
	return s.invoke('sync_audit_project', { slug, forceDraft: true });
}

export function selorsonPushDraft(s, slug) {
	return s.invoke('sync_push_project', buildPushArgs(slug), 300000);
}
