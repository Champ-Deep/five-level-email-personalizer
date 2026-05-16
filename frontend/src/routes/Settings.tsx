import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { InternalLayout } from "@/components/InternalLayout";
import { api, setToken, type UserMe } from "@/lib/api";

export function SettingsRoute() {
  const navigate = useNavigate();
  const [me, setMe] = useState<UserMe | null>(null);
  const [pwCurr, setPwCurr] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { api.me().then(setMe).catch(e => setErr(String(e))); }, []);

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setMsg(null); setErr(null);
    try {
      if (pwNew.length < 8) throw new Error("New password must be at least 8 characters");
      await api.changePassword(pwCurr, pwNew);
      setMsg("Password updated.");
      setPwCurr(""); setPwNew("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const signOut = async () => {
    try { await api.logout(); } catch { /* ignore */ }
    setToken(null);
    navigate("/login");
  };

  const inputClass = "w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none";
  const inputStyle = {
    background: "var(--brand-bg)",
    borderColor: "var(--brand-rule)",
    color: "var(--brand-ink)",
  };

  return (
    <InternalLayout title="Settings" subtitle="Account details and security.">
      <div className="space-y-6">
        <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            Profile
          </h2>
          {me ? (
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div><dt className="text-xs uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Email</dt><dd style={{ color: "var(--brand-ink)" }}>{me.email}</dd></div>
              <div><dt className="text-xs uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Name</dt><dd style={{ color: "var(--brand-ink)" }}>{me.name || "—"}</dd></div>
              <div><dt className="text-xs uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Role</dt><dd style={{ color: "var(--brand-ink)" }}>{me.role}</dd></div>
              <div><dt className="text-xs uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>Member since</dt><dd style={{ color: "var(--brand-ink)" }}>{new Date(me.created_at).toLocaleDateString()}</dd></div>
            </dl>
          ) : <div className="text-sm" style={{ color: "var(--brand-muted)" }}>Loading…</div>}
        </section>

        <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            Change password
          </h2>
          <form onSubmit={changePassword} className="space-y-3 max-w-md">
            <input
              type="password" required autoComplete="current-password"
              className={inputClass} style={inputStyle}
              placeholder="Current password" value={pwCurr}
              onChange={e => setPwCurr(e.target.value)}
            />
            <input
              type="password" required minLength={8} autoComplete="new-password"
              className={inputClass} style={inputStyle}
              placeholder="New password (min 8 chars)" value={pwNew}
              onChange={e => setPwNew(e.target.value)}
            />
            {msg && <div className="text-xs" style={{ color: "#15803d" }}>{msg}</div>}
            {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
            <button
              type="submit" disabled={busy || !pwCurr || !pwNew}
              className="rounded-lg px-5 py-2.5 text-sm font-bold disabled:opacity-60"
              style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
            >
              {busy ? "Updating…" : "Update password"}
            </button>
          </form>
        </section>

        <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <h2 className="mb-3 text-xs font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
            Session
          </h2>
          <p className="mb-3 text-sm" style={{ color: "var(--brand-muted)" }}>
            Sign out revokes this device's token immediately (server-side blacklist for the remaining TTL).
          </p>
          <button
            onClick={signOut}
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
