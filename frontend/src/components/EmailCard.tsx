import { useState } from "react";
import type { EmailDraft } from "@/lib/api";
import { CopyBtn } from "./CopyBtn";
import { levelMeta } from "@/lib/levels";

interface Props {
  level: number;
  email: EmailDraft | null;
  loading: boolean;
  senderName: string;
}

export function EmailCard({ level, email, loading, senderName }: Props) {
  const [open, setOpen] = useState(true);
  const meta = levelMeta(level);

  const bodyWithoutSignoff = email ? email.body.replace(/\s*Best,\s*[^\n]*\s*$/i, "").trim() : "";
  const fullText = email ? `Subject: ${email.subject}\n\n${bodyWithoutSignoff}\n\nBest,\n${senderName}` : "";

  return (
    <div
      className="overflow-hidden rounded-xl border transition-colors"
      style={{
        background: "var(--brand-bg)",
        borderColor: "var(--brand-rule)",
        borderLeft: "3px solid var(--brand-accent)",
        animation: email ? "fadeUp .35s ease" : "none",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left"
      >
        <span
          className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full text-xs font-extrabold"
          style={{
            background: "var(--brand-accent-soft)",
            color: "var(--brand-accent)",
            border: "1px solid var(--brand-rule)",
          }}
        >
          {meta.id}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold" style={{ color: "var(--brand-ink)" }}>{meta.label}</span>
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider"
              style={{ background: "var(--brand-accent-soft)", color: "var(--brand-accent)" }}
            >
              {meta.tag}
            </span>
          </div>
          <div className="mt-0.5 truncate text-xs" style={{ color: "var(--brand-muted)" }}>{meta.premise}</div>
        </div>
        <div className="flex items-center gap-2">
          {loading && (
            <div
              className="h-4 w-4 rounded-full border-2"
              style={{
                borderColor: "var(--brand-rule)",
                borderTopColor: "var(--brand-accent)",
                animation: "spin .8s linear infinite",
              }}
            />
          )}
          {email && !loading && <CopyBtn text={fullText} />}
          <span
            className="inline-block text-xs transition-transform"
            style={{
              color: "var(--brand-muted)",
              transform: open ? "rotate(180deg)" : "rotate(0deg)",
            }}
          >
            ▾
          </span>
        </div>
      </button>

      {open && (
        <div className="border-t px-5 pb-5" style={{ borderColor: "var(--brand-rule)" }}>
          {loading && (
            <div className="space-y-2 py-5">
              {[85, 70, 90, 55, 75].map((w, i) => (
                <div
                  key={i}
                  className="h-3 rounded"
                  style={{
                    width: `${w}%`,
                    background: "linear-gradient(90deg, var(--brand-accent-soft) 0%, transparent 50%, var(--brand-accent-soft) 100%)",
                    backgroundSize: "200% 100%",
                    animation: `shimmer 1.4s ease-in-out ${i * 120}ms infinite`,
                  }}
                />
              ))}
            </div>
          )}
          {!loading && email && (
            <>
              <pre
                className="mt-4 whitespace-pre-wrap break-words font-brand-display text-[13.5px] leading-relaxed"
                style={{ color: "var(--brand-ink)" }}
              >
                {fullText}
              </pre>
              {email.warnings.length > 0 && (
                <div
                  className="mt-3 rounded-md border px-3 py-2 text-xs"
                  style={{
                    background: "rgba(251,191,36,.08)",
                    borderColor: "rgba(251,191,36,.35)",
                    color: "#92400e",
                  }}
                >
                  <strong>Warnings:</strong> {email.warnings.join(" · ")}
                </div>
              )}
            </>
          )}
          {!loading && !email && (
            <div className="py-5 text-sm" style={{ color: "var(--brand-muted)" }}>Waiting to generate…</div>
          )}
        </div>
      )}
    </div>
  );
}
