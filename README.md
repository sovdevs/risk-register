# Risk Register

A place to track organizational risks — the kind of tool a compliance or
security team uses to answer "what could go wrong, how bad would it be,
and what are we doing about it." Built in short, runnable Django cycles;
see [SPEC.md](SPEC.md) for the full data model and roadmap, or the
cycle-by-cycle notes below for what shipped when and why.

**What it does:**

- **Log a risk** — title, description, category (Cyber, Financial, Legal
  & Regulatory, etc.), owning department, responsible owner, and a
  lifecycle status (identified → assessing → mitigating → monitoring →
  closed).
- **Score it** — likelihood (1–5) × impact (1–5) → a 1–25 score. Every
  risk gets an *inherent* score when first assessed, and a *residual*
  score once its mitigation completes, so you can see how much a
  treatment actually reduced the risk.
- **Plan a response** — treatment type (accept/mitigate/transfer/avoid),
  action plan, owner, due date.
- **See it at a glance** — the heatmap (`/`) plots every risk on a 5×5
  likelihood × impact grid, color-banded Low→Critical, using each risk's
  *current* (most recent) score. The same page has a trend chart of the
  portfolio's average score over time and a list of overdue mitigations.
- **Slice the list** — the register (`/register/`) is a filterable table
  by status/category/department, with each row's current score and a
  link into the full record.
- **Full audit trail** — every change to a risk, assessment, or
  mitigation is versioned (`django-simple-history`), with a "History"
  page in admin showing who changed what and when.
- **Data entry** — Django admin (`/admin/`) handles actual CRUD.

Comes seeded with 27 realistic risks across 7 categories (unpatched CVEs,
GDPR backlogs, vendor risk, budget overruns, etc.) — see `seed_demo`
below.

## Running it

```bash
uv run python manage.py createsuperuser
uv run python manage.py runserver 8088
```

Then visit http://127.0.0.1:8088/admin/ and log in.

To populate demo data (departments, categories, 8 fake owners — 4 German, 4
American names — 27 risks with an inherent likelihood/impact assessment
each):

```bash
uv run python manage.py seed_demo        # add demo data
uv run python manage.py seed_demo --flush # wipe seeded data and regenerate
```

Safe to re-run — existing rows are matched by name/title and skipped.
`--flush` only deletes seeded rows (and non-staff/non-superuser demo
owners) — your own `createsuperuser` login is never touched.

Titles/categories/departments stay English (GRC domain vocabulary); only
owner names are mixed-locale, reflecting a multinational org rather than a
localized build of the app.

All seeded content (departments, categories, risk titles/descriptions,
mitigation action plans) lives in [risks/seed_data.yaml](risks/seed_data.yaml),
not in the command itself — edit that file (or paste in LLM-generated text)
without touching `seed_demo.py`.

## Cycle 1 (done)

`Department`, `RiskCategory`, `Risk` models + admin CRUD.

## Cycle 2 (done)

`RiskAssessment` model (likelihood/impact, computed score, inherent vs
residual), shown inline on the Risk admin page. `seed_demo` management
command added, generating curated risk titles with category-biased
inherent scores (Cyber/Third-Party skew higher) rather than uniform noise.

## Cycle 3 (done)

`Mitigation` model (treatment type, action plan, owner, due date, status,
computed `is_overdue`), shown inline on the Risk admin page. `seed_demo`
now gives any risk in `mitigating`/`monitoring`/`closed` status a
mitigation, and once that mitigation is complete, a residual
`RiskAssessment` showing the reduced score. Seed content (risk
descriptions, mitigation action plans) moved out of the command and into
`risks/seed_data.yaml` — real, hand-written text instead of Faker
gibberish.

**Milestone 1: basic static admin app.** Full data model and realistic
seeded content, but everything so far is just Django admin's
auto-generated CRUD — nothing yet is bespoke to a risk register as opposed
to any other set of models.

## Cycle 4 (done)

Risk heatmap dashboard at `/` — first custom view/template, not admin.
5×5 likelihood × impact grid (Low/Medium/High/Critical color bands),
each risk plotted by its *most recent* assessment (so a completed
mitigation's residual score shows instead of the original inherent one),
cell hover shows the risk titles in that cell. Plain HTML/CSS grid rather
than Chart.js — a color-banded matrix is how risk heatmaps actually look
in the GRC world, and it needed no extra dependency; Chart.js is still
the plan for the trend line chart in a later cycle. `risks/urls.py`
introduced, `config/urls.py` now includes it at the root path.

## Cycle 5 (done)

Filterable risk register at `/register/` — status/category/department
filters as GET params (bookmarkable/shareable URLs), each risk's row
showing its current score badge via the same "most recent assessment"
logic the heatmap uses (factored out into `_latest_assessments_by_risk()`
in `risks/views.py` so both views agree on what "current score" means).
Row titles link through to the admin change page for that risk — no
custom detail view yet, that wasn't in scope for this cycle.

## Cycle 6 (done)

Added a trend chart and an overdue-mitigations list to the heatmap page
(`/`) — turning it into the actual dashboard rather than adding a third
nav item. First real use of Chart.js (loaded via CDN, as originally
planned).

- **Risk Score Trend**: reconstructs the portfolio's average current
  score at the end of every month with at least one assessment (19
  months of data currently), not just a point-in-time snapshot — a
  risk's score contributes to every month from its first assessment
  onward, so a mitigation completing partway through actually pulls the
  average down in the months after. Logic in `_monthly_trend()`
  (`risks/views.py`).
- **Overdue Mitigations**: any `Mitigation` past its `due_date` and not
  `complete`, with days-overdue computed per row. Logic in
  `_overdue_mitigations()`.

## Cycle 7 (done)

Audit trail via `django-simple-history` on `Risk`, `RiskAssessment`, and
`Mitigation` — every save creates a timestamped snapshot, and edits made
through the web (admin) also record which user made them
(`HistoryRequestMiddleware`). `Risk`'s admin page got a working "History"
button (`SimpleHistoryAdmin`) that lists every past version with a diff.
Existing seeded rows got a one-time backfilled snapshot via
`manage.py populate_history --auto`; going forward, `history` populates
automatically on every save, including future `seed_demo --flush` runs
— no extra step needed for those.

## Cycle 8 (done) — Milestone 2: app complete

Polish pass: `pyproject.toml` description filled in, duplicated CSS
(`.band-*`, `.row-link`) consolidated from `heatmap.html`/`register.html`
into the shared `base.html`, this README reorganized with an overview up
top instead of requiring a read through all 8 cycles to know what the app
does.

This closed out the planned roadmap in [SPEC.md](SPEC.md). Phase 2 below
is new scope: AI features on top of the finished app.

## Cycle 9 (done) — AI settings

`AISettings` singleton model (`api_key`, `model` — free text, not a
hardcoded choice, so whatever model the account has access to works).
`/ai/settings/` page to edit it — API key uses a password input and is
never redisplayed in full (masked as `••••••••1234`, last 4 chars only);
leaving it blank on save keeps the existing key rather than clearing it.
`risks/ai.py` wraps the OpenAI client behind a single `generate_text()`
call, raising a friendly `AIError` for both "no key configured" and
"request failed" — verified both paths directly (missing key, and a
real 401 from an intentionally-invalid key) render a clean message
instead of a crash. Not registered in Django admin on purpose — admin
doesn't mask `CharField`s, which would defeat the point of the dedicated
page.

## Cycle 10 (done) — AI portfolio insight

A "Generate Insight" button on the heatmap page (`/`). POST-triggered
(not on page load — costs a real API call), it builds a text summary of
the actual current data — top 5 risks by score, portfolio average score
trend (first vs. last month with data), and up to 5 overdue mitigations
— and asks the model for a 3-4 sentence executive summary grounded in
that data. Read-only, no write path.

## Cycle 11 (done) — AI draft-assist

A custom "New Risk" page at `/new/` (not admin — admin isn't easily
extensible with a custom button without deeper template overrides).
Fill in a title + category, optionally hit "Draft with AI" (plain fetch,
no framework) to call `/ai/draft/`, which asks the model for a JSON
object (description, likelihood, impact, treatment_type,
mitigation_action_plan) and fills the form fields client-side — nothing
is saved until you hit "Save Risk". Likelihood/impact are clamped to 1-5
and treatment_type is validated against the real choices server-side, in
case the model returns something out of range. Saving creates the Risk
plus, if filled in, an inherent `RiskAssessment` and a `Mitigation`
(default due date: 90 days out if not specified) — then redirects to
that risk's admin change page. Verified live end-to-end in the browser
with a real API call — draft quality is genuinely good, specific to the
title/category given, not generic filler.

Cycle 12 (AI Q&A over the register) is scoped in [SPEC.md](SPEC.md) but
not yet built.
