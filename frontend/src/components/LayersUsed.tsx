import type { Brief } from "@/lib/api";

const LAYERS: { id: number; tag: string; label: string; check: (b: Brief) => boolean }[] = [
  { id: 1, tag: "INDUSTRY",   label: "Industry",   check: b => !!b.industry },
  { id: 2, tag: "COMPANY",    label: "Company",    check: b => b.company_signals.length > 0 },
  { id: 3, tag: "ROLE",       label: "Role",       check: b => b.role_pain_points.length > 0 },
  { id: 4, tag: "INDIVIDUAL", label: "Individual", check: b => b.individual_signals.length > 0 },
  { id: 5, tag: "HYPER",      label: "Synthesis",  check: b => !!b.likely_pain_point || !!b.strongest_trigger },
];

export function LayersUsed({ brief }: { brief: Brief }) {
  return (
    <div
      className="rounded-lg border px-4 py-3"
      style={{ background: "var(--brand-accent-soft)", borderColor: "var(--brand-rule)" }}
    >
      <div className="mb-2 text-[10px] font-bold tracking-[0.15em]" style={{ color: "var(--brand-accent)" }}>
        SIGNAL LAYERS FUSED INTO THIS EMAIL
      </div>
      <div className="flex flex-wrap gap-2">
        {LAYERS.map(l => {
          const present = l.check(brief);
          return (
            <span
              key={l.id}
              className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-wider"
              style={{
                background: present ? "var(--brand-accent)" : "var(--brand-bg)",
                borderColor: present ? "var(--brand-accent)" : "var(--brand-rule)",
                color: present ? "var(--brand-bg)" : "var(--brand-muted)",
                opacity: present ? 1 : 0.55,
              }}
              title={present ? `${l.label} signal used` : `${l.label} signal missing`}
            >
              <span style={{ fontSize: 9 }}>{present ? "✓" : "○"}</span>
              L{l.id} · {l.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
