At its core: it's a place to track organizational risks — the kind of tool a compliance/security team uses to answer "what could go wrong, how bad would it be, and what are we doing about it."

What you can actually do with it right now:

Log a risk — title, description, which category it falls under (Cyber, Financial, Legal & Regulatory, etc.), which department owns it, who's responsible, and its lifecycle status (identified → assessing → mitigating → monitoring → closed).
Score it — rate likelihood (1–5) and impact (1–5) to get a risk score (1–25). This happens twice per risk: an inherent score when first assessed, and a residual score once a mitigation is complete — so you can see how much a treatment actually reduced the risk.
Plan a response — record how you're treating a risk (accept/mitigate/transfer/avoid), the action plan, who owns it, and a due date.
See it at a glance — the heatmap (/) shows every risk plotted on a 5×5 likelihood × impact grid, color-banded Low→Critical, so you can spot where risk is concentrated. It uses each risk's current (most recent) score, so mitigated risks show their reduced position, not their original one.
Slice the list — the register (/register/) is a filterable table — by status, category, or department — with each row's current score and a link into the full record.
Full data entry — Django admin still handles actual CRUD: adding/editing risks, assessments, mitigations.
Right now it's populated with 27 realistic seeded risks across 7 categories (real GRC-style scenarios — unpatched CVEs, GDPR backlogs, vendor risk, budget overruns, etc.), so it already looks and behaves like a small real risk register rather than an empty schema.

What it doesn't do yet: trend-over-time charts, an overdue-items dashboard, or an audit trail of who-changed-what-when — those are cycles 6 and 7.