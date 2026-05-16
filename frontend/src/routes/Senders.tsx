import { useEffect, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { api, type SavedSender } from "@/lib/api";

const blank = { label: "", name: "", company: "", offer: "", is_default: false };

export function SendersRoute() {
  const [senders, setSenders] = useState<SavedSender[]>([]);
  const [form, setForm] = useState<typeof blank>(blank);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = () => api.listSenders().then(setSenders).catch(e => setErr(String(e)));
  useEffect(() => { load(); }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      if (editingId) await api.updateSender(editingId, form);
      else await api.createSender(form);
      setForm(blank); setEditingId(null);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const edit = (s: SavedSender) => {
    setForm({ label: s.label, name: s.name, company: s.company, offer: s.offer, is_default: s.is_default });
    setEditingId(s.id);
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this saved sender?")) return;
    await api.deleteSender(id);
    load();
  };

  const inputClass = "w-full rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="Saved senders"
      subtitle="Quick-pick presets for the Sender block on the lead-magnet form. Mark one as default to pre-fill new runs."
    >
      <section className="mb-6 rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          {editingId ? "Edit sender" : "New saved sender"}
        </h2>
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
          <input placeholder='Label (e.g. "Deep @ LakeB2B")' className={inputClass} style={inputStyle}
            value={form.label} onChange={e => setForm({ ...form, label: e.target.value })} required />
          <input placeholder="Your name" className={inputClass} style={inputStyle}
            value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          <input placeholder="Company" className={inputClass} style={inputStyle}
            value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} required />
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--brand-ink)" }}>
            <input type="checkbox" checked={form.is_default}
              onChange={e => setForm({ ...form, is_default: e.target.checked })} />
            Use as default
          </label>
          <textarea
            placeholder="What you're offering (1-2 sentences)"
            rows={2}
            className={`${inputClass} sm:col-span-2`} style={{ ...inputStyle, resize: "vertical" }}
            value={form.offer} onChange={e => setForm({ ...form, offer: e.target.value })} required
          />
          {err && <div className="text-xs sm:col-span-2" style={{ color: "#dc2626" }}>{err}</div>}
          <div className="flex gap-2 sm:col-span-2">
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
          Your saved senders ({senders.length})
        </h2>
        {senders.length === 0
          ? <p className="text-sm" style={{ color: "var(--brand-muted)" }}>None yet.</p>
          : (
            <ul className="space-y-2">
              {senders.map(s => (
                <li key={s.id} className="rounded-lg border p-4"
                  style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <strong className="text-sm" style={{ color: "var(--brand-ink)" }}>{s.label}</strong>
                        {s.is_default && (
                          <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>Default</span>
                        )}
                      </div>
                      <div className="mt-1 text-xs" style={{ color: "var(--brand-muted)" }}>
                        {s.name} · {s.company}
                      </div>
                      <div className="mt-1 text-sm" style={{ color: "var(--brand-ink)" }}>{s.offer}</div>
                    </div>
                    <button onClick={() => edit(s)} className="text-xs font-semibold" style={{ color: "var(--brand-accent)" }}>Edit</button>
                    <button onClick={() => remove(s.id)} className="text-xs font-semibold" style={{ color: "#dc2626" }}>Delete</button>
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
