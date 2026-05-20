import { useEffect, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { CopyBtn } from "@/components/CopyBtn";
import { api, type ReplyClassification, type ReplyDraft, type SavedSender } from "@/lib/api";

const INTENT_COLOR: Record<ReplyClassification["intent"], string> = {
  interested:     "#15803d",
  not_interested: "#dc2626",
  ooo:            "#854d0e",
  wrong_person:   "#854d0e",
  unsubscribe:    "#b91c1c",
  info_request:   "#1d4ed8",
  scheduling:     "#15803d",
  other:          "#5C5C66",
};

export function RepliesRoute() {
  const [reply, setReply] = useState("");
  const [original, setOriginal] = useState("");
  const [senders, setSenders] = useState<SavedSender[]>([]);
  const [senderId, setSenderId] = useState<string>("");
  const [classification, setClassification] = useState<ReplyClassification | null>(null);
  const [drafts, setDrafts] = useState<ReplyDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listSenders().then(s => {
      setSenders(s);
      const def = s.find(x => x.is_default) || s[0];
      if (def) setSenderId(def.id);
    }).catch(() => { /* ok */ });
  }, []);

  const sender = senders.find(s => s.id === senderId);

  const classify = async () => {
    if (!reply.trim()) return;
    setBusy(true); setErr(null); setDrafts([]); setClassification(null);
    try {
      const c = await api.classifyReply({
        reply_body: reply.trim(),
        original_email: original.trim() || undefined,
      });
      setClassification(c);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const draft = async () => {
    if (!classification || !sender) return;
    setDrafting(true); setErr(null);
    try {
      const r = await api.draftReplies({
        reply_body: reply.trim(),
        intent: classification.intent,
        original_email: original.trim() || undefined,
        sender_name: sender.name,
        sender_company: sender.company,
        sender_offer: sender.offer,
        n: 3,
      });
      setDrafts(r.drafts);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setDrafting(false);
    }
  };

  const inputClass = "w-full rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="Reply triage"
      subtitle="Paste a reply you received. The system classifies the intent (interested, OOO, wrong person, unsubscribe…) and drafts response options."
    >
      <section className="mb-6 rounded-2xl border p-6 space-y-3" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <div>
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            Reply body (what they wrote back)
          </label>
          <textarea rows={6}
            className={inputClass} style={{ ...inputStyle, resize: "vertical" }}
            placeholder="Paste the full text of their reply…"
            value={reply} onChange={e => setReply(e.target.value)}
          />
        </div>
        <details>
          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            + Original email you sent (optional, improves drafting)
          </summary>
          <textarea rows={4} className={`mt-2 ${inputClass}`} style={{ ...inputStyle, resize: "vertical" }}
            placeholder="Paste the original email you sent (subject + body) for better context…"
            value={original} onChange={e => setOriginal(e.target.value)}
          />
        </details>
        {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
        <button onClick={classify} disabled={busy || !reply.trim()}
          className="rounded-lg px-5 py-2 text-sm font-bold disabled:opacity-60"
          style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>
          {busy ? "Classifying…" : "Classify reply"}
        </button>
      </section>

      {classification && (
        <section className="mb-6 rounded-2xl border p-6 space-y-3" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider"
              style={{ background: INTENT_COLOR[classification.intent] + "22", color: INTENT_COLOR[classification.intent], border: `1px solid ${INTENT_COLOR[classification.intent]}55` }}>
              {classification.intent.replace("_", " ")}
            </span>
            <span className="font-mono text-xs" style={{ color: "var(--brand-muted)" }}>
              confidence {classification.confidence}/100
            </span>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Summary</div>
            <p className="text-sm" style={{ color: "var(--brand-ink)" }}>{classification.summary}</p>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Suggested action</div>
            <p className="text-sm" style={{ color: "var(--brand-ink)" }}>{classification.suggested_action}</p>
          </div>
          <div className="flex items-center gap-2 border-t pt-3" style={{ borderColor: "var(--brand-rule)" }}>
            <select value={senderId} onChange={e => setSenderId(e.target.value)}
              className={inputClass} style={inputStyle}>
              <option value="">{senders.length === 0 ? "No saved senders" : "Sender for the reply…"}</option>
              {senders.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <button onClick={draft} disabled={drafting || !sender}
              className="rounded-lg px-4 py-2 text-sm font-bold disabled:opacity-60"
              style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>
              {drafting ? "Drafting…" : "Draft 3 replies"}
            </button>
          </div>
        </section>
      )}

      {drafts.length > 0 && (
        <section className="space-y-3">
          {drafts.map((d, i) => {
            const full = (d.subject ? `Subject: ${d.subject}\n\n` : "") + d.body;
            return (
              <div key={i} className="rounded-2xl border p-5"
                style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", borderLeft: "3px solid var(--brand-accent)" }}>
                <div className="mb-2 flex items-center gap-3">
                  <strong className="text-sm" style={{ color: "var(--brand-ink)" }}>{d.label}</strong>
                  <span className="flex-1" />
                  <CopyBtn text={full} />
                </div>
                {d.subject && (
                  <div className="text-sm font-semibold" style={{ color: "var(--brand-ink)" }}>Subject: {d.subject}</div>
                )}
                <pre className="mt-2 whitespace-pre-wrap break-words font-brand-display text-[13px] leading-relaxed"
                  style={{ color: "var(--brand-ink)" }}>
                  {d.body}
                </pre>
              </div>
            );
          })}
        </section>
      )}
    </InternalLayout>
  );
}
