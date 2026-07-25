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

No audit trail or dashboard yet — that's cycles 4+.
