import { useEffect, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { CopyBtn } from "@/components/CopyBtn";
import { api, type WebhookOut, type WebhookDelivery } from "@/lib/api";

const EVENTS = [
  "personalize.completed",
  "batch.queued",
  "batch.prospect.completed",
  "batch.completed",
  "lead.captured",
];

export function WebhooksRoute() {
  const [subs, setSubs] = useState<WebhookOut[]>([]);
  const [url, setUrl] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set(EVENTS));
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [justCreated, setJustCreated] = useState<{ secret: string; id: string } | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);

  const load = () => api.listWebhooks().then(setSubs).catch(e => setErr(String(e)));
  useEffect(() => { load(); }, []);

  const toggle = (e: string) => setSelected(s => {
    const ns = new Set(s); ns.has(e) ? ns.delete(e) : ns.add(e); return ns;
  });

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() || selected.size === 0) return;
    setBusy(true); setErr(null);
    try {
      const res = await api.createWebhook(url.trim(), Array.from(selected), description.trim() || undefined);
      setJustCreated({ secret: res.secret, id: res.id });
      setUrl(""); setDescription("");
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: string) => {
    if (!confirm("Disable this webhook? Future events won't be delivered to it.")) return;
    await api.revokeWebhook(id);
    load();
  };

  const showDeliveries = async (id: string) => {
    if (openId === id) { setOpenId(null); setDeliveries([]); return; }
    setOpenId(id);
    setDeliveries(await api.listWebhookDeliveries(id));
  };

  const inputClass = "w-full rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="Webhooks"
      subtitle="Subscribe to events. Each delivery is HMAC-SHA256 signed; verify with the secret shown ONCE at create time."
    >
      <section className="mb-6 rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Subscribe an endpoint
        </h2>
        <form onSubmit={create} className="space-y-3">
          <input
            type="url" required placeholder="https://your-crm.com/webhooks/personalize"
            className={inputClass} style={inputStyle}
            value={url} onChange={e => setUrl(e.target.value)}
          />
          <input
            placeholder="Description (optional)"
            className={inputClass} style={inputStyle}
            value={description} onChange={e => setDescription(e.target.value)}
          />
          <div>
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Events</div>
            <div className="flex flex-wrap gap-2">
              {EVENTS.map(e => (
                <button
                  key={e} type="button" onClick={() => toggle(e)}
                  className="rounded-full border px-3 py-1 text-xs font-semibold"
                  style={{
                    background: selected.has(e) ? "var(--brand-accent)" : "transparent",
                    color: selected.has(e) ? "var(--brand-bg)" : "var(--brand-muted)",
                    borderColor: selected.has(e) ? "var(--brand-accent)" : "var(--brand-rule)",
                  }}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>
          {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
          <button
            type="submit" disabled={busy || !url.trim() || selected.size === 0}
            className="rounded-lg px-5 py-2 text-sm font-bold disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            {busy ? "Creating…" : "Subscribe"}
          </button>
        </form>
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
              Secret — copy now (shown ONCE)
            </div>
            <div className="flex items-start gap-2">
              <code className="block flex-1 break-all rounded bg-white/50 p-2 text-xs">{justCreated.secret}</code>
              <CopyBtn text={justCreated.secret} label="Copy" />
            </div>
            <div className="mt-2 text-[11px] opacity-80">
              Use this to verify the <code>X-Champ-Signature</code> header on each delivery.
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Your subscriptions ({subs.length})
        </h2>
        {subs.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--brand-muted)" }}>No webhooks yet.</p>
        ) : (
          <ul className="space-y-2">
            {subs.map(w => (
              <li
                key={w.id}
                className="rounded-lg border p-4"
                style={{
                  background: "var(--brand-bg)",
                  borderColor: "var(--brand-rule)",
                  opacity: w.active ? 1 : 0.5,
                }}
              >
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="truncate font-mono text-sm" style={{ color: "var(--brand-ink)" }}>{w.target_url}</div>
                    <div className="mt-0.5 flex flex-wrap gap-1.5">
                      {w.events.map(ev => (
                        <span key={ev} className="rounded px-1.5 py-0.5 text-[10px] font-mono" style={{ background: "var(--brand-accent-soft)", color: "var(--brand-accent)" }}>{ev}</span>
                      ))}
                    </div>
                    {w.description && <div className="mt-1 text-[11px]" style={{ color: "var(--brand-muted)" }}>{w.description}</div>}
                  </div>
                  <button onClick={() => showDeliveries(w.id)} className="text-xs font-semibold" style={{ color: "var(--brand-accent)" }}>
                    {openId === w.id ? "Hide deliveries" : "Recent deliveries"}
                  </button>
                  {w.active && (
                    <button onClick={() => revoke(w.id)} className="text-xs font-semibold" style={{ color: "#dc2626" }}>
                      Disable
                    </button>
                  )}
                </div>
                {openId === w.id && (
                  <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--brand-rule)" }}>
                    {deliveries.length === 0
                      ? <span className="text-xs" style={{ color: "var(--brand-muted)" }}>No deliveries yet.</span>
                      : (
                        <ul className="space-y-1 text-xs">
                          {deliveries.slice(0, 10).map(d => (
                            <li key={d.id} className="flex items-center gap-3">
                              <span className="font-mono" style={{ color: "var(--brand-muted)" }}>{new Date(d.created_at).toLocaleString()}</span>
                              <span className="font-mono">{d.event_type}</span>
                              <span style={{ color: d.status === "delivered" ? "#15803d" : d.status === "failed" ? "#dc2626" : "var(--brand-muted)" }}>
                                {d.status}
                              </span>
                              {d.response_status !== null && <span style={{ color: "var(--brand-muted)" }}>{d.response_status}</span>}
                              {d.attempts > 1 && <span style={{ color: "var(--brand-muted)" }}>· {d.attempts} attempts</span>}
                            </li>
                          ))}
                        </ul>
                      )
                    }
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </InternalLayout>
  );
}
