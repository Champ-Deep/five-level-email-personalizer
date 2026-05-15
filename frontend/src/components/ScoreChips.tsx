import { useState } from "react";
import type { EmailScores } from "@/lib/api";

interface Props {
  scores: EmailScores | null | undefined;
}

function color(score: number): { bg: string; fg: string; label: string } {
  if (score >= 80) return { bg: "rgba(34,197,94,.12)", fg: "#15803d", label: "Strong" };
  if (score >= 60) return { bg: "rgba(202,138,4,.12)", fg: "#854d0e", label: "OK" };
  return { bg: "rgba(220,38,38,.10)", fg: "#b91c1c", label: "Weak" };
}

export function ScoreChips({ scores }: Props) {
  const [openId, setOpenId] = useState<string | null>(null);

  if (!scores) return null;

  const blocks: Array<{ id: string; label: string; score: number; factors: Record<string, string> }> = [
    { id: "deliver", label: "Deliverability", score: scores.deliverability.score, factors: scores.deliverability.factors },
    { id: "reply", label: "Reply likelihood", score: scores.reply_likelihood.score, factors: scores.reply_likelihood.factors },
  ];

  return (
    <div className="mt-3 flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {blocks.map(b => {
          const c = color(b.score);
          const open = openId === b.id;
          return (
            <button
              key={b.id}
              type="button"
              onClick={() => setOpenId(open ? null : b.id)}
              className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold tracking-wider transition"
              style={{
                background: c.bg,
                borderColor: open ? c.fg : "var(--brand-rule)",
                color: c.fg,
              }}
              title="Click for factor breakdown"
            >
              <span className="font-mono text-[11px]">{b.score}/100</span>
              <span>{b.label.toUpperCase()}</span>
              <span style={{ opacity: 0.6 }}>{c.label}</span>
              <span style={{ fontSize: 9 }}>{open ? "▴" : "▾"}</span>
            </button>
          );
        })}
      </div>
      {openId && (() => {
        const b = blocks.find(x => x.id === openId)!;
        const entries = Object.entries(b.factors);
        return (
          <div
            className="rounded-md border px-3 py-2 text-[11px] leading-relaxed"
            style={{
              background: "var(--brand-bg)",
              borderColor: "var(--brand-rule)",
              color: "var(--brand-muted)",
            }}
          >
            {entries.length === 0 ? (
              <em>Clean. No negative factors detected.</em>
            ) : (
              <ul className="space-y-0.5">
                {entries.map(([key, val]) => (
                  <li key={key} className="flex gap-2">
                    <span className="font-mono" style={{ color: "var(--brand-accent)" }}>{key}:</span>
                    <span>{val}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })()}
    </div>
  );
}
