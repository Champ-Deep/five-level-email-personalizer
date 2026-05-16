import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";

export function SignupRoute() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      setErr("Password must be at least 8 characters");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const res = await api.signup(email, password, name || undefined);
      setToken(res.token);
      navigate("/app");
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
          Create account
        </h1>
        <p className="mb-5 text-xs" style={{ color: "var(--brand-muted)" }}>
          Internal tool for sales and marketing teams.
        </p>
        <form onSubmit={submit} className="space-y-3">
          <input
            className={inputClass} style={inputStyle}
            placeholder="Name (optional)" value={name}
            onChange={e => setName(e.target.value)}
          />
          <input
            type="email" required autoComplete="email"
            className={inputClass} style={inputStyle}
            placeholder="Work email" value={email}
            onChange={e => setEmail(e.target.value)}
          />
          <input
            type="password" required minLength={8} autoComplete="new-password"
            className={inputClass} style={inputStyle}
            placeholder="Password (min 8 chars)" value={password}
            onChange={e => setPassword(e.target.value)}
          />
          {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
          <button
            type="submit" disabled={busy}
            className="w-full rounded-lg px-5 py-3 text-sm font-bold disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>
        <div className="mt-6 space-y-2 text-center text-xs">
          <Link to="/login" style={{ color: "var(--brand-accent)" }}>
            Already have an account? Sign in
          </Link>
          <div>
            <Link to="/lead-magnet/lakeb2b" style={{ color: "var(--brand-muted)" }}>
              ← back to lead magnet
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
