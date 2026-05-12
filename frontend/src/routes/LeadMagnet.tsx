import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { BrandHeader } from "@/components/BrandHeader";
import { BriefPanel } from "@/components/BriefPanel";
import { EmailCard } from "@/components/EmailCard";
import { LeadGate } from "@/components/LeadGate";
import { LevelPills } from "@/components/LevelPills";
import { PersonalizerForm } from "@/components/PersonalizerForm";
import { api, getToken, type BrandConfig, type PersonalizeBody, type PersonalizeResponse } from "@/lib/api";
import { applyBrandTokens } from "@/lib/brandTokens";
import { LEVELS } from "@/lib/levels";

export function LeadMagnetRoute() {
  const params = useParams<{ brand: string }>();
  const slug = params.brand ?? "lakeb2b";

  const [brand, setBrand] = useState<BrandConfig | null>(null);
  const [brandErr, setBrandErr] = useState<string | null>(null);

  const [prospect, setProspect] = useState<PersonalizeBody["prospect"]>({
    name: "", title: "", domain: "", linkedin: "",
  });
  const [sender, setSender] = useState<NonNullable<PersonalizeBody["sender"]>>({
    name: "", company: "", offer: "",
  });
  const [response, setResponse] = useState<PersonalizeResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [gateOpen, setGateOpen] = useState(false);
  const [runsThisSession, setRunsThisSession] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.getBrand(slug).then(b => {
      if (cancelled) return;
      setBrand(b);
      applyBrandTokens(b);
      setSender(s => s.company ? s : ({
        name: s.name,
        company: b.sender_default.company,
        offer: b.sender_default.offer,
      }));
    }).catch(e => setBrandErr(String(e)));
    return () => { cancelled = true; };
  }, [slug]);

  const hasToken = !!getToken();
  const canRunMore = hasToken || runsThisSession === 0;

  const onSubmit = useCallback(async () => {
    if (!brand) return;
    if (!canRunMore) {
      setGateOpen(true);
      return;
    }
    setRunning(true);
    setErr(null);
    setResponse(null);
    try {
      const body: PersonalizeBody = {
        prospect: {
          name: prospect.name,
          title: prospect.title,
          domain: prospect.domain,
          ...(prospect.linkedin ? { linkedin: prospect.linkedin } : {}),
        },
        sender: { name: sender.name || "—", company: sender.company, offer: sender.offer },
        levels: [1, 2, 3, 4, 5],
      };
      const result = await api.personalize(body, brand.slug);
      setResponse(result);
      setRunsThisSession(n => n + 1);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }, [brand, canRunMore, prospect, sender]);

  const levels = useMemo(() => LEVELS.map(l => l.id), []);

  if (brandErr) return <div className="p-10 text-sm">Failed to load brand: {brandErr}</div>;
  if (!brand) return <div className="p-10 text-sm">Loading…</div>;

  return (
    <div className="min-h-screen" style={{ background: "var(--brand-bg)" }}>
      <BrandHeader
        brand={brand}
        rightSlot={
          <Link
            to="/app"
            className="rounded-md border px-3 py-1.5 text-xs font-semibold"
            style={{ borderColor: "var(--brand-rule)", color: "var(--brand-muted)" }}
          >
            Internal app →
          </Link>
        }
      />

      <main className="mx-auto max-w-3xl px-6 pb-24 pt-10">
        <section className="mb-8 text-center">
          <h1
            className="font-brand-display text-4xl font-extrabold leading-tight md:text-5xl"
            style={{ color: "var(--brand-ink)", letterSpacing: "-0.02em" }}
          >
            5-Level Email Personalizer
          </h1>
          <p
            className="mx-auto mt-4 max-w-xl text-base leading-relaxed"
            style={{ color: "var(--brand-muted)" }}
          >
            Enter a prospect — AI researches them live and writes five emails, from broad industry signal to hyper-personal. {brand.tagline && <strong style={{ color: "var(--brand-accent)" }}> · {brand.tagline}</strong>}
          </p>
          <div className="mt-6"><LevelPills /></div>
        </section>

        {!response ? (
          <PersonalizerForm
            prospect={prospect}
            sender={sender}
            setProspect={setProspect}
            setSender={setSender}
            onSubmit={onSubmit}
            running={running}
            brandName={brand.name}
          />
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <button
                onClick={() => { setResponse(null); }}
                className="text-sm font-semibold"
                style={{ color: "var(--brand-accent)" }}
              >
                ← New prospect
              </button>
              <div className="text-xs" style={{ color: "var(--brand-muted)" }}>
                {hasToken ? "Unlocked · 20/day" : `Free tier · 1 run used`}
              </div>
            </div>
            <BriefPanel brief={response.brief} />
            <div className="space-y-3">
              {levels.map(lvl => (
                <EmailCard
                  key={lvl}
                  level={lvl}
                  email={response.emails[lvl] ?? null}
                  loading={false}
                  senderName={sender.name || brand.sender_default.name || brand.name}
                />
              ))}
            </div>
            {!hasToken && (
              <div
                className="mt-6 rounded-xl border px-5 py-5 text-center"
                style={{ background: "var(--brand-accent-soft)", borderColor: "var(--brand-rule)" }}
              >
                <div className="mb-2 text-sm font-bold" style={{ color: "var(--brand-ink)" }}>
                  Want more — and a CSV batch?
                </div>
                <button
                  onClick={() => setGateOpen(true)}
                  className="rounded-lg px-5 py-2.5 text-sm font-bold"
                  style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
                >
                  Unlock 20/day + cheat-sheet PDF
                </button>
              </div>
            )}
          </div>
        )}

        {err && (
          <div className="mt-4 rounded-md border px-4 py-3 text-sm" style={{ borderColor: "#fca5a5", color: "#b91c1c", background: "#fef2f2" }}>
            {err}
          </div>
        )}
      </main>

      {gateOpen && (
        <LeadGate
          brand={brand.slug}
          brandName={brand.name}
          onUnlocked={() => setGateOpen(false)}
          onClose={() => setGateOpen(false)}
        />
      )}
    </div>
  );
}
