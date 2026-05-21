import { useEffect, useState } from "react";
import { api, type Variation } from "@/lib/api";
import { CopyBtn } from "./CopyBtn";
import { ScoreChips } from "./ScoreChips";

interface Props {
  variation: Variation;
  senderName: string;
  picked: boolean;
  onPick: () => void;
  /** When true, the card surfaces an Edit and AI Rewrite affordance. */
  editable?: boolean;
  /** Server-stored user-edited subject (overrides email.subject if set). */
  editedSubject?: string | null;
  /** Server-stored user-edited body (overrides email.body if set). */
  editedBody?: string | null;
  /** Persist user edits (null/empty body clears the override). */
  onSaveEdits?: (subject: string | null, body: string | null) => Promise<void>;
}

const REWRITE_PRESETS: Array<{ label: string; instruction: string }> = [
  { label: "30% shorter",       instruction: "Cut roughly 30% of the words while keeping the anchor signal and the single CTA. Tighten every sentence." },
  { label: "More direct",       instruction: "Make the email more direct and confident. Drop softeners and hedges. Keep the same anchor signal." },
  { label: "Softer CTA",        instruction: "Soften the call-to-action so it feels like an invitation, not a request. Keep length and anchor signal the same." },
  { label: "Friendlier",        instruction: "Warm the tone up. Sound like a colleague, not a vendor. Keep the structure and the single CTA." },
  { label: "More specific",     instruction: "Replace any generic claims with concrete specifics drawn from the anchor signal. Keep the length the same." },
];

export function VariationCard({
  variation,
  senderName,
  picked,
  onPick,
  editable = false,
  editedSubject,
  editedBody,
  onSaveEdits,
}: Props) {
  const [open, setOpen] = useState(true);
  const { slot, label, model, email } = variation;

  // Edit-mode state
  const [editing, setEditing] = useState(false);
  const [draftSubject, setDraftSubject] = useState<string>("");
  const [draftBody, setDraftBody] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [rewriteErr, setRewriteErr] = useState<string | null>(null);
  const [showRewrite, setShowRewrite] = useState(false);
  const [customInstruction, setCustomInstruction] = useState("");

  // Effective subject/body (server-stored edits trump LLM output).
  const effectiveSubject = (editedSubject && editedSubject.trim()) || email?.subject || "";
  const effectiveBody = (editedBody && editedBody.trim()) || email?.body || "";

  // Reset draft state when entering edit mode or when the underlying email changes.
  useEffect(() => {
    if (editing) {
      setDraftSubject(effectiveSubject);
      setDraftBody(effectiveBody);
    }
  }, [editing, effectiveSubject, effectiveBody]);

  const bodyWithoutSignoff = effectiveBody
    ? effectiveBody.replace(/\s*Best,\s*[^\n]*\s*$/i, "").trim()
    : "";
  const fullText = email
    ? `Subject: ${effectiveSubject}\n\n${bodyWithoutSignoff}\n\nBest,\n${senderName}`
    : "";

  const hasEdits = Boolean(
    (editedSubject && editedSubject.trim()) || (editedBody && editedBody.trim()),
  );

  const startEdit = () => {
    setEditing(true);
    setShowRewrite(false);
  };

  const cancelEdit = () => {
    setEditing(false);
    setDraftSubject("");
    setDraftBody("");
  };

  const saveEdits = async () => {
    if (!onSaveEdits) return;
    const subjChanged = draftSubject.trim() !== (email?.subject || "").trim();
    const bodyChanged = draftBody.trim() !== (email?.body || "").trim();
    setSaving(true);
    try {
      await onSaveEdits(
        subjChanged ? draftSubject.trim() : null,
        bodyChanged ? draftBody.trim() : null,
      );
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const clearEdits = async () => {
    if (!onSaveEdits) return;
    if (!confirm("Discard your edits and revert to the AI-written version?")) return;
    setSaving(true);
    try {
      await onSaveEdits(null, null);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const runRewrite = async (instruction: string) => {
    if (!instruction.trim()) return;
    setRewriting(true);
    setRewriteErr(null);
    try {
      const r = await api.rewriteEmail({
        subject: editing ? draftSubject : effectiveSubject,
        body: editing ? draftBody : effectiveBody,
        instruction: instruction.trim(),
      });
      // Drop the rewritten text straight into the edit buffer so the user
      // can keep tweaking before saving.
      setEditing(true);
      setDraftSubject(r.subject);
      setDraftBody(r.body);
      setShowRewrite(false);
      setCustomInstruction("");
    } catch (e) {
      setRewriteErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRewriting(false);
    }
  };

  return (
    <div
      className="overflow-hidden rounded-xl border transition"
      style={{
        background: "var(--brand-bg)",
        borderColor: picked ? "var(--brand-accent)" : "var(--brand-rule)",
        borderLeft: `3px solid var(--brand-accent)`,
        boxShadow: picked ? "0 0 0 2px var(--brand-accent-soft)" : undefined,
        animation: "fadeUp .35s ease",
      }}
    >
      <div className="flex items-center gap-3 border-b px-4 py-3" style={{ borderColor: "var(--brand-rule)" }}>
        <span
          className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full text-xs font-extrabold"
          style={{
            background: "var(--brand-accent-soft)",
            color: "var(--brand-accent)",
            border: "1px solid var(--brand-rule)",
          }}
        >
          {slot}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold" style={{ color: "var(--brand-ink)" }}>{label}</span>
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-mono"
              style={{ background: "var(--brand-accent-soft)", color: "var(--brand-muted)" }}
              title={model}
            >
              {model}
            </span>
            {hasEdits && (
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
                style={{ background: "rgba(21,128,61,.10)", color: "#15803d", border: "1px solid rgba(21,128,61,.30)" }}
                title="You've edited this draft. Edits override the AI version when exported or pushed."
              >
                edited
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onPick}
          className="rounded-md border px-3 py-1.5 text-xs font-bold tracking-wider transition"
          style={{
            background: picked ? "var(--brand-accent)" : "transparent",
            color: picked ? "var(--brand-bg)" : "var(--brand-accent)",
            borderColor: "var(--brand-accent)",
          }}
        >
          {picked ? "✓ PICKED" : "I'd SEND THIS"}
        </button>
        {editable && onSaveEdits && !editing && email && !email.subject.startsWith("[") && (
          <button
            type="button"
            onClick={startEdit}
            className="rounded-md border px-2.5 py-1.5 text-xs font-semibold"
            style={{ borderColor: "var(--brand-rule)", color: "var(--brand-muted)" }}
            title="Edit subject and body"
          >
            ✏ Edit
          </button>
        )}
        {editable && onSaveEdits && !editing && email && !email.subject.startsWith("[") && (
          <button
            type="button"
            onClick={() => setShowRewrite(s => !s)}
            className="rounded-md border px-2.5 py-1.5 text-xs font-semibold"
            style={{ borderColor: "var(--brand-rule)", color: "var(--brand-muted)" }}
            title="Rewrite this email with an AI instruction"
          >
            ✨ AI rewrite
          </button>
        )}
        {email && !email.subject.startsWith("[") && <CopyBtn text={fullText} />}
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="text-xs"
          style={{ color: "var(--brand-muted)", transform: open ? "rotate(180deg)" : undefined, transition: "transform .2s" }}
          aria-label={open ? "Collapse" : "Expand"}
        >
          ▾
        </button>
      </div>

      {open && (
        <div className="px-5 pb-5">
          {email ? (
            <>
              {editing ? (
                <div className="mt-4 space-y-3">
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
                      Subject
                    </label>
                    <input
                      type="text"
                      className="w-full rounded-lg border px-3 py-2 text-sm outline-none"
                      style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
                      value={draftSubject}
                      onChange={e => setDraftSubject(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
                      Body
                    </label>
                    <textarea
                      rows={10}
                      className="w-full rounded-lg border px-3 py-2 font-brand-display text-[13px] leading-relaxed outline-none"
                      style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)", resize: "vertical" }}
                      value={draftBody}
                      onChange={e => setDraftBody(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={saveEdits}
                      disabled={saving}
                      className="rounded-md px-3 py-1.5 text-xs font-bold disabled:opacity-60"
                      style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
                    >
                      {saving ? "Saving…" : "Save edits"}
                    </button>
                    <button
                      onClick={cancelEdit}
                      disabled={saving}
                      className="rounded-md border px-3 py-1.5 text-xs font-semibold"
                      style={{ borderColor: "var(--brand-rule)", color: "var(--brand-muted)" }}
                    >
                      Cancel
                    </button>
                    {hasEdits && (
                      <button
                        onClick={clearEdits}
                        disabled={saving}
                        className="rounded-md border px-3 py-1.5 text-xs font-semibold"
                        style={{ borderColor: "var(--brand-rule)", color: "#dc2626" }}
                        title="Discard edits and revert to AI version"
                      >
                        Revert to AI
                      </button>
                    )}
                    <span className="flex-1" />
                    <button
                      type="button"
                      onClick={() => setShowRewrite(s => !s)}
                      className="rounded-md border px-2.5 py-1.5 text-xs font-semibold"
                      style={{ borderColor: "var(--brand-rule)", color: "var(--brand-muted)" }}
                    >
                      ✨ AI rewrite
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <pre
                    className="mt-4 whitespace-pre-wrap break-words font-brand-display text-[13.5px] leading-relaxed"
                    style={{ color: "var(--brand-ink)" }}
                  >
                    {fullText}
                  </pre>
                  <ScoreChips scores={email.scores} />
                  <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px]" style={{ color: "var(--brand-muted)" }}>
                    <span>{email.word_count} words</span>
                    {email.anchor_signal && (
                      <span title="Anchor signal">anchor: <em>{email.anchor_signal.slice(0, 80)}</em></span>
                    )}
                  </div>
                  {email.warnings.length > 0 && (
                    <div
                      className="mt-3 rounded-md border px-3 py-2 text-xs"
                      style={{
                        background: "rgba(251,191,36,.08)",
                        borderColor: "rgba(251,191,36,.35)",
                        color: "#92400e",
                      }}
                    >
                      <strong>Style warnings:</strong> {email.warnings.join(" · ")}
                    </div>
                  )}
                </>
              )}

              {showRewrite && (
                <div
                  className="mt-4 rounded-lg border p-3"
                  style={{ background: "var(--brand-accent-soft)", borderColor: "var(--brand-rule)" }}
                >
                  <div className="mb-2 text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--brand-accent)" }}>
                    AI rewrite
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {REWRITE_PRESETS.map(p => (
                      <button
                        key={p.label}
                        onClick={() => runRewrite(p.instruction)}
                        disabled={rewriting}
                        className="rounded-md border px-2.5 py-1 text-xs font-semibold disabled:opacity-50"
                        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-accent)" }}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Or give your own instruction (e.g. 'mention they just raised a Series B')"
                      className="flex-1 rounded-md border px-2.5 py-1.5 text-xs outline-none"
                      style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
                      value={customInstruction}
                      onChange={e => setCustomInstruction(e.target.value)}
                      onKeyDown={e => { if (e.key === "Enter") runRewrite(customInstruction); }}
                    />
                    <button
                      onClick={() => runRewrite(customInstruction)}
                      disabled={rewriting || !customInstruction.trim()}
                      className="rounded-md px-3 py-1.5 text-xs font-bold disabled:opacity-50"
                      style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
                    >
                      {rewriting ? "Rewriting…" : "Rewrite"}
                    </button>
                  </div>
                  {rewriteErr && (
                    <div className="mt-2 text-[11px]" style={{ color: "#dc2626" }}>{rewriteErr}</div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="py-5 text-sm" style={{ color: "var(--brand-muted)" }}>Generating…</div>
          )}
        </div>
      )}
    </div>
  );
}
