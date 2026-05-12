import type { BrandConfig } from "./api";

export function applyBrandTokens(brand: BrandConfig) {
  const root = document.documentElement;
  const t = brand.tokens;
  root.style.setProperty("--brand-accent", t.brand_accent);
  root.style.setProperty("--brand-accent-soft", t.brand_accent_soft);
  root.style.setProperty("--brand-ink", t.brand_ink);
  root.style.setProperty("--brand-muted", t.brand_muted);
  root.style.setProperty("--brand-rule", t.brand_rule);
  root.style.setProperty("--brand-bg", t.brand_bg);
  root.style.setProperty("--brand-font-primary", `"${t.font_primary}", system-ui, sans-serif`);
  root.style.setProperty("--brand-font-secondary", `"${t.font_secondary}", "${t.font_primary}", serif`);

  if (t.font_google_url) {
    const existing = document.getElementById("brand-google-font") as HTMLLinkElement | null;
    if (existing) existing.href = t.font_google_url;
    else {
      const link = document.createElement("link");
      link.id = "brand-google-font";
      link.rel = "stylesheet";
      link.href = t.font_google_url;
      document.head.appendChild(link);
    }
  }

  document.title = `${brand.name} · 5-Level Email Personalizer`;
}
