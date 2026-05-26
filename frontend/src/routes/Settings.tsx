import { useClerk, useUser } from "@clerk/clerk-react";
import { InternalLayout } from "@/components/InternalLayout";

/**
 * Post-Clerk settings page. Password changes, email changes, and 2FA
 * all live in the Clerk-managed user profile modal — clicking the
 * "Manage account" button below pops that open, so we don't ship our
 * own form for any of it.
 */
export function SettingsRoute() {
  const { user } = useUser();
  const { openUserProfile, signOut } = useClerk();

  return (
    <InternalLayout title="Settings" subtitle="Account details and security.">
      <div className="space-y-6">
        <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            Profile
          </h2>
          {user ? (
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div><dt className="text-xs uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Email</dt>
                <dd style={{ color: "var(--brand-ink)" }}>{user.primaryEmailAddress?.emailAddress || "—"}</dd></div>
              <div><dt className="text-xs uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Name</dt>
                <dd style={{ color: "var(--brand-ink)" }}>{user.fullName || user.firstName || "—"}</dd></div>
              <div><dt className="text-xs uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Clerk ID</dt>
                <dd className="font-mono text-[11px]" style={{ color: "var(--brand-ink)" }}>{user.id}</dd></div>
              <div><dt className="text-xs uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Member since</dt>
                <dd style={{ color: "var(--brand-ink)" }}>{user.createdAt ? new Date(user.createdAt).toLocaleDateString() : "—"}</dd></div>
            </dl>
          ) : <div className="text-sm" style={{ color: "var(--brand-muted)" }}>Loading…</div>}
        </section>

        <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            Account & security
          </h2>
          <p className="mb-3 text-sm" style={{ color: "var(--brand-muted)" }}>
            Change your password, update your email, enable two-factor, or connect Google. Clerk handles all of this for us.
          </p>
          <button
            onClick={() => openUserProfile()}
            className="rounded-lg px-5 py-2.5 text-sm font-bold"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            Manage account
          </button>
        </section>

        <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            Session
          </h2>
          <button
            onClick={() => signOut({ redirectUrl: "/" })}
            className="rounded-lg border px-5 py-2.5 text-sm font-semibold"
            style={{ borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
          >
            Sign out
          </button>
        </section>
      </div>
    </InternalLayout>
  );
}
