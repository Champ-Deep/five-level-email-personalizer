import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, setToken } from "@/lib/api";

export function ResetPasswordRoute() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) setErr("This reset link is missing its token. Request a new one.");
  }, [token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) { setErr("Password must be at least 8 characters."); return; }
    if (password !== confirm) { setErr("Passwords don't match."); return; }
    setBusy(true);
    try {
      const r = await api.resetPassword(token, password);
      setToken(r.token);
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
          Choose a new password
        </h1>
        <p className="mb-5 text-xs" style={{ color: "var(--brand-muted)" }}>
          You'll be signed in automatically once the reset is saved.
        </p>
        <form onSubmit={submit} className="space-y-3">
          <input
            type="password" required autoComplete="new-password"
            className={inputClass} style={inputStyle}
            placeholder="New password (min 8 chars)" value={password}
            onChange={e => setPassword(e.target.value)}
          />
          <input
            type="password" required autoComplete="new-password"
            className={inputClass} style={inputStyle}
            placeholder="Confirm new password" value={confirm}
            onChange={e => setConfirm(e.target.value)}
          />
          {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
          <button
            type="submit" disabled={busy || !token}
            className="w-full rounded-lg px-5 py-3 text-sm font-bold disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            {busy ? "Saving…" : "Reset password"}
          </button>
        </form>
        <div className="mt-6 text-center text-xs">
          <Link to="/login" style={{ color: "var(--brand-muted)" }}>
            ← back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
