import type { Brief } from "@/lib/api";

export function BriefPanel({ brief }: { brief: Brief | null }) {
  if (!brief) return null;
  const rows: [string, string][] = [
    ["Name", brief.name],
    ["Title", brief.title],
    ["Company", brief.company],
    ["Industry", brief.industry],
  ];
  const topSignals = [...brief.company_signals.slice(0, 2), ...brief.individual_signals.slice(0, 1)];

  return (
    <section
      className="rounded-xl border p-5"
      style={{
        background: "var(--brand-bg)",
        borderColor: "var(--brand-rule)",
        borderLeft: "3px solid var(--brand-accent)",
        animation: "fadeUp .35s ease",
      }}
    >
      <div className="mb-4 flex items-center gap-3">
        <span className="text-[11px] font-bold tracking-[0.18em]" style={{ color: "var(--brand-accent)" }}>
          PROSPECT BRIEF
        </span>
        <div className="h-px flex-1" style={{ background: "var(--brand-rule)" }} />
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 md:grid-cols-4">
        {rows.map(([k, v]) => (
          <div key={k}>
            <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
              {k}
            </div>
            <div className="text-sm font-medium" style={{ color: "var(--brand-ink)" }}>
              {v || "·"}
            </div>
          </div>
        ))}
      </div>

      <div className="mb-3">
        <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
          Top Signals
        </div>
        <div className="flex flex-col gap-1.5">
          {topSignals.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-sm leading-relaxed" style={{ color: "var(--brand-muted)" }}>
              <span style={{ color: "var(--brand-accent)" }}>›</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>

      {brief.strongest_trigger && (
        <div
          className="rounded-lg border px-4 py-3"
          style={{
            background: "var(--brand-accent-soft)",
            borderColor: "var(--brand-rule)",
          }}
        >
          <div className="mb-1 text-[10px] font-bold tracking-[0.1em]" style={{ color: "var(--brand-accent)" }}>
            STRONGEST TRIGGER
          </div>
          <div className="text-sm leading-relaxed" style={{ color: "var(--brand-ink)" }}>
            {brief.strongest_trigger}
          </div>
        </div>
      )}
    </section>
  );
}
