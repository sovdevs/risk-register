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
5. **Filterable register view** (done) — list page at `/register/` with
   status/category/department filters as GET params. Shares the heatmap's
   "most recent assessment" logic (extracted to
   `_latest_assessments_by_risk()`) so current scores agree between views.
   Row titles link to the admin change page — no custom detail view yet.
6. **Trend + overdue widgets** (done) — added to the heatmap page (`/`)
   rather than a new page. Trend chart (Chart.js, first real use of it)
   reconstructs average current score per month across the portfolio's
   assessment history, so completed mitigations pull the line down after
   the fact rather than only affecting a final snapshot. Overdue widget
   lists `Mitigation`s past `due_date` and not `complete`.
7. **Audit trail** (done) — `django-simple-history` on Risk, RiskAssessment,
   Mitigation. `HistoryRequestMiddleware` captures which user made a change
   via the web. `SimpleHistoryAdmin` gives Risk a working History page.
   Existing seeded rows backfilled once via `populate_history --auto`;
   new saves (including future reseeds) track automatically from here on.
8. **Polish** (done) — `pyproject.toml` description, shared CSS
   (`.band-*`, `.row-link`) deduplicated into `base.html`, README
   reorganized with an overview instead of requiring all 8 cycles read
   to understand the app.

   — **Milestone 2: app complete.** Full roadmap shipped. Next: the
   second project (`controlmappingcoverage`), and scoping where an AI
   feature could add real value on top of either app.

Each cycle ends in a state where `uv run python manage.py runserver` works
and the new feature is visible/checkable.

## Phase 2: AI features
BYOK (bring your own key) OpenAI integration. Dataset is small enough
(dozens of rows) that every feature just passes relevant rows as context
directly — no vector DB/embeddings needed.

9. **AI settings** (done) — `AISettings` singleton model (api_key, model
   name as free text — no hardcoded model ID). `/ai/settings/` page,
   password input, masked on redisplay (`••••••••1234`), blank submit
   keeps the existing key. `risks/ai.py` wraps the OpenAI client behind
   `generate_text()`, raising `AIError` for "no key" / "request failed".
   Not in Django admin — admin doesn't mask CharFields.
10. **AI portfolio insight** (done) — "Generate Insight" button on the
    heatmap page (`/`), POST-triggered. Builds a grounded text summary
    (top 5 risks by score, trend first-vs-last-month, up to 5 overdue
    mitigations) and asks for a 3-4 sentence executive summary. Read-only.
11. **AI draft-assist** (done) — custom "New Risk" page (`/new/`, not
    admin). "Draft with AI" (plain fetch) calls `/ai/draft/`
    (`generate_json`, structured OpenAI response), fills form fields
    client-side, nothing saved until "Save Risk". Server-side validation
    clamps likelihood/impact to 1-5 and checks treatment_type against
    real choices regardless of what the model returns. Saving creates
    Risk + optional inherent RiskAssessment + optional Mitigation
    (90-day default due date), redirects to the admin change page.
12. **AI Q&A** — a chat-style page answering natural-language questions
    ("what are our top open Cyber risks?") against the current register,
    passing matching rows as context and instructing the model to answer
    only from provided data.

## Non-goals
No multi-tenant orgs, no auth beyond Django's built-in, no deployment
config — this is a local dev demo only. No vector search/embeddings — not
needed at this data volume.
