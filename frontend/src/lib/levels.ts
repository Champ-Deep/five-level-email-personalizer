export interface LevelMeta {
  id: number;
  tag: string;
  label: string;
  premise: string;
}

export const LEVELS: LevelMeta[] = [
  { id: 1, tag: "INDUSTRY",   label: "Industry Signal",     premise: "Something is true about your industry." },
  { id: 2, tag: "COMPANY",    label: "Company Signal",      premise: "Something is happening at your company." },
  { id: 3, tag: "ROLE",       label: "Role Signal",         premise: "Pressures specific to your seat." },
  { id: 4, tag: "INDIVIDUAL", label: "Individual Signal",   premise: "Something specific to you." },
  { id: 5, tag: "HYPER",      label: "Hyper-Personalization", premise: "Industry × Company × Role × You, fused." },
];

export function levelMeta(id: number): LevelMeta {
  return LEVELS.find(l => l.id === id) ?? LEVELS[0];
}
