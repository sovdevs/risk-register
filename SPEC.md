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
- `django-simple-history` for audit trail (added in cycle 4)
- Chart.js via CDN for the heatmap/trend visuals (added in cycle 6)
- Faker + a custom management command for synthetic demo data (cycle 5)
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
1. **Scaffold** — project + `risks` app, Risk/RiskCategory/Department
   models, admin registration, migrations. Runnable: CRUD via `/admin/`.
2. **RiskAssessment** — likelihood/impact/score, inline in Risk admin.
3. **Mitigation** — treatment type, action plan, residual assessment
   linkage.
4. **Audit trail** — wire up `django-simple-history` on the core models.
5. **Synthetic data** — `manage.py seed_demo`, Faker, weighted (not
   uniform) distributions, a deliberate narrative (e.g. Third-Party risks
   skew high and under-mitigated) rather than pure noise.
6. **Heatmap dashboard** — 5×5 likelihood × impact grid, Chart.js, risk
   count per cell.
7. **Filterable register view** — list page with status/category/
   department filters.
8. **Trend + overdue widgets** — aggregate risk score over time from
   assessment history; overdue mitigations list.
9. **Polish** — README, `pyproject.toml` cleanup, light styling pass.

Each cycle ends in a state where `uv run python manage.py runserver` works
and the new feature is visible/checkable.

## Non-goals
No multi-tenant orgs, no auth beyond Django's built-in, no deployment
config — this is a local dev demo only.
