import { FormEvent } from "react";
import type { PersonalizeBody } from "@/lib/api";

interface Props {
  prospect: PersonalizeBody["prospect"];
  sender: NonNullable<PersonalizeBody["sender"]>;
  setProspect: (p: PersonalizeBody["prospect"]) => void;
  setSender: (s: NonNullable<PersonalizeBody["sender"]>) => void;
  onSubmit: () => void;
  running: boolean;
  brandName: string;
}

const inputClass =
  "w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none transition focus:ring-2";

const labelClass = "mb-1.5 block text-[11px] font-semibold uppercase tracking-wider";

export function PersonalizerForm({ prospect, sender, setProspect, setSender, onSubmit, running, brandName }: Props) {
  const valid = prospect.name.trim() && prospect.title.trim() && prospect.domain.trim();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!valid || running) return;
    onSubmit();
  };

  const inputStyle = {
    background: "var(--brand-bg)",
    borderColor: "var(--brand-rule)",
    color: "var(--brand-ink)",
  };
  const labelStyle = { color: "var(--brand-muted)" };

  return (
    <form
      onSubmit={submit}
      className="space-y-5"
      style={{ animation: "fadeUp .3s ease" }}
    >
      <fieldset
        className="rounded-2xl border p-6"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <legend
          className="px-1 text-[10px] font-bold uppercase tracking-[0.15em]"
          style={labelStyle}
        >
          Prospect Details
        </legend>

        <div className="mt-2 grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass} style={labelStyle}>Full Name <span style={{ color: "var(--brand-accent)" }}>*</span></label>
            <input
              className={inputClass}
              style={inputStyle}
              placeholder="e.g. Priya Sharma"
              value={prospect.name}
              onChange={e => setProspect({ ...prospect, name: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass} style={labelStyle}>Job Title / Persona <span style={{ color: "var(--brand-accent)" }}>*</span></label>
            <input
              className={inputClass}
              style={inputStyle}
              placeholder="e.g. VP of Sales, CMO"
              value={prospect.title}
              onChange={e => setProspect({ ...prospect, title: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass} style={labelStyle}>Company Domain <span style={{ color: "var(--brand-accent)" }}>*</span></label>
            <input
              className={inputClass}
              style={inputStyle}
              placeholder="e.g. acmecorp.com"
              value={prospect.domain}
              onChange={e => setProspect({ ...prospect, domain: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass} style={labelStyle}>LinkedIn URL</label>
            <input
              className={inputClass}
              style={inputStyle}
              placeholder="https://linkedin.com/in/…"
              value={prospect.linkedin || ""}
              onChange={e => setProspect({ ...prospect, linkedin: e.target.value })}
            />
          </div>
        </div>
      </fieldset>

      <fieldset
        className="rounded-2xl border p-6"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <legend className="px-1 text-[10px] font-bold uppercase tracking-[0.15em]" style={labelStyle}>
          Sender Context · {brandName}
        </legend>

        <div className="mt-2 grid gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass} style={labelStyle}>Your Name</label>
            <input
              className={inputClass}
              style={inputStyle}
              value={sender.name}
              onChange={e => setSender({ ...sender, name: e.target.value })}
            />
          </div>
          <div>
            <label className={labelClass} style={labelStyle}>Your Company</label>
            <input
              className={inputClass}
              style={inputStyle}
              value={sender.company}
              onChange={e => setSender({ ...sender, company: e.target.value })}
            />
          </div>
        </div>
        <div className="mt-4">
          <label className={labelClass} style={labelStyle}>What You're Offering (1–2 sentences)</label>
          <textarea
            rows={2}
            className={inputClass}
            style={{ ...inputStyle, resize: "vertical" }}
            value={sender.offer}
            onChange={e => setSender({ ...sender, offer: e.target.value })}
          />
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={!valid || running}
        className="flex w-full items-center justify-center gap-2 rounded-xl px-7 py-4 text-base font-bold transition disabled:cursor-not-allowed disabled:opacity-50"
        style={{
          background: valid && !running ? "var(--brand-accent)" : "var(--brand-rule)",
          color: valid && !running ? "var(--brand-bg)" : "var(--brand-muted)",
        }}
      >
        {running ? "Researching & generating…" : "Research prospect & generate 5 emails"}
      </button>

      {!valid && (
        <p className="text-center text-xs" style={{ color: "var(--brand-muted)" }}>
          Fill in Name, Title and Company Domain to continue
        </p>
      )}
    </form>
  );
}
