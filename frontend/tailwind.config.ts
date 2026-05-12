import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          accent: "var(--brand-accent)",
          "accent-soft": "var(--brand-accent-soft)",
          ink: "var(--brand-ink)",
          muted: "var(--brand-muted)",
          rule: "var(--brand-rule)",
          bg: "var(--brand-bg)",
        },
      },
      fontFamily: {
        brand: ["var(--brand-font-primary)", "system-ui", "sans-serif"],
        "brand-display": ["var(--brand-font-secondary)", "var(--brand-font-primary)", "serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
