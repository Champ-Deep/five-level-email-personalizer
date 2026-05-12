import { useState } from "react";
import type { Variation } from "@/lib/api";
import { CopyBtn } from "./CopyBtn";

interface Props {
  variation: Variation;
  senderName: string;
  picked: boolean;
  onPick: () => void;
}

export function VariationCard({ variation, senderName, picked, onPick }: Props) {
  const [open, setOpen] = useState(true);
  const { slot, label, model, email } = variation;

  const bodyWithoutSignoff = email
    ? email.body.replace(/\s*Best,\s*[^\n]*\s*$/i, "").trim()
    : "";
  const fullText = email
    ? `Subject: ${email.subject}\n\n${bodyWithoutSignoff}\n\nBest,\n${senderName}`
    : "";

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
              <pre
                className="mt-4 whitespace-pre-wrap break-words font-brand-display text-[13.5px] leading-relaxed"
                style={{ color: "var(--brand-ink)" }}
              >
                {fullText}
              </pre>
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
          ) : (
            <div className="py-5 text-sm" style={{ color: "var(--brand-muted)" }}>Generating…</div>
          )}
        </div>
      )}
    </div>
  );
}
