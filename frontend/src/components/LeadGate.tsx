import { useState } from "react";
import { api, setLeadToken } from "@/lib/api";

interface Props {
  brand: string;
  brandName: string;
  onUnlocked: () => void;
  onClose: () => void;
}

export function LeadGate({ brand, brandName, onUnlocked, onClose }: Props) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api.captureLead(email.trim(), brand, name.trim() || undefined);
      setLeadToken(res.token);
      onUnlocked();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div
        className="w-full max-w-md rounded-2xl border p-6 shadow-2xl"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <button
          onClick={onClose}
          className="float-right text-sm"
          style={{ color: "var(--brand-muted)" }}
          aria-label="Close"
        >
          ✕
        </button>
        <h2 className="mb-2 font-brand-display text-2xl font-extrabold" style={{ color: "var(--brand-ink)" }}>
          Unlock 20 personalizations/day + CSV batch
        </h2>
        <p className="mb-5 text-sm leading-relaxed" style={{ color: "var(--brand-muted)" }}>
          Tell us where to send the 5-Level cheat-sheet PDF. You'll get 20 free runs per day plus the ability to upload a CSV from {brandName}.
        </p>
        <form onSubmit={submit} className="space-y-3">
          <input
            type="email"
            required
            placeholder="you@company.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none"
            style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
          />
          <input
            placeholder="First name (optional)"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none"
            style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
          />
          {err && <div className="text-xs" style={{ color: "#dc2626" }}>{err}</div>}
          <button
            type="submit"
            disabled={busy || !email.trim()}
            className="w-full rounded-lg px-5 py-3 text-sm font-bold transition disabled:opacity-60"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            {busy ? "Sending…" : "Get my cheat sheet + unlock"}
          </button>
          <p className="text-center text-[11px]" style={{ color: "var(--brand-muted)" }}>
            One email. No marketing list. Unsubscribe any time.
          </p>
        </form>
      </div>
    </div>
  );
}
