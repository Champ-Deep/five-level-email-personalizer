import { useEffect, useRef, useState } from "react";
import Papa from "papaparse";
import { Link, useNavigate } from "react-router-dom";

import { BrandHeader } from "@/components/BrandHeader";
import { api, getToken, setToken, type BrandConfig, type PersonalizeBody, type PersonalizeResponse } from "@/lib/api";
import { applyBrandTokens } from "@/lib/brandTokens";

interface CsvRow {
  name: string;
  title: string;
  domain: string;
  linkedin?: string;
}

export function InternalAppRoute() {
  const navigate = useNavigate();
  const [brands, setBrands] = useState<string[]>([]);
  const [activeBrand, setActiveBrand] = useState<BrandConfig | null>(null);
  const [rows, setRows] = useState<CsvRow[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Awaited<ReturnType<typeof api.getJob>> | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!getToken()) {
      navigate("/login");
      return;
    }
    api.listBrands().then(slugs => {
      setBrands(slugs);
      if (slugs.length > 0) {
        api.getBrand(slugs[0]).then(b => { setActiveBrand(b); applyBrandTokens(b); });
      }
    }).catch(e => setErr(String(e)));
  }, [navigate]);

  const pickBrand = async (slug: string) => {
    const b = await api.getBrand(slug);
    setActiveBrand(b);
    applyBrandTokens(b);
  };

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
          name: r.name,
          title: r.title,
          domain: r.domain,
          ...(r.linkedin ? { linkedin: r.linkedin } : {}),
        })),
        sender: {
          name: "Team",
          company: activeBrand.sender_default.company,
          offer: activeBrand.sender_default.offer,
        },
        levels: [1, 2, 3, 4, 5],
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
    const lines: string[] = ["prospect,level,subject,body,anchor_signal,warnings"];
    Object.values(job.results).forEach((r) => {
      if ("error" in r) return;
      const v = r as PersonalizeResponse;
      Object.entries(v.emails).forEach(([lvl, draft]) => {
        const subject = (draft.subject || "").replace(/"/g, '""');
        const body = (draft.body || "").replace(/"/g, '""').replace(/\n/g, "\\n");
        const anchor = (draft.anchor_signal || "").replace(/"/g, '""');
        const warns = (draft.warnings || []).join(" | ").replace(/"/g, '""');
        lines.push(`"${v.brief.name}",${lvl},"${subject}","${body}","${anchor}","${warns}"`);
      });
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `personalize-${jobId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!activeBrand) return <div className="p-10 text-sm">Loading…</div>;

  return (
    <div className="min-h-screen" style={{ background: "var(--brand-bg)" }}>
      <BrandHeader
        brand={activeBrand}
        rightSlot={
          <div className="flex items-center gap-2">
            <select
              value={activeBrand.slug}
              onChange={e => pickBrand(e.target.value)}
              className="rounded-md border px-2 py-1.5 text-xs"
              style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)", color: "var(--brand-ink)" }}
            >
              {brands.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <Link to={`/lead-magnet/${activeBrand.slug}`} className="text-xs" style={{ color: "var(--brand-muted)" }}>
              View lead-magnet
            </Link>
            <button
              onClick={() => { setToken(null); navigate("/login"); }}
              className="text-xs"
              style={{ color: "var(--brand-muted)" }}
            >
              Sign out
            </button>
          </div>
        }
      />

      <main className="mx-auto max-w-4xl px-6 pb-24 pt-10">
        <h1 className="mb-2 font-brand-display text-3xl font-extrabold" style={{ color: "var(--brand-ink)" }}>
          Internal · Batch personalize
        </h1>
        <p className="mb-8 text-sm" style={{ color: "var(--brand-muted)" }}>
          Upload a CSV with columns <code>name, title, domain, linkedin</code>. The system runs research +
          all 5 levels per row and lets you export the result.
        </p>

        <section className="rounded-2xl border p-6" style={{ background: "var(--brand-bg)", borderColor: "var(--brand-rule)" }}>
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              onChange={onFile}
              className="text-sm"
            />
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
                Job {jobId}
              </h2>
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
      </main>
    </div>
  );
}
