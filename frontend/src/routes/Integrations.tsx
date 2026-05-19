import { useEffect, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { api, type IntegrationOut, type IntegrationProvider } from "@/lib/api";

const FIELD_HINTS: Record<string, string> = {
  api_key: "Bearer token (Instantly dashboard → Integrations)",
  api_token: "Service JWT or API key",
  campaign_id: "Destination Instantly campaign UUID",
  sequence_id: "ChampMail sequence UUID",
  base_url: "https://champmail.example.com",
  team_id: "ChampMail team UUID (optional, for multi-tenant)",
  webhook_url: "Full URL of the ChampIQ webhook receiver",
  webhook_secret: "HMAC-SHA256 secret used to sign each push",
};

export function IntegrationsRoute() {
  const [providers, setProviders] = useState<IntegrationProvider[]>([]);
  const [items, setItems] = useState<IntegrationOut[]>([]);
  const [selected, setSelected] = useState<string>("");  // provider key
  const [label, setLabel] = useState<string>("");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = () => Promise.all([
    api.listIntegrationProviders().then(setProviders),
    api.listIntegrations().then(setItems),
  ]).catch(e => setErr(String(e)));
  useEffect(() => { load(); }, []);

  const providerInfo = providers.find(p => p.provider === selected);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !label.trim()) return;
    setBusy(true); setErr(null); setMsg(null);
    try {
      const rec = await api.createIntegration(selected, label.trim(), config, items.length === 0);
      setMsg(`${providerInfo?.label || selected} integration "${rec.label}" added.`);
      setLabel(""); setConfig({}); setSelected("");
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Remove this integration?")) return;
    await api.deleteIntegration(id);
    load();
  };

  const testIt = async (id: string) => {
    setErr(null); setMsg(null);
    try {
      const r = await api.healthcheckIntegration(id);
      (r.ok ? setMsg : setErr)(`Health check: ${r.message}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const inputClass = "w-full rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="Integrations"
      subtitle="Push personalized batches into Instantly, ChampMail, or any ChampIQ-style webhook receiver. Credentials are encrypted at rest."
    >
      <section className="mb-6 rounded-2xl border p-6 space-y-3" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <h2 className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Connect a destination
        </h2>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Provider</label>
              <select value={selected} onChange={e => { setSelected(e.target.value); setConfig({}); }}
                className={inputClass} style={inputStyle}>
                <option value="">Choose a provider…</option>
                {providers.map(p => <option key={p.provider} value={p.provider}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Label</label>
              <input className={inputClass} style={inputStyle}
                placeholder='e.g. "LakeB2B Q3 Outbound"'
                value={label} onChange={e => setLabel(e.target.value)} />
            </div>
          </div>

          {providerInfo && (
            <div className="grid gap-3 sm:grid-cols-2">
              {providerInfo.required.map(field => (
                <div key={field}>
                  <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
                    {field}
                  </label>
                  <input
                    className={inputClass} style={inputStyle}
                    type={(field.includes("key") || field.includes("token") || field.includes("secret")) ? "password" : "text"}
                    placeholder={FIELD_HINTS[field] || ""}
                    value={config[field] || ""}
                    onChange={e => setConfig({ ...config, [field]: e.target.value })}
                  />
                </div>
              ))}
            </div>
          )}

          {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
          {msg && <div className="text-xs" style={{ color: "#15803d" }}>{msg}</div>}

          <button type="submit" disabled={busy || !selected || !label.trim()}
            className="rounded-lg px-5 py-2 text-sm font-bold disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>
            {busy ? "Saving…" : "Connect"}
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Your integrations ({items.length})
        </h2>
        {items.length === 0
          ? <p className="text-sm" style={{ color: "var(--brand-muted)" }}>None yet.</p>
          : (
            <ul className="space-y-2">
              {items.map(i => (
                <li key={i.id} className="rounded-lg border p-4"
                  style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <strong className="text-sm" style={{ color: "var(--brand-ink)" }}>{i.label}</strong>
                        <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                          style={{ background: "var(--brand-accent-soft)", color: "var(--brand-accent)" }}>
                          {i.provider}
                        </span>
                        {i.is_default && (
                          <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>
                            Default
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-[11px]" style={{ color: "var(--brand-muted)" }}>
                        {Object.entries(i.config_preview).map(([k, v]) => `${k}: ${v}`).join("  ·  ")}
                        {i.last_used_at && `  ·  Last used ${new Date(i.last_used_at).toLocaleDateString()}`}
                      </div>
                    </div>
                    <button onClick={() => testIt(i.id)} className="text-xs font-semibold" style={{ color: "var(--brand-accent)" }}>
                      Test
                    </button>
                    <button onClick={() => remove(i.id)} className="text-xs font-semibold" style={{ color: "#dc2626" }}>
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )
        }
      </section>
    </InternalLayout>
  );
}
