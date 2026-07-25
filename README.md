# Risk Register

See [SPEC.md](SPEC.md) for the full data model and feature-cycle roadmap.

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

No trend charts, overdue widgets, or audit trail yet — that's cycles 6+.
See [SPEC.md](SPEC.md) for the full roadmap.
