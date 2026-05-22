import { useEffect, useMemo, useState } from "react";
import { InternalLayout } from "@/components/InternalLayout";
import { CopyBtn } from "@/components/CopyBtn";
import {
  api,
  type BulkReplyItem,
  type ReplyClassification,
  type ReplyDraft,
  type ReplyIntent,
  type SavedSender,
} from "@/lib/api";

const INTENT_COLOR: Record<ReplyIntent, string> = {
  interested:     "#15803d",
  not_interested: "#dc2626",
  ooo:            "#854d0e",
  wrong_person:   "#854d0e",
  unsubscribe:    "#b91c1c",
  info_request:   "#1d4ed8",
  scheduling:     "#15803d",
  other:          "#5C5C66",
};

const INTENT_LABEL: Record<ReplyIntent, string> = {
  interested: "Interested",
  not_interested: "Not interested",
  ooo: "Out of office",
  wrong_person: "Wrong person",
  unsubscribe: "Unsubscribe",
  info_request: "Info request",
  scheduling: "Scheduling",
  other: "Other",
};

export function RepliesRoute() {
  const [mode, setMode] = useState<"single" | "bulk">("single");
  const [senders, setSenders] = useState<SavedSender[]>([]);
  const [senderId, setSenderId] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listSenders().then(s => {
      setSenders(s);
      const def = s.find(x => x.is_default) || s[0];
      if (def) setSenderId(def.id);
    }).catch(() => { /* ok */ });
  }, []);

  const sender = senders.find(s => s.id === senderId);

  const inputClass = "w-full rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="Reply triage"
      subtitle="Classify inbound replies and draft response options. Switch to Bulk to handle a backlog of replies in one go."
    >
      <div className="mb-4 inline-flex rounded-lg border p-1" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        {(["single", "bulk"] as const).map(m => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className="rounded-md px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition"
            style={{
              background: mode === m ? "var(--brand-accent)" : "transparent",
              color: mode === m ? "var(--brand-bg)" : "var(--brand-muted)",
            }}
          >
            {m === "single" ? "Single reply" : "Bulk (paste many)"}
          </button>
        ))}
      </div>

      {err && <div className="mb-4 text-xs" style={{ color: "#dc2626" }}>{err}</div>}

      {mode === "single" ? (
        <SingleRepliePanel
          sender={sender} senders={senders} senderId={senderId}
          setSenderId={setSenderId}
          onError={setErr}
          inputClass={inputClass} inputStyle={inputStyle}
        />
      ) : (
        <BulkRepliesPanel
          sender={sender} senders={senders} senderId={senderId}
          setSenderId={setSenderId}
          onError={setErr}
          inputClass={inputClass} inputStyle={inputStyle}
        />
      )}
    </InternalLayout>
  );
}

interface PanelProps {
  sender: SavedSender | undefined;
  senders: SavedSender[];
  senderId: string;
  setSenderId: (id: string) => void;
  onError: (e: string | null) => void;
  inputClass: string;
  inputStyle: React.CSSProperties;
}

function SingleRepliePanel({ sender, senders, senderId, setSenderId, onError, inputClass, inputStyle }: PanelProps) {
  const [reply, setReply] = useState("");
  const [original, setOriginal] = useState("");
  const [classification, setClassification] = useState<ReplyClassification | null>(null);
  const [drafts, setDrafts] = useState<ReplyDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [drafting, setDrafting] = useState(false);

  const classify = async () => {
    if (!reply.trim()) return;
    setBusy(true); onError(null); setDrafts([]); setClassification(null);
    try {
      const c = await api.classifyReply({
        reply_body: reply.trim(),
        original_email: original.trim() || undefined,
      });
      setClassification(c);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const draft = async () => {
    if (!classification || !sender) return;
    setDrafting(true); onError(null);
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
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setDrafting(false);
    }
  };

  return (
    <>
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
              {INTENT_LABEL[classification.intent]}
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
    </>
  );
}

// ─── Bulk panel ────────────────────────────────────────────────────────

interface ParsedReply {
  id: string;
  reply_body: string;
}

/** Split a paste of multiple replies by blank lines, "---" separators,
 *  or "From:" headers (Gmail forward pattern). We label each by an
 *  index so the user can match the row back to their inbox. */
function parseReplies(text: string): ParsedReply[] {
  if (!text.trim()) return [];
  // First try "---" or "===" hard separators.
  let chunks = text.split(/\n\s*(?:---+|===+)\s*\n/);
  // Fallback: split on a blank line followed by "From:" (Gmail forward).
  if (chunks.length === 1) {
    chunks = text.split(/\n\n(?=From:\s)/i);
  }
  // Final fallback: split on double blank lines.
  if (chunks.length === 1) {
    chunks = text.split(/\n{3,}/);
  }
  return chunks
    .map(c => c.trim())
    .filter(c => c.length >= 5)
    .map((reply_body, i) => ({ id: `reply-${i + 1}`, reply_body }));
}

function BulkRepliesPanel({ sender, senders, senderId, setSenderId, onError, inputClass, inputStyle }: PanelProps) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<BulkReplyItem[] | null>(null);
  const [byIntent, setByIntent] = useState<Record<string, string[]> | null>(null);
  const [draftsByIntent, setDraftsByIntent] = useState<Record<string, ReplyDraft[]>>({});
  const [draftingIntent, setDraftingIntent] = useState<ReplyIntent | null>(null);

  const parsed = useMemo(() => parseReplies(text), [text]);

  const run = async () => {
    if (parsed.length === 0) return;
    setBusy(true); onError(null); setResults(null); setByIntent(null); setDraftsByIntent({});
    try {
      const r = await api.classifyRepliesBulk(parsed.map(p => ({ id: p.id, reply_body: p.reply_body })));
      setResults(r.items);
      setByIntent(r.by_intent);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const draftForIntent = async (intent: ReplyIntent) => {
    if (!sender) { onError("Pick a saved sender first."); return; }
    // Use the highest-confidence reply with this intent as the template
    // source — drafting per-reply would explode token cost.
    const sample = (results || []).filter(r => r.intent === intent).sort((a, b) => b.confidence - a.confidence)[0];
    if (!sample) return;
    const sampleSource = parsed.find(p => p.id === sample.id);
    if (!sampleSource) return;
    setDraftingIntent(intent);
    onError(null);
    try {
      const r = await api.draftReplies({
        reply_body: sampleSource.reply_body,
        intent,
        sender_name: sender.name,
        sender_company: sender.company,
        sender_offer: sender.offer,
        n: 2,
      });
      setDraftsByIntent(prev => ({ ...prev, [intent]: r.drafts }));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setDraftingIntent(null);
    }
  };

  const copyAllForIntent = (intent: ReplyIntent) => {
    const drafts = draftsByIntent[intent];
    if (!drafts || drafts.length === 0) return;
    const template = drafts[0];
    const full = (template.subject ? `Subject: ${template.subject}\n\n` : "") + template.body;
    navigator.clipboard.writeText(full);
  };

  const intentsSeen = byIntent ? (Object.keys(byIntent) as ReplyIntent[]) : [];

  return (
    <>
      <section className="mb-6 rounded-2xl border p-6 space-y-3" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <div>
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            Paste all the replies you want to triage (up to 50)
          </label>
          <p className="mb-2 text-[11px]" style={{ color: "var(--brand-muted)" }}>
            Separate replies with a blank line, a line of dashes (---), or a "From:" header. The system splits automatically.
          </p>
          <textarea rows={12}
            className={inputClass} style={{ ...inputStyle, resize: "vertical" }}
            placeholder={`Reply 1 text...\n\n---\n\nReply 2 text...`}
            value={text} onChange={e => setText(e.target.value)}
          />
          <div className="mt-2 text-[11px]" style={{ color: "var(--brand-muted)" }}>
            Detected: <strong>{parsed.length}</strong> {parsed.length === 1 ? "reply" : "replies"}
            {parsed.length > 50 && <span style={{ color: "#dc2626" }}> · over the 50-reply limit, only the first 50 will run</span>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <select value={senderId} onChange={e => setSenderId(e.target.value)}
            className={inputClass} style={{ ...inputStyle, maxWidth: 280 }}>
            <option value="">{senders.length === 0 ? "No saved senders" : "Sender for drafts…"}</option>
            {senders.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          <button onClick={run} disabled={busy || parsed.length === 0}
            className="rounded-lg px-5 py-2 text-sm font-bold disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}>
            {busy ? `Classifying ${parsed.length}…` : `Classify ${parsed.length || ""} replies`}
          </button>
        </div>
      </section>

      {results && byIntent && (
        <section className="space-y-4">
          {intentsSeen.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--brand-muted)" }}>No replies classified.</p>
          ) : intentsSeen.map(intent => {
            const ids = byIntent[intent] || [];
            const drafts = draftsByIntent[intent];
            return (
              <div key={intent} className="rounded-2xl border" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
                <div className="flex flex-wrap items-center gap-3 border-b px-5 py-3" style={{ borderColor: "var(--brand-rule)" }}>
                  <span className="rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider"
                    style={{
                      background: INTENT_COLOR[intent] + "22",
                      color: INTENT_COLOR[intent],
                      border: `1px solid ${INTENT_COLOR[intent]}55`,
                    }}>
                    {INTENT_LABEL[intent]}
                  </span>
                  <span className="text-sm font-semibold" style={{ color: "var(--brand-ink)" }}>
                    {ids.length} {ids.length === 1 ? "reply" : "replies"}
                  </span>
                  <span className="flex-1" />
                  <button
                    onClick={() => draftForIntent(intent)}
                    disabled={draftingIntent === intent}
                    className="rounded-md border px-2.5 py-1 text-xs font-semibold disabled:opacity-60"
                    style={{ borderColor: "var(--brand-rule)", color: "var(--brand-accent)" }}
                  >
                    {draftingIntent === intent ? "Drafting…" : drafts ? "Re-draft template" : "Draft template reply"}
                  </button>
                  {drafts && drafts.length > 0 && (
                    <button
                      onClick={() => copyAllForIntent(intent)}
                      className="rounded-md border px-2.5 py-1 text-xs font-semibold"
                      style={{ borderColor: "var(--brand-rule)", color: "var(--brand-muted)" }}
                      title="Copy the top template — paste into each thread"
                    >
                      ⧉ Copy template
                    </button>
                  )}
                </div>
                <ul className="divide-y" style={{ borderColor: "var(--brand-rule)" }}>
                  {ids.map(id => {
                    const r = (results || []).find(x => x.id === id);
                    const src = parsed.find(p => p.id === id);
                    if (!r || !src) return null;
                    return (
                      <li key={id} className="px-5 py-3 text-sm">
                        <div className="flex items-baseline gap-2">
                          <span className="font-mono text-[10px]" style={{ color: "var(--brand-muted)" }}>{r.id}</span>
                          <span className="font-mono text-[10px]" style={{ color: "var(--brand-muted)" }}>·</span>
                          <span className="font-mono text-[10px]" style={{ color: "var(--brand-muted)" }}>{r.confidence}/100</span>
                          <span style={{ color: "var(--brand-ink)" }}>{r.summary}</span>
                        </div>
                        <div className="mt-1 text-[12px]" style={{ color: "var(--brand-muted)" }}>
                          Action: {r.suggested_action}
                        </div>
                        <details className="mt-1">
                          <summary className="cursor-pointer text-[11px]" style={{ color: "var(--brand-muted)" }}>show source</summary>
                          <pre className="mt-1 whitespace-pre-wrap break-words text-[11px]"
                            style={{ color: "var(--brand-muted)" }}>{src.reply_body.slice(0, 600)}{src.reply_body.length > 600 ? "…" : ""}</pre>
                        </details>
                      </li>
                    );
                  })}
                </ul>
                {drafts && drafts.length > 0 && (
                  <div className="border-t p-4 space-y-3" style={{ borderColor: "var(--brand-rule)" }}>
                    {drafts.map((d, i) => {
                      const full = (d.subject ? `Subject: ${d.subject}\n\n` : "") + d.body;
                      return (
                        <div key={i} className="rounded-lg border p-3"
                          style={{ background: "var(--brand-accent-soft)", borderColor: "var(--brand-rule)" }}>
                          <div className="mb-1 flex items-center gap-2">
                            <strong className="text-xs" style={{ color: "var(--brand-ink)" }}>{d.label}</strong>
                            <span className="flex-1" />
                            <CopyBtn text={full} />
                          </div>
                          {d.subject && (
                            <div className="text-[12px] font-semibold" style={{ color: "var(--brand-ink)" }}>Subject: {d.subject}</div>
                          )}
                          <pre className="mt-1 whitespace-pre-wrap break-words font-brand-display text-[12px] leading-relaxed"
                            style={{ color: "var(--brand-ink)" }}>
                            {d.body}
                          </pre>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </section>
      )}
    </>
  );
}
