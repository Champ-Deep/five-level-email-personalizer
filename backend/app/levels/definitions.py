from dataclasses import dataclass


@dataclass(frozen=True)
class LevelMeta:
    id: int
    tag: str
    label: str
    premise: str
    signal_source: str
    research_minutes: str
    best_for: str


LEVELS: tuple[LevelMeta, ...] = (
    LevelMeta(
        id=1,
        tag="INDUSTRY",
        label="Industry Signal",
        premise="I'm emailing you because something is true about your industry.",
        signal_source="Industry reports, regulation, macro trends",
        research_minutes="Zero per prospect",
        best_for="High-volume TOFU, broad segments",
    ),
    LevelMeta(
        id=2,
        tag="COMPANY",
        label="Company Signal",
        premise="I'm emailing you because something is happening at your company.",
        signal_source="Funding, hiring, launches, leadership changes",
        research_minutes="2–5 min per account",
        best_for="ABM, strategic accounts, trigger windows",
    ),
    LevelMeta(
        id=3,
        tag="ROLE",
        label="Role Signal",
        premise="I'm emailing you because of pressures specific to your seat.",
        signal_source="Title pain points, KPIs, cycle pressures",
        research_minutes="Zero per prospect, upfront persona work",
        best_for="Persona campaigns, timed cycles",
    ),
    LevelMeta(
        id=4,
        tag="INDIVIDUAL",
        label="Individual Signal",
        premise="I'm emailing you because of something specific to you.",
        signal_source="LinkedIn activity, posts, talks, career moves",
        research_minutes="5–15 min per prospect",
        best_for="Named accounts, executive outreach",
    ),
    LevelMeta(
        id=5,
        tag="HYPER",
        label="Hyper-Personalization",
        premise="I've synthesized industry, company, role, and individual signals into a hypothesis.",
        signal_source="All of the above, fused into a POV",
        research_minutes="15–30 min per prospect",
        best_for="Top 20 accounts per quarter, exec replies",
    ),
)


def level_meta(level_id: int) -> LevelMeta:
    for lvl in LEVELS:
        if lvl.id == level_id:
            return lvl
    raise ValueError(f"Unknown level id: {level_id}")
