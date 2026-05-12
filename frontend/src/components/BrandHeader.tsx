import { Link } from "react-router-dom";
import type { BrandConfig } from "@/lib/api";

export function BrandHeader({ brand, rightSlot }: { brand: BrandConfig; rightSlot?: React.ReactNode }) {
  return (
    <header
      className="border-b"
      style={{
        background: "var(--brand-bg)",
        borderColor: "var(--brand-rule)",
      }}
    >
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-3">
        <Link to="/" className="flex items-center gap-3">
          <span
            className="inline-flex items-center gap-2 rounded-lg border px-3 py-1.5"
            style={{
              background: "var(--brand-accent-soft)",
              borderColor: "var(--brand-rule)",
            }}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: "var(--brand-accent)" }} />
            <span className="text-[11px] font-bold tracking-[0.12em]" style={{ color: "var(--brand-accent)" }}>
              {brand.name.toUpperCase()}
            </span>
          </span>
        </Link>
        <div className="h-px flex-1" style={{ background: "var(--brand-rule)" }} />
        {rightSlot}
      </div>
    </header>
  );
}
