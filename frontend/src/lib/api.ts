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
  const res = await fetch(path, { ...init, headers });
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

export interface EmailDraft {
  subject: string;
  body: string;
  word_count: number;
  anchor_signal: string;
  warnings: string[];
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
    request<{ token: string; email: string }>(`/v1/auth/signup`, {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
      auth: false,
    }),
  login: (email: string, password: string) =>
    request<{ token: string; email: string }>(`/v1/auth/login`, {
      method: "POST",
      body: JSON.stringify({ email, password }),
      auth: false,
    }),
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
};
