# Risk Register

**What this demo is actually about**: how a thin AI layer, dropped on top
of an otherwise static Django CRUD backend, makes that backend's data
meaningfully easier to get information *out of* — without changing the
underlying data model at all. Cycles 1-8 built a real, ordinary Django
app: models, admin, a heatmap dashboard, filters, an audit trail — no AI
anywhere. Cycles 9-12 then added a BYOK OpenAI layer on top of that
already-finished app: ask it questions in plain English, get a portfolio
summary on demand, get help drafting a new entry. The underlying app
happens to be an enterprise-style risk register (likelihood × impact
scoring, mitigation tracking — the kind of tool a GRC vendor like
Athereon builds), but the point of the exercise was the retrieval layer,
not the register itself.

See [SPEC.md](SPEC.md) for the full data model and roadmap, or the
cycle-by-cycle notes below for what shipped when and why.

**The AI layer — the actual point of this demo:**

- **Ask it, and let it act** (`/ai/ask/`) — natural-language Q&A that
  looks up whatever it needs via tool calls (`search_risks`,
  `get_risk_detail`) instead of getting the whole register dumped in up
  front; any risk it names becomes a clickable link. It can also propose
  writes (`create_mitigation`, `update_mitigation`) — shown as a pending
  diff you approve or discard, nothing saved until you say so, unless a
  risk's category has been marked as not requiring approval. The page
  also runs a standing proactive check for overdue mitigations, surfaced
  before you ask anything. A collapsible panel lists every tool the
  assistant has, its description, and the live system prompt — what it
  can do isn't hidden behind the chat.
- **Summarize it** (`/` → "Generate Insight") — a one-click portfolio
  summary (top risks, score trend, overdue mitigations) instead of
  reading the dashboard yourself.
- **Draft with it** (`/new/` → "Draft with AI") — given just a title and
  category, drafts a description, a suggested likelihood/impact, and a
  mitigation plan — editable before saving, nothing auto-applied.

**The underlying static app it sits on:**

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

Comes seeded with 27-28 realistic risks across 7 categories (unpatched
CVEs, GDPR backlogs, vendor risk, budget overruns, etc.) — see
`seed_demo` below.

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

## Cycle 12 (done) — AI Q&A

A chat-style page at `/ai/ask/`: type a question in plain English, get an
answer grounded in the actual register. `_register_context()` builds a
full text dump of every current risk (title, category, department,
owner, status, current score, description, and mitigation plan where one
exists — ~16.5K characters for 28 risks) and passes it as context with
every question; no retrieval/filtering logic needed at this data volume.
The system prompt instructs the model to answer only from the provided
data and say so plainly if it can't. Verified live: correctly listed all
7 overdue mitigations with the right due dates and picked out the most
overdue one; correctly declined to answer a question about data that
isn't tracked (insurance coverage) rather than guessing.

This completes Phase 2 as scoped in [SPEC.md](SPEC.md). The app now has:
data model + admin (cycles 1-3), heatmap/register/trend/overdue
dashboards (cycles 4-6), audit trail (cycle 7), polish (cycle 8), and a
full BYOK AI layer — settings, portfolio insight, draft-assist, and Q&A
(cycles 9-12).

## Cycle 13 (done) — Agentic assistant: propose-then-approve writes, proactive checks, multi-tool reasoning

Phase 3, new scope: turning the Q&A assistant from cycle 12 into
something closer to an agent — able to act (with approval), notice
things unprompted, and reason over the register via tool calls instead
of a full context dump. Modeled after a competitor's ("LAiKA") feature
set, scoped down to what fits this app without new infrastructure (no
Teams/email integration, no scheduler, no asset-inventory module — those
were explicitly cut, see below).

- **Propose-then-approve writes.** `ai.run_agent()` gives the model two
  write tools, `create_mitigation` and `update_mitigation`
  (`risks/ai.py`). Neither executes inline — every call is queued and
  returned to the caller as a proposed action. `/ai/ask/` renders queued
  actions as a diff card with Approve/Discard buttons; approving runs
  `_execute_agent_action()` (`risks/views.py`), which validates the risk
  and owner exist before writing anything, and the confirmation links
  straight to the changed risk's admin page as evidence.
- **Configurable approval.** `RiskCategory.requires_approval` (default
  `True`, list-editable in admin) lets a category opt out of the gate —
  matching writes apply immediately and say so on the page
  (`_action_requires_approval()`). An unresolvable risk title still
  routes through the approval step rather than silently applying, so
  ambiguity never bypasses the gate.
- **Proactive overdue check.** `/ai/ask/` shows a standing "N mitigations
  overdue" banner, grouped by owner and linked to each record, before
  any question is asked — reusing the same `_overdue_mitigations()`
  helper the heatmap's dashboard list already used. No scheduler, no
  external notification channel (Teams/email) — this is a page-load
  check, not a background job; real proactive nagging of owners needs
  actual users and a delivery channel this demo doesn't have.
- **Multi-tool reasoning, replacing the context dump.** Cycle 12's
  `_register_context()` (full text dump of every risk, ~16.5K chars) is
  gone. The model now calls `search_risks` (filter by owner, status,
  category, overdue) and `get_risk_detail` (full detail for one risk) —
  read tools execute immediately server-side and feed results back, in
  a loop (`ai.run_agent()`, max 5 rounds) — so it only pulls what a
  given question actually needs.
- **Transparent, single-source-of-truth prompts.** `ai.TOOLS` is one
  registry (name, `kind` read/write, description, JSON-schema
  parameters) that generates both the OpenAI tool schema sent to the
  model and a "what the assistant can do" panel on `/ai/ask/` — the
  same text the model sees is what the page shows, so there's no
  separate/hand-copied description to drift out of sync. The system
  prompt is shown in the same panel.
- **Two real bugs found and fixed via live testing**, not just written
  tests: `search_risks` returned an empty (not error) result for a
  typo'd/nonexistent `owner_username`, so the assistant reported false
  negatives ("X has no overdue risks") instead of saying it couldn't
  find that user — now returns `{"error": ...}`. And `owner_username`
  only matched `Risk.owner`, missing risks where the person is the
  *mitigation's* owner instead (a different, sometimes-different
  person) — now matches either via `Q(owner=...) | Q(mitigations__owner=...)`.

**Explicitly cut**, to keep this an extension of the existing app rather
than a rebuild: an "Infrastructure Mapper"-equivalent asset inventory
(new domain — assets/metamodel/protection-need scoring — not a risk
register concern, and would replicate modeling work already done here
for risks themselves); MS Teams/email delivery for nudges; a scheduler
for true background/unprompted runs; multi-turn clarifying follow-up
questions (the right tool for that is a proper agent framework with
conversation state, not something to hand-roll here); and "autonomous
prioritization" as a distinct capability — without new write scope or
external system access, an agent here has nothing to do but nag, so
that's just a ranking policy on data already surfaced, not a new
feature.
