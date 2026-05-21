import { useEffect, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { api, type IcpProfile } from "@/lib/api";

const blank = { label: "", description: "", is_default: false };

export function IcpProfilesRoute() {
  const [items, setItems] = useState<IcpProfile[]>([]);
  const [form, setForm] = useState<typeof blank>(blank);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = () => api.listIcpProfiles().then(setItems).catch(e => setErr(String(e)));
  useEffect(() => { load(); }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      if (editingId) await api.updateIcpProfile(editingId, form);
      else await api.createIcpProfile(form);
      setForm(blank); setEditingId(null);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const edit = (p: IcpProfile) => {
    setForm({ label: p.label, description: p.description, is_default: p.is_default });
    setEditingId(p.id);
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this ICP profile?")) return;
    await api.deleteIcpProfile(id);
    load();
  };

  const inputClass = "w-full rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="ICP profiles"
      subtitle="Save an ideal customer profile description. Use it to score prospects 0-100 before personalizing — skip the bad fits, save your tokens."
    >
      <section className="mb-6 rounded-2xl border p-6 space-y-3" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <h2 className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          {editingId ? "Edit profile" : "New ICP profile"}
        </h2>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className={inputClass} style={inputStyle}
              placeholder='Label (e.g. "RevOps at Series B SaaS, US")'
              value={form.label} onChange={e => setForm({ ...form, label: e.target.value })} required
            />
            <label className="flex items-center gap-2 text-sm" style={{ color: "var(--brand-ink)" }}>
              <input type="checkbox" checked={form.is_default}
                onChange={e => setForm({ ...form, is_default: e.target.checked })} />
              Use as default
            </label>
          </div>
          <textarea rows={6}
            className={inputClass} style={{ ...inputStyle, resize: "vertical" }}
            placeholder="Describe your ideal customer in 3-6 sentences. Industry, company size, key titles, geography, ICP signals you actually care about (recent funding, hiring, AI adoption, etc.). The scorer reads this directly."
            value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} required minLength={20}
          />
          {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
          <div className="flex gap-2">
            <button type="submit" disabled={busy}
              className="rounded-lg px-5 py-2 text-sm font-bold disabled:opacity-60"
              style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>
              {busy ? "Saving…" : editingId ? "Update" : "Save"}
            </button>
            {editingId && (
              <button type="button" onClick={() => { setForm(blank); setEditingId(null); }}
                className="rounded-lg border px-5 py-2 text-sm font-semibold"
                style={{ borderColor: "var(--brand-rule)", color: "var(--brand-muted)" }}>
                Cancel
              </button>
            )}
          </div>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Your profiles ({items.length})
        </h2>
        {items.length === 0
          ? <p className="text-sm" style={{ color: "var(--brand-muted)" }}>None yet.</p>
          : (
            <ul className="space-y-2">
              {items.map(p => (
                <li key={p.id} className="rounded-lg border p-4"
                  style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <strong className="text-sm" style={{ color: "var(--brand-ink)" }}>{p.label}</strong>
                        {p.is_default && (
                          <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>Default</span>
                        )}
                      </div>
                      <p className="mt-1 text-sm leading-relaxed whitespace-pre-line" style={{ color: "var(--brand-ink)" }}>
                        {p.description}
                      </p>
                    </div>
                    <button onClick={() => edit(p)} className="text-xs font-semibold" style={{ color: "var(--brand-accent)" }}>Edit</button>
                    <button onClick={() => remove(p.id)} className="text-xs font-semibold" style={{ color: "#dc2626" }}>Delete</button>
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
