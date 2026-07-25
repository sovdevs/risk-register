# Cycle 4 — Risk Heatmap

How the heatmap at `/` is generated: the data pipeline, the layout logic,
and why it's built as a plain grid instead of a chart.

## What it shows

A 5×5 matrix — likelihood (1–5) on the vertical axis, impact (1–5) on the
horizontal axis — with each cell showing how many risks currently sit at
that likelihood/impact combination, and the resulting score (likelihood ×
impact, 1–25) color-banded into Low/Medium/High/Critical.

## Which assessment counts as "current"

A `Risk` can have multiple `RiskAssessment` rows over time — an inherent
one when first assessed, and a residual one once its mitigation completes
(see [Cycle 3 in SPEC.md](SPEC.md)). The heatmap plots each risk by its
**most recent** assessment, not always the inherent one. That means a risk
whose mitigation has finished shows its reduced, post-treatment score — the
heatmap reflects where things stand today, not where they started.

## The pipeline (`risks/views.py`)

1. Pull every `RiskAssessment`, ordered by `risk_id`, then `-assessed_date`,
   then `-id` (the `-id` tiebreak matters when two assessments land on the
   same date, e.g. an inherent and residual assessment created in the same
   seed run).
2. Walk that list once and keep only the first assessment seen per
   `risk_id` — because of the ordering, "first seen" is "most recent."
   This is a plain Python dict (`latest_by_risk`), not a database
   aggregation — the row count here (dozens, not millions) makes an ORM
   window-function query unnecessary complexity for a weekend project.
3. Bucket those latest assessments by `(likelihood, impact)` into a `cells`
   dict, collecting the actual `Risk` objects in each bucket (not just a
   count) — the titles are what populate each cell's hover tooltip.
4. Build the `grid` the template renders: a list of rows for likelihood 5
   down to 1, each containing 5 cells for impact 1 through 5, each cell
   carrying its score, color band, risk count, and risk titles.
5. Score → band comes from fixed thresholds: 1–4 low, 5–9 medium, 10–15
   high, 16–25 critical — the same bands the legend at the bottom of the
   page shows.

## Rendering (`risks/templates/risks/heatmap.html`)

A plain HTML `<table>` styled with CSS custom properties (`--low`,
`--medium`, `--high`, `--critical`, themed for light/dark via
`prefers-color-scheme`), not a Chart.js chart. Deliberate choice: a
color-banded risk matrix is conventionally a *grid*, not a chart type —
real GRC tools render it exactly this way — so building it as a styled
table needed no extra dependency. Chart.js (already planned in the spec)
is reserved for the trend line chart in a later cycle, where a genuine
time-series chart is the right tool.

Each cell's `title` attribute lists the risk titles in that cell
(comma-joined), so hovering a cell shows what's actually in it — cheap
interactivity with no JavaScript.

## Files touched

- `risks/views.py` — the `heatmap` view and `_score_band` helper (new)
- `risks/urls.py` — new, maps `""` to the heatmap view under the `risks`
  namespace
- `config/urls.py` — now includes `risks.urls` at the root path
- `risks/templates/risks/base.html` — new, shared layout/nav/theming
- `risks/templates/risks/heatmap.html` — new, extends `base.html`

## Viewing it

`uv run python manage.py runserver 8088`, then visit
`http://127.0.0.1:8088/`. Re-run `manage.py seed_demo --flush` first if you
want fresh data to look at.
