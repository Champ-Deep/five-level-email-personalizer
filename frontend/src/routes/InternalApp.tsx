import { useEffect, useMemo, useRef, useState } from "react";
import Papa from "papaparse";

import { InternalLayout } from "@/components/InternalLayout";
import { api, type BrandConfig, type IntegrationOut, type PersonalizeBody, type PersonalizeResponse, type SavedSender, type PushResult } from "@/lib/api";

interface CsvRow { name: string; title: string; domain: string; linkedin?: string }

interface RowResult {
  index: number;
  prospect: { name: string; title: string; domain: string };
  best?: {
    slot: string;
    model: string;
    subject: string;
    body: string;
    reply_likelihood: number | null;
    deliverability: number | null;
  };
  followup?: { subject: string; body: string } | null;
  linkedin?: { body: string; char_count: number } | null;
  error?: string;
}

export function InternalAppRoute() {
  const [activeBrand, setActiveBrand] = useState<BrandConfig | null>(null);
  const [senders, setSenders] = useState<SavedSender[]>([]);
  const [senderId, setSenderId] = useState<string>("");
  const [includeFollowup, setIncludeFollowup] = useState(false);
  const [includeLinkedin, setIncludeLinkedin] = useState(false);
  const [tonePreset, setTonePreset] = useState<string>("");
  const [rows, setRows] = useState<CsvRow[]>([]);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Awaited<ReturnType<typeof api.getJob>> | null>(null);
  const [pick, setPick] = useState<"auto" | "A" | "B" | "C">("auto");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationOut[]>([]);
  const [pushTargetId, setPushTargetId] = useState<string>("");
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState<PushResult | null>(null);
  const [regenerating, setRegenerating] = useState<Record<number, boolean>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listBrands().then(slugs => {
      if (slugs.length > 0) api.getBrand(slugs[0]).then(setActiveBrand);
    });
    api.listSenders().then(s => {
      setSenders(s);
      const def = s.find(x => x.is_default) || s[0];
      if (def) setSenderId(def.id);
    }).catch(() => { /* ok */ });
    api.listIntegrations().then(setIntegrations).catch(() => { /* ok */ });
  }, []);

  const selectedSender = useMemo(
    () => senders.find(s => s.id === senderId),
    [senders, senderId],
  );

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setErr(null);
    const name = f.name.toLowerCase();
    if (name.endsWith(".xlsx") || name.endsWith(".xlsm")) {
      setExcelFile(f);
      setRows([]); // CSV path cleared
      return;
    }
    // CSV path
    setExcelFile(null);
    Papa.parse(f, {
      header: true,
      skipEmptyLines: true,
      complete: (res) => {
        const parsed = (res.data as Record<string, string>[]).map(r => ({
          name: r.name || r.Name || "",
          title: r.title || r.Title || "",
          domain: r.domain || r.Domain || r.company_domain || "",
          linkedin: r.linkedin || r.LinkedIn || r.linkedin_url || "",
        })).filter(r => r.name && r.title && r.domain);
        setRows(parsed);
      },
      error: (e) => setErr(e.message),
    });
  };

  const totalRowCount = excelFile ? "Excel file ready (server-parsed on submit)" : `${rows.length} valid rows`;

  const run = async () => {
    if (!activeBrand) return;
    if (!selectedSender) {
      setErr("Pick a saved sender (Saved senders tab) or create one.");
      return;
    }
    if (!excelFile && rows.length === 0) {
      setErr("Upload a CSV or .xlsx with at least one prospect.");
      return;
    }
    setBusy(true);
    setErr(null);
    setJobId(null);
    setJob(null);

    try {
      if (excelFile) {
        const r = await api.batchExcel(excelFile, {
          name: selectedSender.name,
          company: selectedSender.company,
          offer: selectedSender.offer,
        }, {
          brand: activeBrand.slug,
          include_followup: includeFollowup,
          include_linkedin: includeLinkedin,
          tone_preset: tonePreset || undefined,
        });
        setJobId(r.job_id);
      } else {
        const body = {
          prospects: rows.map(r => ({
            name: r.name, title: r.title, domain: r.domain,
            ...(r.linkedin ? { linkedin: r.linkedin } : {}),
          })),
          sender: {
            name: selectedSender.name,
            company: selectedSender.company,
            offer: selectedSender.offer,
          },
          levels: [5],
          include_followup: includeFollowup,
          include_linkedin: includeLinkedin,
          ...(tonePreset ? { tone_preset: tonePreset } : {}),
        } as PersonalizeBody & { prospects: PersonalizeBody["prospect"][]; include_followup: boolean };
        const { job_id } = await api.batch(body, activeBrand.slug);
        setJobId(job_id);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  // Poll for job state until done.
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const j = await api.getJob(jobId);
        if (cancelled) return;
        setJob(j);
        if (j.status === "completed" || j.status === "completed_with_failures") return;
        setTimeout(tick, 2500);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    };
    tick();
    return () => { cancelled = true; };
  }, [jobId]);

  // Build per-row preview from the latest job state.
  const rowResults = useMemo<RowResult[]>(() => {
    if (!job) return [];
    return Object.entries(job.results).map(([idxStr, r]) => {
      const idx = Number(idxStr);
      if ("error" in r) {
        return { index: idx, prospect: { name: "—", title: "—", domain: "—" }, error: r.error };
      }
      const v = r as PersonalizeResponse;
      const variations = v.variations || [];
      const sorted = [...variations].sort((a, b) => {
        const sa = (a.email.scores?.reply_likelihood.score || 0);
        const sb = (b.email.scores?.reply_likelihood.score || 0);
        return sb - sa;
      });
      const chosen = pick === "auto" ? sorted[0] : (variations.find(x => x.slot === pick) || sorted[0]);
      if (!chosen) {
        return { index: idx, prospect: { name: v.brief?.name || "—", title: v.brief?.title || "—", domain: "—" } };
      }
      const e = chosen.email;
      return {
        index: idx,
        prospect: { name: v.brief.name, title: v.brief.title, domain: v.brief.company },
        best: {
          slot: chosen.slot,
          model: chosen.model,
          subject: e.subject,
          body: e.body,
          reply_likelihood: e.scores?.reply_likelihood.score ?? null,
          deliverability: e.scores?.deliverability.score ?? null,
        },
        followup: chosen.followup ? { subject: chosen.followup.subject, body: chosen.followup.body } : null,
        linkedin: chosen.linkedin ? { body: chosen.linkedin.body, char_count: chosen.linkedin.char_count } : null,
      };
    }).sort((a, b) => a.index - b.index);
  }, [job, pick]);

  const exportExcel = async () => {
    if (!jobId) return;
    const { blob, filename } = await api.exportJob(jobId, { format: "xlsx", pick });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const exportCsv = async () => {
    if (!jobId) return;
    const { blob, filename } = await api.exportJob(jobId, { format: "csv", pick });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const regenerateRow = async (index: number) => {
    if (!jobId) return;
    setRegenerating(r => ({ ...r, [index]: true }));
    setErr(null);
    try {
      await api.regenerateRow(jobId, index, {
        include_followup: includeFollowup,
        include_linkedin: includeLinkedin,
        tone_preset: tonePreset || undefined,
      });
      // Refresh job state so the row picks up the new variations.
      const j = await api.getJob(jobId);
      setJob(j);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRegenerating(r => ({ ...r, [index]: false }));
    }
  };

  const pushToIntegration = async () => {
    if (!jobId || !pushTargetId) return;
    setPushing(true);
    setPushResult(null);
    setErr(null);
    try {
      const r = await api.pushJobToIntegration(jobId, pushTargetId, pick);
      setPushResult(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPushing(false);
    }
  };

  if (!activeBrand) return <InternalLayout title="Batch personalize"><div>Loading…</div></InternalLayout>;

  const inputClass = "rounded-lg border px-3 py-2 text-sm outline-none";
  const inputStyle = { background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" };

  return (
    <InternalLayout
      title="Batch personalize"
      subtitle="Upload an Excel or CSV of prospects, pick a saved sender, and the system writes personalized cold emails (+ optional follow-ups) for every row."
    >
      <section className="mb-6 rounded-2xl border p-6 space-y-4" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
              Sender preset
            </label>
            <select
              value={senderId} onChange={e => setSenderId(e.target.value)}
              className={`${inputClass} w-full`} style={inputStyle}
            >
              <option value="">{senders.length === 0 ? "No saved senders yet — create one in Saved senders" : "Pick a sender…"}</option>
              {senders.map(s => (
                <option key={s.id} value={s.id}>
                  {s.label} {s.is_default ? "(default)" : ""}
                </option>
              ))}
            </select>
            {selectedSender && (
              <p className="mt-1 text-[11px]" style={{ color: "var(--brand-muted)" }}>
                {selectedSender.name} · {selectedSender.company}
              </p>
            )}
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
              Tone preset (optional)
            </label>
            <select
              value={tonePreset} onChange={e => setTonePreset(e.target.value)}
              className={`${inputClass} w-full`} style={inputStyle}
            >
              <option value="">Brand voice only</option>
              <option value="casual">Casual</option>
              <option value="formal">Formal</option>
              <option value="founder">Founder</option>
              <option value="friendly">Friendly</option>
              <option value="concise">Concise</option>
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={fileRef} type="file" accept=".csv,.xlsx,.xlsm"
            onChange={onFile} className="text-sm"
          />
          <span className="text-sm" style={{ color: "var(--brand-muted)" }}>{totalRowCount}</span>
          <span className="flex-1" />
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--brand-ink)" }}>
            <input
              type="checkbox" checked={includeFollowup}
              onChange={e => setIncludeFollowup(e.target.checked)}
            />
            Include follow-up email
          </label>
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--brand-ink)" }}>
            <input
              type="checkbox" checked={includeLinkedin}
              onChange={e => setIncludeLinkedin(e.target.checked)}
            />
            Include LinkedIn DM
          </label>
          <button
            onClick={run}
            disabled={busy || (!excelFile && rows.length === 0) || !selectedSender}
            className="rounded-lg px-5 py-2.5 text-sm font-bold disabled:opacity-50"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            {busy ? "Submitting…" : `Run on ${activeBrand.name}`}
          </button>
        </div>

        <p className="text-[11px]" style={{ color: "var(--brand-muted)" }}>
          Accepted columns: <code>name</code>, <code>title</code>, <code>domain</code> (required) +
          <code> linkedin</code>, <code>email</code> (optional). Case- and space-insensitive.
        </p>
      </section>

      {err && (
        <div className="mb-4 rounded-md border px-4 py-3 text-sm" style={{ borderColor: "#fca5a5", color: "#b91c1c", background: "#fef2f2" }}>
          {err}
        </div>
      )}

      {job && (
        <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <h2 className="text-sm font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
              Job {jobId?.slice(0, 8)}
            </h2>
            <span className="flex-1" />
            <div className="flex items-center gap-2 text-xs" style={{ color: "var(--brand-muted)" }}>
              <span>Pick variation:</span>
              {(["auto", "A", "B", "C"] as const).map(p => (
                <button
                  key={p} onClick={() => setPick(p)}
                  className="rounded-md border px-2 py-1 text-xs font-semibold"
                  style={{
                    background: pick === p ? "var(--brand-accent)" : "transparent",
                    color: pick === p ? "var(--brand-bg)" : "var(--brand-muted)",
                    borderColor: pick === p ? "var(--brand-accent)" : "var(--brand-rule)",
                  }}
                >
                  {p === "auto" ? "Best of 3" : `Slot ${p}`}
                </button>
              ))}
            </div>
            <button
              onClick={exportExcel} disabled={job.done === 0}
              className="rounded-md px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
              style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
            >
              Download Excel
            </button>
            <button
              onClick={exportCsv} disabled={job.done === 0}
              className="rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
              style={{ borderColor: "var(--brand-rule)", color: "var(--brand-accent)" }}
            >
              CSV
            </button>
          </div>

          <div className="mb-2 text-sm" style={{ color: "var(--brand-ink)" }}>
            Status: <strong>{job.status}</strong> · {job.done}/{job.total} done
            {job.failed_count > 0 && <span style={{ color: "#dc2626" }}> · {job.failed_count} failed</span>}
          </div>
          <div className="h-2 w-full overflow-hidden rounded" style={{ background: "var(--brand-rule)" }}>
            <div
              className="h-full transition-all"
              style={{
                width: `${job.total > 0 ? Math.round((job.done / job.total) * 100) : 0}%`,
                background: "var(--brand-accent)",
              }}
            />
          </div>

          {(job.status === "completed" || job.status === "completed_with_failures") && (
            <div className="mt-4 rounded-lg border p-4" style={{ background: "var(--brand-accent-soft)", borderColor: "var(--brand-rule)" }}>
              <div className="mb-2 text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--brand-accent)" }}>
                Push to destination
              </div>
              {integrations.length === 0 ? (
                <p className="text-xs" style={{ color: "var(--brand-muted)" }}>
                  No integrations configured. Set one up in the <strong>Integrations</strong> tab to push directly into Instantly, ChampMail, or ChampIQ.
                </p>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    value={pushTargetId} onChange={e => setPushTargetId(e.target.value)}
                    className="rounded-lg border px-3 py-1.5 text-sm outline-none"
                    style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
                  >
                    <option value="">Choose destination…</option>
                    {integrations.map(i => (
                      <option key={i.id} value={i.id}>
                        {i.label} ({i.provider})
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={pushToIntegration}
                    disabled={pushing || !pushTargetId}
                    className="rounded-md px-3 py-1.5 text-xs font-bold disabled:opacity-50"
                    style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
                  >
                    {pushing ? "Pushing…" : `Push ${pick === "auto" ? "best of 3" : `slot ${pick}`}`}
                  </button>
                  {pushResult && (
                    <span className="text-xs font-semibold" style={{ color: pushResult.ok ? "#15803d" : "#dc2626" }}>
                      {pushResult.ok
                        ? `✓ ${pushResult.pushed} pushed to ${pushResult.provider}`
                        : `✗ ${pushResult.pushed} pushed, ${pushResult.failed} failed`}
                    </span>
                  )}
                </div>
              )}
              {pushResult && pushResult.errors.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-[11px]" style={{ color: "var(--brand-muted)" }}>
                    {pushResult.errors.length} error{pushResult.errors.length === 1 ? "" : "s"}
                  </summary>
                  <ul className="mt-1 space-y-0.5 text-[11px] font-mono" style={{ color: "#b91c1c" }}>
                    {pushResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </details>
              )}
            </div>
          )}

          {rowResults.length > 0 && (
            <div className="mt-5 max-h-[60vh] overflow-auto rounded-lg border" style={{ borderColor: "var(--brand-rule)" }}>
              <table className="w-full text-sm">
                <thead style={{ background: "var(--brand-accent-soft)" }}>
                  <tr>
                    <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-accent)" }}>Prospect</th>
                    <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-accent)" }}>Subject</th>
                    <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-accent)" }}>Reply</th>
                    <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-accent)" }}>Deliv.</th>
                    <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-accent)" }}>Model</th>
                    <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--brand-accent)" }}></th>
                  </tr>
                </thead>
                <tbody>
                  {rowResults.map(r => (
                    <tr key={r.index} className="border-t" style={{ borderColor: "var(--brand-rule)" }}>
                      <td className="px-3 py-2">
                        <div className="font-semibold" style={{ color: "var(--brand-ink)" }}>{r.prospect.name}</div>
                        <div className="text-[11px]" style={{ color: "var(--brand-muted)" }}>{r.prospect.title} · {r.prospect.domain}</div>
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--brand-ink)" }}>
                        {r.error ? (
                          <span style={{ color: "#dc2626" }}>{r.error}</span>
                        ) : r.best ? (
                          <>
                            <div className="font-semibold">{r.best.subject}</div>
                            {r.followup && <div className="mt-0.5 text-[11px]" style={{ color: "var(--brand-muted)" }}>+ Follow-up: {r.followup.subject}</div>}
                            {r.linkedin && (
                              <div className="mt-0.5 text-[11px]" style={{ color: "var(--brand-muted)" }}>
                                + LinkedIn DM ({r.linkedin.char_count} chars)
                              </div>
                            )}
                          </>
                        ) : (
                          <em style={{ color: "var(--brand-muted)" }}>Pending…</em>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-[11px]" style={{ color: "var(--brand-ink)" }}>
                        {r.best?.reply_likelihood ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-[11px]" style={{ color: "var(--brand-ink)" }}>
                        {r.best?.deliverability ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-[11px]" style={{ color: "var(--brand-muted)" }}>
                        {r.best ? `${r.best.slot} · ${r.best.model.split("/").pop()}` : "—"}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {r.best && (
                          <button
                            onClick={() => regenerateRow(r.index)}
                            disabled={regenerating[r.index]}
                            className="rounded-md border px-2 py-1 text-[11px] font-semibold disabled:opacity-50"
                            style={{ borderColor: "var(--brand-rule)", color: "var(--brand-accent)" }}
                            title="Regenerate this row only"
                          >
                            {regenerating[r.index] ? "…" : "↻ Regenerate"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </InternalLayout>
  );
}
