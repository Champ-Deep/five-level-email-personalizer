import { useEffect, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { CopyBtn } from "@/components/CopyBtn";
import { api, type ApiKeyOut } from "@/lib/api";

export function ApiKeysRoute() {
  const [keys, setKeys] = useState<ApiKeyOut[]>([]);
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [justCreated, setJustCreated] = useState<{ key: string; name: string } | null>(null);

  const load = () => api.listApiKeys().then(setKeys).catch(e => setErr(String(e)));
  useEffect(() => { load(); }, []);

  const createKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true); setErr(null);
    try {
      const res = await api.createApiKey(name, brand ? { brand } : undefined);
      setJustCreated({ key: res.key, name: res.name });
      setName(""); setBrand("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: string) => {
    if (!confirm("Revoke this API key? Any clients using it will fail immediately.")) return;
    await api.revokeApiKey(id);
    load();
  };

  const inputClass = "rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="API keys"
      subtitle="Mint long-lived keys for programmatic access to /v1/personalize. Use Authorization: Bearer ck_live_…"
    >
      <section className="mb-6 rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Create a new key
        </h2>
        <form onSubmit={createKey} className="flex flex-wrap gap-2">
          <input
            className={inputClass} style={inputStyle}
            placeholder='Label (e.g. "ChampMail production")'
            value={name} onChange={e => setName(e.target.value)}
          />
          <input
            className={inputClass} style={inputStyle}
            placeholder='Lock to brand (optional, e.g. "lakeb2b")'
            value={brand} onChange={e => setBrand(e.target.value)}
          />
          <button
            type="submit" disabled={busy || !name.trim()}
            className="rounded-lg px-5 py-2 text-sm font-bold disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            {busy ? "Creating…" : "Create key"}
          </button>
        </form>
        {err && <div className="mt-3 text-xs" style={{ color: "#dc2626" }}>{err}</div>}
        {justCreated && (
          <div
            className="mt-4 rounded-lg border p-3"
            style={{
              background: "rgba(34,197,94,.08)",
              borderColor: "rgba(34,197,94,.4)",
              color: "#15803d",
            }}
          >
            <div className="mb-2 text-xs font-bold uppercase tracking-wider">
              Key created — copy now (shown ONCE)
            </div>
            <div className="flex items-start gap-2">
              <code className="block flex-1 break-all rounded bg-white/50 p-2 text-xs">{justCreated.key}</code>
              <CopyBtn text={justCreated.key} label="Copy" />
            </div>
            <div className="mt-2 text-[11px] opacity-80">
              Label: <strong>{justCreated.name}</strong>. Stored hashed; you can't see this value again.
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Your keys ({keys.length})
        </h2>
        {keys.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--brand-muted)" }}>No keys yet.</p>
        ) : (
          <ul className="space-y-2">
            {keys.map(k => (
              <li
                key={k.id}
                className="flex items-center gap-3 rounded-lg border p-4"
                style={{
                  background: "var(--brand-bg)",
                  borderColor: "var(--brand-rule)",
                  opacity: k.revoked_at ? 0.5 : 1,
                }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <strong className="text-sm" style={{ color: "var(--brand-ink)" }}>{k.name}</strong>
                    <code className="text-[11px] opacity-70">ck_live_{k.prefix}…</code>
                    {k.brand && (
                      <span
                        className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                        style={{ background: "var(--brand-accent-soft)", color: "var(--brand-accent)" }}
                      >
                        {k.brand}
                      </span>
                    )}
                    {k.revoked_at && (
                      <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#dc2626" }}>
                        revoked
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-[11px]" style={{ color: "var(--brand-muted)" }}>
                    Created {new Date(k.created_at).toLocaleDateString()}
                    {k.last_used_at && ` · Last used ${new Date(k.last_used_at).toLocaleDateString()}`}
                    {` · ${k.rate_limit_per_day}/day limit`}
                  </div>
                </div>
                {!k.revoked_at && (
                  <button
                    onClick={() => revoke(k.id)}
                    className="text-xs font-semibold"
                    style={{ color: "#dc2626" }}
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </InternalLayout>
  );
}
