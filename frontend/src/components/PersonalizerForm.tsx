import { FormEvent, useState } from "react";
import type { PersonalizeBody } from "@/lib/api";

interface Props {
  prospect: PersonalizeBody["prospect"];
  sender: NonNullable<PersonalizeBody["sender"]>;
  styleRules: string;
  tonePreset: string;
  setProspect: (p: PersonalizeBody["prospect"]) => void;
  setSender: (s: NonNullable<PersonalizeBody["sender"]>) => void;
  setStyleRules: (s: string) => void;
  setTonePreset: (s: string) => void;
  onSubmit: () => void;
  running: boolean;
  brandName: string;
}

const TONE_PRESETS: Array<{ id: string; label: string; hint: string }> = [
  { id: "",         label: "Default",   hint: "Brand voice only" },
  { id: "casual",   label: "Casual",    hint: "Like a former coworker" },
  { id: "formal",   label: "Formal",    hint: "Executive register" },
  { id: "founder",  label: "Founder",   hint: "Dry, founder-to-founder" },
  { id: "friendly", label: "Friendly",  hint: "Warm, peer-to-peer" },
  { id: "concise",  label: "Concise",   hint: "55-75 words, every word does work" },
];

const inputClass =
  "w-full rounded-lg border px-3.5 py-2.5 text-sm outline-none transition focus:ring-2";

const labelClass = "mb-1.5 block text-[11px] font-semibold uppercase tracking-wider";

const BAKED_IN_RULES = [
  "No em-dashes (—) or en-dashes (–) — use commas or periods",
  "No 'not X, but Y' / 'it's not just X, it's Y' constructions",
  "No AI-slop words: delve, leverage, navigate, landscape, tapestry, robust, holistic, seamless, supercharge, paradigm, transformative, cutting-edge…",
  "No opener clichés ('hope this finds you', 'I noticed that you', 'quick question')",
  "Plain prose, short sentences, concrete specifics over abstractions",
];

export function PersonalizerForm({
  prospect, sender, styleRules, tonePreset,
  setProspect, setSender, setStyleRules, setTonePreset,
  onSubmit, running, brandName,
}: Props) {
  const [styleOpen, setStyleOpen] = useState(false);
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
    <form onSubmit={submit} className="space-y-5" style={{ animation: "fadeUp .3s ease" }}>
      <fieldset
        className="rounded-2xl border p-6"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <legend className="px-1 text-[10px] font-bold uppercase tracking-[0.15em]" style={labelStyle}>
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

      <fieldset
        className="rounded-2xl border p-6"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <legend className="px-1 text-[10px] font-bold uppercase tracking-[0.15em]" style={labelStyle}>
          Tone preset
        </legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {TONE_PRESETS.map(p => {
            const active = tonePreset === p.id;
            return (
              <button
                key={p.id || "default"}
                type="button"
                onClick={() => setTonePreset(p.id)}
                className="inline-flex flex-col items-start gap-0.5 rounded-lg border px-3 py-2 text-left text-xs transition"
                style={{
                  background: active ? "var(--brand-accent)" : "var(--brand-bg)",
                  borderColor: active ? "var(--brand-accent)" : "var(--brand-rule)",
                  color: active ? "var(--brand-bg)" : "var(--brand-ink)",
                }}
              >
                <span className="font-bold">{p.label}</span>
                <span className="text-[10px]" style={{ opacity: 0.8 }}>{p.hint}</span>
              </button>
            );
          })}
        </div>
      </fieldset>

      <div
        className="rounded-2xl border"
        style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}
      >
        <button
          type="button"
          onClick={() => setStyleOpen(o => !o)}
          className="flex w-full items-center justify-between px-6 py-4 text-left"
        >
          <span className="text-[10px] font-bold uppercase tracking-[0.15em]" style={labelStyle}>
            Custom style rules {styleRules.trim() && <span style={{ color: "var(--brand-accent)" }}>· added</span>}
          </span>
          <span style={{ color: "var(--brand-muted)", transform: styleOpen ? "rotate(180deg)" : undefined, transition: "transform .2s" }}>▾</span>
        </button>
        {styleOpen && (
          <div className="border-t px-6 pb-5 pt-4" style={{ borderColor: "var(--brand-rule)" }}>
            <div className="mb-3">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider" style={labelStyle}>
                Built-in rules (always on)
              </div>
              <ul className="space-y-1 text-xs leading-relaxed" style={{ color: "var(--brand-ink)" }}>
                {BAKED_IN_RULES.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span style={{ color: "var(--brand-accent)" }}>✓</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <label className={labelClass} style={labelStyle}>
                Additional rules (your tone, banned words, voice notes…)
              </label>
              <textarea
                rows={4}
                className={inputClass}
                style={{ ...inputStyle, resize: "vertical", fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: 12 }}
                placeholder={`e.g.\n- No exclamation marks\n- Open with a question about their last LinkedIn post\n- Tone: dry, witty, founder-to-founder\n- Banned: "circle back", "touch base"`}
                value={styleRules}
                onChange={e => setStyleRules(e.target.value)}
              />
              <p className="mt-1.5 text-[11px]" style={{ color: "var(--brand-muted)" }}>
                These rules are appended to the brand voice and the built-in anti-slop rules. They don't replace them.
              </p>
            </div>
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={!valid || running}
        className="flex w-full items-center justify-center gap-2 rounded-xl px-7 py-4 text-base font-bold transition disabled:cursor-not-allowed disabled:opacity-50"
        style={{
          background: valid && !running ? "var(--brand-accent)" : "var(--brand-rule)",
          color: valid && !running ? "var(--brand-bg)" : "var(--brand-muted)",
        }}
      >
        {running ? "Researching & generating…" : "Research prospect & write the email"}
      </button>

      {!valid && (
        <p className="text-center text-xs" style={{ color: "var(--brand-muted)" }}>
          Fill in Name, Title and Company Domain to continue
        </p>
      )}
    </form>
  );
}
