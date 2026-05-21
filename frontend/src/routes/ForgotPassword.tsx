import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";

export function ForgotPasswordRoute() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.forgotPassword(email);
      setSent(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const inputClass = "w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none";
  const inputStyle = {
    background: "var(--brand-bg)",
    borderColor: "var(--brand-rule)",
    color: "var(--brand-ink)",
  };

  return (
    <div className="grid min-h-screen place-items-center px-4" style={{ background: "var(--brand-bg)" }}>
      <div
        className="w-full max-w-sm rounded-2xl border p-6"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <h1 className="mb-1 font-brand-display text-xl font-extrabold" style={{ color: "var(--brand-ink)" }}>
          Forgot password
        </h1>
        <p className="mb-5 text-xs" style={{ color: "var(--brand-muted)" }}>
          We'll email you a reset link if your account exists. The link expires in 60 minutes.
        </p>
        {sent ? (
          <div className="rounded-lg border px-3 py-3 text-sm" style={{ background: "var(--brand-accent-soft)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}>
            Check your inbox. If the address is registered, a reset link is on its way.
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <input
              type="email" required autoComplete="email"
              className={inputClass} style={inputStyle}
              placeholder="Work email" value={email}
              onChange={e => setEmail(e.target.value)}
            />
            {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
            <button
              type="submit" disabled={busy}
              className="w-full rounded-lg px-5 py-3 text-sm font-bold disabled:opacity-60"
              style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
            >
              {busy ? "Sending…" : "Email me a reset link"}
            </button>
          </form>
        )}
        <div className="mt-6 text-center text-xs">
          <Link to="/login" style={{ color: "var(--brand-muted)" }}>
            ← back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
