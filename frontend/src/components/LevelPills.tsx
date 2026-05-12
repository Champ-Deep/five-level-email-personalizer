import { LEVELS } from "@/lib/levels";

export function LevelPills() {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {LEVELS.map(l => (
        <span
          key={l.id}
          className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold tracking-wider"
          style={{
            background: "var(--brand-accent-soft)",
            borderColor: "var(--brand-rule)",
            color: "var(--brand-accent)",
          }}
        >
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: "var(--brand-accent)" }}
          />
          L{l.id} · {l.label}
        </span>
      ))}
    </div>
  );
}
