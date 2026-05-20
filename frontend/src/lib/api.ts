// Base URL prefix for all API calls. Empty string = same-origin (works
// with the Vite dev proxy AND reverse-proxy production deploys). For
// cross-origin deploys like Railway separate services, set
// VITE_API_BASE_URL at build time, e.g. https://api.personalize.lakeb2b.com.
const API_BASE: string = (
  (import.meta as any).env?.VITE_API_BASE_URL ?? ""
).replace(/\/$/, "");

const TOKEN_KEY = "champ-personalize:token";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch {}
}

type Body = unknown;

async function request<T>(path: string, init: RequestInit & { brand?: string; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (init.brand) headers["X-Brand"] = init.brand;
  if (init.auth !== false) {
    const t = getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    let detail: unknown;
    try { detail = await res.json(); } catch { detail = await res.text(); }
    const message = typeof detail === "object" && detail && "detail" in (detail as object)
      ? String((detail as Record<string, unknown>).detail)
      : `HTTP ${res.status}`;
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export interface BrandTokens {
  brand_accent: string;
  brand_accent_soft: string;
  brand_ink: string;
  brand_muted: string;
  brand_rule: string;
  brand_bg: string;
  font_primary: string;
  font_secondary: string;
  font_google_url?: string | null;
}

export interface BrandConfig {
  slug: string;
  name: string;
  tagline: string;
  logo_url?: string | null;
  tokens: BrandTokens;
  sender_default: { name?: string | null; company: string; offer: string };
  system_prompt_addendum: string;
  default_model: string;
  voice_keywords: string[];
}

export interface Brief {
  name: string;
  title: string;
  company: string;
  industry: string;
  company_signals: string[];
  individual_signals: string[];
  industry_trends: string[];
  role_pain_points: string[];
  strongest_trigger: string;
  likely_pain_point: string;
}

export interface ScoreBlock {
  score: number;
  factors: Record<string, string>;
}

export interface EmailScores {
  deliverability: ScoreBlock;
  reply_likelihood: ScoreBlock;
}

export interface EmailDraft {
  subject: string;
  body: string;
  word_count: number;
  anchor_signal: string;
  warnings: string[];
  scores?: EmailScores | null;
}

export interface Variation {
  slot: string;
  label: string;
  model: string;
  email: EmailDraft;
  followup?: EmailDraft | null;
}

export interface PersonalizeResponse {
  brand: string;
  brief: Brief;
  variations: Variation[];
  /** kept for back-compat — usually `{ 5: <A-slot email> }` */
  emails: Record<string, EmailDraft>;
}

export interface PersonalizeBody {
  prospect: { name: string; title: string; domain: string; linkedin?: string };
  sender?: { name: string; company: string; offer: string };
  levels?: number[];
  provider?: string;
  model?: string;
  system_prompt_override?: string | null;
  style_rules?: string | null;
  tone_preset?: string | null;
}

export interface UserMe {
  id: string;
  email: string;
  name: string | null;
  role: string;
  created_at: string;
}

export interface ApiKeyOut {
  id: string;
  name: string;
  prefix: string;
  brand: string | null;
  rate_limit_per_day: number;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface CreateApiKeyResp extends ApiKeyOut { key: string }

export interface WebhookOut {
  id: string;
  target_url: string;
  events: string[];
  brand: string | null;
  active: boolean;
  description: string | null;
  created_at: string;
}

export interface CreateWebhookResp extends WebhookOut { secret: string }

export interface WebhookDelivery {
  id: string;
  event_type: string;
  status: string;
  attempts: number;
  response_status: number | null;
  response_body: string | null;
  created_at: string;
  last_attempt_at: string | null;
}

export interface HistoryItem {
  id: string;
  brand: string;
  prospect_name: string;
  prospect_title: string;
  prospect_domain: string;
  sender_company: string | null;
  sender_name: string | null;
  tone_preset: string | null;
  picked_slot: string | null;
  created_at: string;
}

export interface HistoryDetail extends HistoryItem {
  style_rules: string | null;
  request_payload: Record<string, unknown>;
  response_payload: PersonalizeResponse;
  edited_subject?: string | null;
  edited_body?: string | null;
  edited_followup_subject?: string | null;
  edited_followup_body?: string | null;
}

export interface SavedSender {
  id: string;
  label: string;
  name: string;
  company: string;
  offer: string;
  is_default: boolean;
  created_at: string;
}

export interface IntegrationProvider {
  provider: string;
  label: string;
  required: string[];
}

export interface IntegrationOut {
  id: string;
  provider: string;
  label: string;
  is_default: boolean;
  last_used_at: string | null;
  created_at: string;
  config_preview: Record<string, string>;
}

export interface PushResult {
  ok: boolean;
  pushed: number;
  failed: number;
  errors: string[];
  provider: string;
}

export interface SuppressionEntry {
  id: string;
  email: string | null;
  domain: string | null;
  reason: string | null;
  source: string;
  created_at: string;
}

export interface IcpProfile {
  id: string;
  label: string;
  description: string;
  is_default: boolean;
  created_at: string;
}

export type ReplyIntent =
  | "interested" | "not_interested" | "ooo" | "wrong_person"
  | "unsubscribe" | "info_request" | "scheduling" | "other";

export interface ReplyClassification {
  intent: ReplyIntent;
  confidence: number;
  summary: string;
  suggested_action: string;
}

export interface ReplyDraft {
  label: string;
  subject: string | null;
  body: string;
}

export interface RewriteResult {
  subject: string;
  body: string;
  word_count: number;
  instruction: string;
}

export const api = {
  getBrand: (slug: string) => request<BrandConfig>(`/v1/brands/${slug}`, { auth: false }),
  listBrands: () => request<string[]>(`/v1/brands`, { auth: false }),
  personalize: (body: PersonalizeBody, brand: string) =>
    request<PersonalizeResponse>(`/v1/personalize`, {
      method: "POST",
      body: JSON.stringify(body),
      brand,
    }),
  captureLead: (email: string, brand: string, name?: string) =>
    request<{ token: string; lead_id: string }>(`/v1/leads`, {
      method: "POST",
      body: JSON.stringify({ email, name }),
      brand,
      auth: false,
    }),
  signup: (email: string, password: string, name?: string) =>
    request<{ token: string; email: string; name: string | null }>(`/v1/auth/signup`, {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
      auth: false,
    }),
  login: (email: string, password: string) =>
    request<{ token: string; email: string; name: string | null }>(`/v1/auth/login`, {
      method: "POST",
      body: JSON.stringify({ email, password }),
      auth: false,
    }),
  me: () => request<UserMe>(`/v1/auth/me`),
  changePassword: (current_password: string, new_password: string) =>
    request<void>(`/v1/auth/password`, {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
  logout: () => request<void>(`/v1/auth/logout`, { method: "POST" }),

  batch: (body: PersonalizeBody & { prospects: PersonalizeBody["prospect"][]; include_followup?: boolean }, brand: string) =>
    request<{ job_id: string }>(`/v1/personalize/batch`, {
      method: "POST",
      body: JSON.stringify(body),
      brand,
    }),
  // Excel multipart upload (server parses headers, no client-side xlsx lib needed).
  batchExcel: async (
    file: File,
    sender: { name: string; company: string; offer: string },
    opts: { brand: string; include_followup?: boolean; tone_preset?: string; style_rules?: string },
  ): Promise<{ job_id: string; total: number; include_followup: boolean }> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("sender_name", sender.name);
    fd.append("sender_company", sender.company);
    fd.append("sender_offer", sender.offer);
    if (opts.include_followup) fd.append("include_followup", "true");
    if (opts.tone_preset) fd.append("tone_preset", opts.tone_preset);
    if (opts.style_rules) fd.append("style_rules", opts.style_rules);
    const headers: Record<string, string> = { "X-Brand": opts.brand };
    const t = getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    const res = await fetch(`/v1/personalize/excel`, { method: "POST", body: fd, headers });
    if (!res.ok) {
      let d: unknown;
      try { d = await res.json(); } catch { d = await res.text(); }
      const msg = typeof d === "object" && d && "detail" in (d as object)
        ? String((d as Record<string, unknown>).detail)
        : `HTTP ${res.status}`;
      throw new Error(msg);
    }
    const j = await res.json();
    return { job_id: j.job_id, total: Number(j.total || 0), include_followup: j.include_followup === "True" };
  },
  getJob: (jobId: string) =>
    request<{
      job_id: string;
      status: string;
      brand: string;
      total: number;
      done: number;
      failed_count: number;
      live: Record<string, unknown>;
      results: Record<number, PersonalizeResponse | { error: string }>;
      has_source_excel: boolean;
      source_filename: string | null;
    }>(`/v1/jobs/${jobId}`),
  // Trigger a file download; returns the blob URL for the caller to use in an <a> click.
  exportJob: async (jobId: string, opts: { format?: "xlsx" | "csv"; pick?: "A" | "B" | "C" | "auto" } = {}) => {
    const sp = new URLSearchParams();
    sp.set("format", opts.format || "xlsx");
    sp.set("pick", opts.pick || "auto");
    const headers: Record<string, string> = {};
    const t = getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    const res = await fetch(`/v1/jobs/${jobId}/export?${sp.toString()}`, { headers });
    if (!res.ok) throw new Error(`Export failed: HTTP ${res.status}`);
    const blob = await res.blob();
    const disp = res.headers.get("Content-Disposition") || "";
    const m = /filename="([^"]+)"/.exec(disp);
    const filename = m ? m[1] : `export-${jobId}.${opts.format || "xlsx"}`;
    return { blob, filename };
  },

  // API keys
  listApiKeys: () => request<ApiKeyOut[]>(`/v1/api-keys`),
  createApiKey: (name: string, opts?: { brand?: string; rate_limit_per_day?: number }) =>
    request<CreateApiKeyResp>(`/v1/api-keys`, {
      method: "POST",
      body: JSON.stringify({ name, ...opts }),
    }),
  revokeApiKey: (id: string) => request<void>(`/v1/api-keys/${id}`, { method: "DELETE" }),

  // Webhooks
  listWebhooks: () => request<WebhookOut[]>(`/v1/webhooks`),
  createWebhook: (
    target_url: string,
    events: string[],
    description?: string,
  ) => request<CreateWebhookResp>(`/v1/webhooks`, {
    method: "POST",
    body: JSON.stringify({ target_url, events, description }),
  }),
  revokeWebhook: (id: string) => request<void>(`/v1/webhooks/${id}`, { method: "DELETE" }),
  listWebhookDeliveries: (id: string) => request<WebhookDelivery[]>(`/v1/webhooks/${id}/deliveries?limit=50`),

  // History
  listHistory: (params: { limit?: number; offset?: number; brand?: string; q?: string } = {}) => {
    const sp = new URLSearchParams();
    if (params.limit) sp.set("limit", String(params.limit));
    if (params.offset) sp.set("offset", String(params.offset));
    if (params.brand) sp.set("brand", params.brand);
    if (params.q) sp.set("q", params.q);
    const qs = sp.toString();
    return request<{ items: HistoryItem[]; total: number; limit: number; offset: number }>(
      `/v1/history${qs ? "?" + qs : ""}`,
    );
  },
  getHistoryItem: (id: string) => request<HistoryDetail>(`/v1/history/${id}`),
  pickHistoryVariation: (id: string, picked_slot: "A" | "B" | "C") =>
    request<HistoryDetail>(`/v1/history/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ picked_slot }),
    }),
  deleteHistoryItem: (id: string) => request<void>(`/v1/history/${id}`, { method: "DELETE" }),

  // Saved senders
  listSenders: () => request<SavedSender[]>(`/v1/senders`),
  createSender: (body: { label: string; name: string; company: string; offer: string; is_default?: boolean }) =>
    request<SavedSender>(`/v1/senders`, { method: "POST", body: JSON.stringify(body) }),
  updateSender: (id: string, body: { label: string; name: string; company: string; offer: string; is_default?: boolean }) =>
    request<SavedSender>(`/v1/senders/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteSender: (id: string) => request<void>(`/v1/senders/${id}`, { method: "DELETE" }),

  // Integrations
  listIntegrationProviders: () => request<IntegrationProvider[]>(`/v1/integrations/providers`),
  listIntegrations: () => request<IntegrationOut[]>(`/v1/integrations`),
  createIntegration: (provider: string, label: string, config: Record<string, string>, is_default = false) =>
    request<IntegrationOut>(`/v1/integrations`, {
      method: "POST",
      body: JSON.stringify({ provider, label, config, is_default }),
    }),
  updateIntegration: (id: string, body: { label?: string; config?: Record<string, string>; is_default?: boolean }) =>
    request<IntegrationOut>(`/v1/integrations/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteIntegration: (id: string) => request<void>(`/v1/integrations/${id}`, { method: "DELETE" }),
  healthcheckIntegration: (id: string) => request<{ ok: boolean; message: string }>(`/v1/integrations/${id}/healthcheck`, { method: "POST" }),
  pushJobToIntegration: (jobId: string, integrationId: string, pick: "auto" | "A" | "B" | "C" = "auto") =>
    request<PushResult>(`/v1/jobs/${jobId}/push`, {
      method: "POST",
      body: JSON.stringify({ integration_id: integrationId, pick }),
    }),

  // Suppression list (DNC)
  listSuppressions: () => request<SuppressionEntry[]>(`/v1/suppressions`),
  addSuppression: (body: { email?: string; domain?: string; reason?: string }) =>
    request<SuppressionEntry>(`/v1/suppressions`, { method: "POST", body: JSON.stringify(body) }),
  deleteSuppression: (id: string) => request<void>(`/v1/suppressions/${id}`, { method: "DELETE" }),
  bulkUploadSuppressions: async (file: File): Promise<{ added: number; skipped: number }> => {
    const fd = new FormData();
    fd.append("file", file);
    const headers: Record<string, string> = {};
    const t = getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
    const res = await fetch(`/v1/suppressions/bulk`, { method: "POST", body: fd, headers });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`Upload failed: ${detail}`);
    }
    return res.json();
  },

  // ICP profiles
  listIcpProfiles: () => request<IcpProfile[]>(`/v1/icp-profiles`),
  createIcpProfile: (body: { label: string; description: string; is_default?: boolean }) =>
    request<IcpProfile>(`/v1/icp-profiles`, { method: "POST", body: JSON.stringify(body) }),
  updateIcpProfile: (id: string, body: { label: string; description: string; is_default?: boolean }) =>
    request<IcpProfile>(`/v1/icp-profiles/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteIcpProfile: (id: string) => request<void>(`/v1/icp-profiles/${id}`, { method: "DELETE" }),
  scoreIcpOne: (
    prospect: PersonalizeBody["prospect"],
    opts: { icp_profile_id?: string; icp_description?: string },
  ) => request<{ score: number; reason: string }>(`/v1/icp-profiles/score`, {
    method: "POST",
    body: JSON.stringify({ prospect, ...opts }),
  }),

  // Replies
  classifyReply: (body: {
    reply_body: string;
    original_email?: string;
    sender_first_name?: string;
  }) => request<ReplyClassification>(`/v1/replies/classify`, {
    method: "POST", body: JSON.stringify(body),
  }),
  draftReplies: (body: {
    reply_body: string;
    intent: ReplyIntent;
    original_email?: string;
    sender_name: string;
    sender_company: string;
    sender_offer?: string;
    n?: number;
  }) => request<{ drafts: ReplyDraft[] }>(`/v1/replies/draft`, {
    method: "POST", body: JSON.stringify(body),
  }),

  // Rewrite (A2)
  rewriteEmail: (body: { subject: string; body: string; instruction: string; model?: string }) =>
    request<RewriteResult>(`/v1/personalize/rewrite`, { method: "POST", body: JSON.stringify(body) }),

  // Per-row regenerate (A3)
  regenerateRow: (jobId: string, index: number, opts: {
    tone_preset?: string; style_rules?: string; include_followup?: boolean; model?: string
  } = {}) =>
    request<PersonalizeResponse>(`/v1/jobs/${jobId}/regenerate/${index}`, {
      method: "POST", body: JSON.stringify(opts),
    }),

  // History edits (A1)
  patchHistoryRun: (id: string, body: {
    picked_slot?: "A" | "B" | "C";
    edited_subject?: string | null;
    edited_body?: string | null;
    edited_followup_subject?: string | null;
    edited_followup_body?: string | null;
  }) => request<HistoryDetail>(`/v1/history/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
};
