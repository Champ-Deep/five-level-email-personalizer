import { useEffect, useRef, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { api, type SuppressionEntry } from "@/lib/api";

export function SuppressionsRoute() {
  const [items, setItems] = useState<SuppressionEntry[]>([]);
  const [target, setTarget] = useState("");  // email or domain
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => api.listSuppressions().then(setItems).catch(e => setErr(String(e)));
  useEffect(() => { load(); }, []);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null); setMsg(null);
    try {
      const t = target.trim().toLowerCase();
      const body = t.includes("@") ? { email: t, reason: reason || undefined }
                                   : { domain: t.replace(/^\./, ""), reason: reason || undefined };
      await api.addSuppression(body);
      setTarget(""); setReason("");
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const bulk = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await api.bulkUploadSuppressions(f);
      setMsg(`Added ${r.added}, skipped ${r.skipped} (already present or invalid).`);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Remove from suppression list?")) return;
    await api.deleteSuppression(id);
    load();
  };

  const inputClass = "rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="Suppression list"
      subtitle="Do-not-contact list. Any prospect whose email or domain matches is automatically skipped in batches."
    >
      <section className="mb-6 rounded-2xl border p-6 space-y-3" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <h2 className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Add a target
        </h2>
        <form onSubmit={add} className="flex flex-wrap gap-2">
          <input
            className={`${inputClass} flex-1 min-w-[260px]`} style={inputStyle}
            placeholder="email@company.com  OR  competitor.com"
            value={target} onChange={e => setTarget(e.target.value)} required
          />
          <input
            className={inputClass} style={inputStyle}
            placeholder="Reason (optional)"
            value={reason} onChange={e => setReason(e.target.value)}
          />
          <button type="submit" disabled={busy || !target.trim()}
            className="rounded-lg px-5 py-2 text-sm font-bold disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>
            {busy ? "Adding…" : "Add"}
          </button>
        </form>
        <div className="flex items-center gap-3 border-t pt-3" style={{ borderColor: "var(--brand-rule)" }}>
          <span className="text-xs" style={{ color: "var(--brand-muted)" }}>Bulk upload (.csv, one per line):</span>
          <input ref={fileRef} type="file" accept=".csv" onChange={bulk} className="text-xs" />
        </div>
        {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
        {msg && <div className="text-xs" style={{ color: "#15803d" }}>{msg}</div>}
      </section>

      <section>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          On your list ({items.length})
        </h2>
        {items.length === 0
          ? <p className="text-sm" style={{ color: "var(--brand-muted)" }}>Empty.</p>
          : (
            <ul className="space-y-1.5">
              {items.map(s => (
                <li key={s.id} className="flex items-center gap-3 rounded-lg border px-3 py-2 text-sm"
                  style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
                  <span className="font-mono" style={{ color: "var(--brand-ink)" }}>
                    {s.email || s.domain}
                  </span>
                  {s.email && (
                    <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
                      style={{ background: "var(--brand-accent-soft)", color: "var(--brand-accent)" }}>email</span>
                  )}
                  {s.domain && !s.email && (
                    <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
                      style={{ background: "var(--brand-accent-soft)", color: "var(--brand-accent)" }}>domain</span>
                  )}
                  <span className="flex-1 text-xs" style={{ color: "var(--brand-muted)" }}>
                    {s.reason || s.source} · {new Date(s.created_at).toLocaleDateString()}
                  </span>
                  <button onClick={() => remove(s.id)} className="text-xs font-semibold" style={{ color: "#dc2626" }}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </section>
    </InternalLayout>
  );
}
