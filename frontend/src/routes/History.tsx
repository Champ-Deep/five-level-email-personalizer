import { useEffect, useMemo, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { VariationCard } from "@/components/VariationCard";
import { BriefPanel } from "@/components/BriefPanel";
import { api, type HistoryItem, type HistoryDetail } from "@/lib/api";

export function HistoryRoute() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [pickedSlot, setPickedSlot] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = (query = "") => api.listHistory({ q: query || undefined, limit: 100 })
    .then(r => { setItems(r.items); setTotal(r.total); })
    .catch(e => setErr(String(e)));

  useEffect(() => { load(); }, []);

  // debounce search
  useEffect(() => {
    const t = setTimeout(() => load(q), 300);
    return () => clearTimeout(t);
  }, [q]);

  const expand = async (id: string) => {
    if (openId === id) { setOpenId(null); setDetail(null); setPickedSlot(null); return; }
    setOpenId(id);
    const d = await api.getHistoryItem(id);
    setDetail(d);
    setPickedSlot(d.picked_slot);
  };

  const pick = async (slot: "A" | "B" | "C") => {
    if (!detail) return;
    const updated = await api.patchHistoryRun(detail.id, { picked_slot: slot });
    setDetail(updated);
    setPickedSlot(slot);
    // Update the list row too
    setItems(items.map(i => i.id === detail.id ? { ...i, picked_slot: slot } : i));
  };

  // Save inline edits to subject/body. Edits only ever apply to the picked slot
  // (matches what gets exported), so saving auto-picks the slot if nothing is
  // picked yet.
  const saveEditsFor = async (slot: "A" | "B" | "C", subject: string | null, body: string | null) => {
    if (!detail) return;
    const updated = await api.patchHistoryRun(detail.id, {
      picked_slot: (pickedSlot as "A" | "B" | "C" | null) ?? slot,
      edited_subject: subject,
      edited_body: body,
    });
    setDetail(updated);
    setPickedSlot(updated.picked_slot);
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this run from history?")) return;
    await api.deleteHistoryItem(id);
    if (openId === id) { setOpenId(null); setDetail(null); }
    load(q);
  };

  const senderName = useMemo(() => detail?.sender_name || "Deep", [detail]);

  return (
    <InternalLayout
      title="History"
      subtitle={`${total} run${total === 1 ? "" : "s"} stored. Click a row to expand.`}
      actions={
        <input
          placeholder="Search prospect / domain / company"
          className="rounded-lg border px-3 py-2 text-sm outline-none"
          style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)", minWidth: 280 }}
          value={q} onChange={e => setQ(e.target.value)}
        />
      }
    >
      {err && <div className="mb-4 rounded-md border px-4 py-3 text-sm" style={{ borderColor: "#fca5a5", color: "#b91c1c", background: "#fef2f2" }}>{err}</div>}
      {items.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--brand-muted)" }}>
          No history yet. Run a personalization while signed in to populate this view.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map(item => (
            <li key={item.id} className="rounded-lg border" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
              <button
                onClick={() => expand(item.id)}
                className="flex w-full items-center gap-4 px-4 py-3 text-left"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <strong className="text-sm" style={{ color: "var(--brand-ink)" }}>{item.prospect_name}</strong>
                    <span className="text-xs" style={{ color: "var(--brand-muted)" }}>{item.prospect_title} · {item.prospect_domain}</span>
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px]" style={{ color: "var(--brand-muted)" }}>
                    <span>{new Date(item.created_at).toLocaleString()}</span>
                    <span>·</span>
                    <span>{item.brand}</span>
                    {item.tone_preset && (<><span>·</span><span>{item.tone_preset}</span></>)}
                    {item.picked_slot && (
                      <span
                        className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                        style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
                      >
                        Picked {item.picked_slot}
                      </span>
                    )}
                  </div>
                </div>
                <span className="text-xs" style={{ color: "var(--brand-muted)" }}>
                  {openId === item.id ? "▴" : "▾"}
                </span>
              </button>

              {openId === item.id && detail && detail.id === item.id && (
                <div className="space-y-4 border-t p-4" style={{ borderColor: "var(--brand-rule)" }}>
                  <BriefPanel brief={detail.response_payload.brief} />
                  <div className="space-y-3">
                    {(detail.response_payload.variations || []).map(v => {
                      const isPicked = pickedSlot === v.slot;
                      // Server-stored edits only apply to the picked slot —
                      // surface them on that card so the user can revert / re-edit.
                      const editedSubject = isPicked ? detail.edited_subject ?? null : null;
                      const editedBody = isPicked ? detail.edited_body ?? null : null;
                      return (
                        <VariationCard
                          key={v.slot}
                          variation={v}
                          senderName={senderName}
                          picked={isPicked}
                          onPick={() => pick(v.slot as "A" | "B" | "C")}
                          editable
                          editedSubject={editedSubject}
                          editedBody={editedBody}
                          onSaveEdits={(subject, body) => saveEditsFor(v.slot as "A" | "B" | "C", subject, body)}
                        />
                      );
                    })}
                  </div>
                  <div className="flex justify-end">
                    <button onClick={() => remove(detail.id)} className="text-xs font-semibold" style={{ color: "#dc2626" }}>
                      Delete this run
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </InternalLayout>
  );
}
