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

  batch: (body: PersonalizeBody & { prospects: PersonalizeBody["prospect"][] }, brand: string) =>
    request<{ job_id: string }>(`/v1/personalize/batch`, {
      method: "POST",
      body: JSON.stringify(body),
      brand,
    }),
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
    }>(`/v1/jobs/${jobId}`),

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
};
