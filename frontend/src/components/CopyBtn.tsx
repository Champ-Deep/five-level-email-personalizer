import { useState } from "react";

export function CopyBtn({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setDone(true);
        setTimeout(() => setDone(false), 2000);
      }}
      className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold tracking-wider transition"
      style={{
        background: done ? "rgba(34,197,94,.12)" : "rgba(0,0,0,.04)",
        borderColor: done ? "rgba(34,197,94,.4)" : "var(--brand-rule)",
        color: done ? "#16a34a" : "var(--brand-muted)",
      }}
    >
      {done ? "COPIED" : label.toUpperCase()}
    </button>
  );
}
