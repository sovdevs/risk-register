# Risk Register — Spec

## Purpose
Weekend Django project: an enterprise-style risk register (likelihood × impact
scoring, mitigation tracking, audit trail, heatmap dashboard) — the kind of
tool a GRC vendor like Athereon builds. Built in short, runnable feature
cycles rather than all at once, to re-familiarize with Django along the way.

## Tech stack
- Python 3.13, Django 5.x
- `uv` for env/dependency management
- SQLite for local dev (swapping to Postgres later is a one-line
  `DATABASES` change — not needed for a local demo)
- `django-simple-history` for audit trail (added in cycle 7)
- Plain HTML/CSS grid for the heatmap (cycle 4, done) — color-banded risk
  matrices are conventionally a grid, not a chart; Chart.js via CDN is
  still the plan for the trend line chart (cycle 6)
- Faker + a custom management command for synthetic demo data (added in
  cycle 2, content moved to `risks/seed_data.yaml` in cycle 3)
- Django admin as the primary data-entry UI — no separate CRUD UI needed
- DRF only if a cycle turns out to need a JSON endpoint for a chart;
  not assumed upfront

## Data model
- **Department** — name
- **RiskCategory** — name, description (e.g. Operational, Cyber, Financial,
  Legal, Third-Party, Compliance)
- **Risk**
  - title, description
  - category (FK RiskCategory), department (FK Department)
  - owner (FK auth.User)
  - status: identified / assessing / mitigating / monitoring / closed
  - date_identified, next_review_date
- **RiskAssessment** (historical — many per Risk, this is what drives trend
  charts)
  - risk (FK), kind: inherent / residual (post-mitigation)
  - likelihood (1-5), impact (1-5) → `score` computed property
    (likelihood × impact)
  - assessed_by (FK User), assessed_date, notes
- **Mitigation**
  - risk (FK)
  - treatment_type: accept / mitigate / transfer / avoid
  - action_plan (text), owner (FK User), due_date
  - status: not_started / in_progress / complete (overdue derived from
    due_date + status)
- History: `django-simple-history` on Risk, RiskAssessment, Mitigation

## Feature cycles
1. **Scaffold** (done) — project + `risks` app, Risk/RiskCategory/Department
   models, admin registration, migrations. Runnable: CRUD via `/admin/`.
2. **RiskAssessment** (done) — likelihood/impact/score, inline in Risk
   admin. `manage.py seed_demo` introduced here (originally planned as its
   own later cycle, front-loaded so there was data to look at early).
3. **Mitigation** (done) — treatment type, action plan, residual assessment
   linkage. Seed content (departments/categories/risk titles/descriptions/
   action plans) extracted out of the command into `risks/seed_data.yaml`,
   with real hand-written descriptions instead of Faker text.

   — **Milestone 1: basic static admin app.** Full data model, all
   relationships, realistic seeded content — but everything so far is just
   Django admin's auto-generated CRUD. Nothing yet is bespoke to "risk
   register" as opposed to any other set of models. Cycles 4+ are what
   turn this into an actual product.

4. **Heatmap dashboard** (done) — 5×5 likelihood × impact grid, risk count
   per cell, color-banded (Low/Medium/High/Critical). First custom
   view/template, not admin. Plotted from each risk's most recent
   assessment (residual once mitigated). Plain HTML/CSS grid rather than
   Chart.js — that's still the plan for the trend chart in cycle 6.
   (Moved up from its original slot after cycle 3 — the visible payoff
   outweighs sequencing purity; audit trail below is invisible
   infrastructure by comparison.)
5. **Filterable register view** — list page with status/category/
   department filters.
6. **Trend + overdue widgets** — aggregate risk score over time from
   assessment history; overdue mitigations list.
7. **Audit trail** — wire up `django-simple-history` on the core models.
8. **Polish** — README, `pyproject.toml` cleanup, light styling pass.

Each cycle ends in a state where `uv run python manage.py runserver` works
and the new feature is visible/checkable.

## Non-goals
No multi-tenant orgs, no auth beyond Django's built-in, no deployment
config — this is a local dev demo only.
