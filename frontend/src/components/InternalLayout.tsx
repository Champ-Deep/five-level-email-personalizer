import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { UserButton, useUser } from "@clerk/clerk-react";
import { api, type BrandConfig } from "@/lib/api";
import { applyBrandTokens } from "@/lib/brandTokens";

const NAV: Array<{ to: string; label: string }> = [
  { to: "/app",              label: "Batch" },
  { to: "/app/history",      label: "History" },
  { to: "/app/replies",      label: "Reply triage" },
  { to: "/app/icp",          label: "ICP profiles" },
  { to: "/app/suppressions", label: "Suppressions" },
  { to: "/app/senders",      label: "Saved senders" },
  { to: "/app/integrations", label: "Integrations" },
  { to: "/app/api-keys",     label: "API keys" },
  { to: "/app/webhooks",     label: "Webhooks" },
  { to: "/app/settings",     label: "Settings" },
];

interface Props {
  /** What this page is doing — shown as the page title. */
  title: string;
  /** Subtitle (one-liner under the title). */
  subtitle?: string;
  children: React.ReactNode;
  /** Optional right-aligned slot for action buttons. */
  actions?: React.ReactNode;
}

export function InternalLayout({ title, subtitle, children, actions }: Props) {
  const location = useLocation();
  const { user } = useUser();
  const [brand, setBrand] = useState<BrandConfig | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.listBrands()
      .then(slugs => slugs[0] ? api.getBrand(slugs[0]) : null)
      .then(b => {
        if (cancelled) return;
        if (b) { setBrand(b); applyBrandTokens(b); }
      });
    return () => { cancelled = true; };
  }, []);

  if (!brand) return <div className="p-10 text-sm">Loading…</div>;

  return (
    <div className="min-h-screen" style={{ background: "var(--brand-bg)" }}>
      <header
        className="border-b"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-3">
          <Link to={`/lead-magnet/${brand.slug}`} className="flex items-center gap-3">
            <span
              className="inline-flex items-center gap-2 rounded-lg border px-3 py-1.5"
              style={{ background: "var(--brand-accent-soft)", borderColor: "var(--brand-rule)" }}
            >
              <span className="h-2 w-2 rounded-full" style={{ background: "var(--brand-accent)" }} />
              <span className="text-[11px] font-bold tracking-[0.12em]" style={{ color: "var(--brand-accent)" }}>
                {brand.name.toUpperCase()}
              </span>
            </span>
          </Link>
          <span className="text-xs" style={{ color: "var(--brand-muted)" }}>Internal</span>
          <span className="flex-1" />
          {user?.primaryEmailAddress?.emailAddress && (
            <span className="text-xs" style={{ color: "var(--brand-muted)" }}>
              {user.primaryEmailAddress.emailAddress}
            </span>
          )}
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl gap-8 px-6 py-8">
        <nav className="w-44 flex-shrink-0">
          <ul className="space-y-1">
            {NAV.map(item => {
              const active = item.to === "/app"
                ? location.pathname === "/app"
                : location.pathname.startsWith(item.to);
              return (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className="block rounded-md px-3 py-2 text-sm transition"
                    style={{
                      background: active ? "var(--brand-accent)" : "transparent",
                      color: active ? "var(--brand-bg)" : "var(--brand-ink)",
                      fontWeight: active ? 700 : 500,
                    }}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <main className="min-w-0 flex-1">
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h1 className="font-brand-display text-2xl font-extrabold" style={{ color: "var(--brand-ink)" }}>
                {title}
              </h1>
              {subtitle && (
                <p className="mt-1 text-sm" style={{ color: "var(--brand-muted)" }}>{subtitle}</p>
              )}
            </div>
            {actions}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
