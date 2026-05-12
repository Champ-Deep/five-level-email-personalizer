import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";

export function LoginRoute() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = mode === "signup"
        ? await api.signup(email, password, name || undefined)
        : await api.login(email, password);
      setToken(res.token);
      navigate("/app");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center px-4" style={{ background: "var(--brand-bg)" }}>
      <div
        className="w-full max-w-sm rounded-2xl border p-6"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <h1 className="mb-1 font-brand-display text-xl font-extrabold" style={{ color: "var(--brand-ink)" }}>
          {mode === "signup" ? "Create internal account" : "Sign in"}
        </h1>
        <p className="mb-5 text-xs" style={{ color: "var(--brand-muted)" }}>
          Internal tool — for sales & marketing teams.
        </p>
        <form onSubmit={submit} className="space-y-3">
          {mode === "signup" && (
            <input
              className="w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none"
              style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
              placeholder="Name (optional)"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          )}
          <input
            type="email"
            required
            className="w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none"
            style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
            placeholder="Work email"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
          <input
            type="password"
            required
            minLength={8}
            className="w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none"
            style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
            placeholder="Password (min 8 chars)"
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
          {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg px-5 py-3 text-sm font-bold disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            {busy ? "…" : mode === "signup" ? "Create account" : "Sign in"}
          </button>
          <button
            type="button"
            onClick={() => setMode(m => (m === "signup" ? "login" : "signup"))}
            className="block w-full text-center text-xs"
            style={{ color: "var(--brand-muted)" }}
          >
            {mode === "signup" ? "Already have an account? Sign in" : "Need an account? Sign up"}
          </button>
        </form>
        <div className="mt-6 text-center text-xs">
          <Link to="/lead-magnet/lakeb2b" style={{ color: "var(--brand-accent)" }}>
            ← back to lead magnet
          </Link>
        </div>
      </div>
    </div>
  );
}
