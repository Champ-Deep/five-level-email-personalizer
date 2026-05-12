import { useEffect, useRef, useState } from "react";
import Papa from "papaparse";

import { InternalLayout } from "@/components/InternalLayout";
import { api, type BrandConfig, type PersonalizeBody, type PersonalizeResponse } from "@/lib/api";

interface CsvRow { name: string; title: string; domain: string; linkedin?: string }

export function InternalAppRoute() {
  const [activeBrand, setActiveBrand] = useState<BrandConfig | null>(null);
  const [rows, setRows] = useState<CsvRow[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Awaited<ReturnType<typeof api.getJob>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listBrands().then(slugs => {
      if (slugs.length > 0) api.getBrand(slugs[0]).then(setActiveBrand);
    });
  }, []);

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
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

  const runBatch = async () => {
    if (!activeBrand || rows.length === 0) return;
    setBusy(true);
    setErr(null);
    try {
      const body = {
        prospects: rows.map(r => ({
          name: r.name, title: r.title, domain: r.domain,
          ...(r.linkedin ? { linkedin: r.linkedin } : {}),
        })),
        sender: {
          name: "Team",
          company: activeBrand.sender_default.company,
          offer: activeBrand.sender_default.offer,
        },
        levels: [5],
      } as PersonalizeBody & { prospects: PersonalizeBody["prospect"][] };
      const { job_id } = await api.batch(body, activeBrand.slug);
      setJobId(job_id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

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

  const exportCsv = () => {
    if (!job) return;
    const lines: string[] = ["prospect,slot,model,subject,body,deliverability,reply_likelihood"];
    Object.values(job.results).forEach(r => {
      if ("error" in r) return;
      const v = r as PersonalizeResponse;
      (v.variations || []).forEach(variation => {
        const e = variation.email;
        const subj = (e.subject || "").replace(/"/g, '""');
        const body = (e.body || "").replace(/"/g, '""').replace(/\n/g, "\\n");
        const d = e.scores?.deliverability.score ?? "";
        const rl = e.scores?.reply_likelihood.score ?? "";
        lines.push(`"${v.brief.name}","${variation.slot}","${variation.model}","${subj}","${body}",${d},${rl}`);
      });
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `personalize-${jobId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!activeBrand) return <InternalLayout title="Batch personalize"><div>Loading…</div></InternalLayout>;

  return (
<<<<<<< HEAD
    <InternalLayout
      title="Batch personalize"
      subtitle={`Upload a CSV with columns "name, title, domain, linkedin". Three model variations per row.`}
    >
      <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
        <div className="flex flex-wrap items-center gap-3">
          <input ref={fileRef} type="file" accept=".csv" onChange={onFile} className="text-sm" />
          <span className="text-sm" style={{ color: "var(--brand-muted)" }}>
            {rows.length} valid rows loaded
          </span>
          <span className="flex-1" />
          <button
            onClick={runBatch}
            disabled={busy || rows.length === 0}
            className="rounded-lg px-5 py-2.5 text-sm font-bold disabled:opacity-50"
            style={{ background: "var(--brand-accent)", color: "var(--brand-bg)" }}
          >
            {busy ? "Submitting…" : `Run batch on ${activeBrand.name}`}
          </button>
        </div>
      </section>

      {err && (
        <div className="mt-4 rounded-md border px-4 py-3 text-sm" style={{ borderColor: "#fca5a5", color: "#b91c1c", background: "#fef2f2" }}>
          {err}
        </div>
      )}

      {job && (
        <section className="mt-6 rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider" style={{ color: "var(--brand-muted)" }}>
              Job {jobId?.slice(0, 8)}
            </h2>
=======
    <div className="min-h-screen" style={{ background: "var(--brand-bg)" }}>
      <BrandHeader
        brand={activeBrand}
        rightSlot={
          <div className="flex items-center gap-3">
            <Link to={`/lead-magnet/${activeBrand.slug}`} className="text-xs" style={{ color: "var(--brand-muted)" }}>
              View lead-magnet
            </Link>
>>>>>>> ee0bb66 (LakeB2B branded build · brand-locked to lakeb2b)
            <button
              onClick={exportCsv}
              disabled={job.done === 0}
              className="rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
              style={{ borderColor: "var(--brand-rule)", color: "var(--brand-accent)" }}
            >
              Export CSV
            </button>
          </div>
          <div className="text-sm" style={{ color: "var(--brand-ink)" }}>
            Status: <strong>{job.status}</strong> · {job.done}/{job.total} done
            {job.failed_count > 0 && <span style={{ color: "#dc2626" }}> · {job.failed_count} failed</span>}
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded" style={{ background: "var(--brand-rule)" }}>
            <div
              className="h-full transition-all"
              style={{
                width: `${job.total > 0 ? Math.round((job.done / job.total) * 100) : 0}%`,
                background: "var(--brand-accent)",
              }}
            />
          </div>
        </section>
      )}
    </InternalLayout>
  );
}
