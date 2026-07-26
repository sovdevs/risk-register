import json
import re
from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from . import ai
from .models import AISettings, Department, Mitigation, Risk, RiskAssessment, RiskCategory

SCORE_BANDS = [
    (4, "low"),
    (9, "medium"),
    (15, "high"),
    (25, "critical"),
]


def _score_band(score):
    for threshold, band in SCORE_BANDS:
        if score <= threshold:
            return band
    return "critical"


def _latest_assessments_by_risk():
    # "Current" position per risk = its most recent assessment, so a risk
    # with a completed mitigation shows its residual (reduced) score
    # instead of the original inherent one. Shared by the heatmap and the
    # register list so both agree on what "current score" means.
    assessments = RiskAssessment.objects.select_related("risk").order_by(
        "risk_id", "-assessed_date", "-id"
    )
    latest_by_risk = {}
    for assessment in assessments:
        latest_by_risk.setdefault(assessment.risk_id, assessment)
    return latest_by_risk


def _monthly_trend():
    # Reconstructs the portfolio's average risk score at the end of each
    # calendar month, using whichever assessment was "current" per risk as
    # of that month (same latest-as-of-a-point-in-time idea as
    # _latest_assessments_by_risk, but walked forward through time instead
    # of collapsed to "now"). This is what makes completed mitigations show
    # up as the average trending down, not just a snapshot.
    assessments = list(
        RiskAssessment.objects.order_by("assessed_date", "id")
    )
    if not assessments:
        return {"labels": [], "scores": []}

    by_month = defaultdict(list)
    for assessment in assessments:
        key = (assessment.assessed_date.year, assessment.assessed_date.month)
        by_month[key].append(assessment)

    today = timezone.localdate()
    year, month = assessments[0].assessed_date.year, assessments[0].assessed_date.month

    current = {}
    labels = []
    scores = []
    while (year, month) <= (today.year, today.month):
        for assessment in by_month.get((year, month), []):
            current[assessment.risk_id] = assessment
        labels.append(date(year, month, 1).strftime("%b %Y"))
        scores.append(
            round(sum(a.score for a in current.values()) / len(current), 2)
            if current
            else None
        )
        month += 1
        if month > 12:
            month = 1
            year += 1

    return {"labels": labels, "scores": scores}


def _linkify_risk_mentions(text):
    # AI-generated text (insight, Q&A answers) often names specific risks
    # verbatim since their exact titles are in the prompt context. Turn
    # those mentions into links back to the risk's admin page — escape
    # the raw text first (it's model output, not trusted), then insert
    # our own <a> tags in a single regex pass so a shorter title can't
    # get double-wrapped if it happens to be a substring of a longer
    # one's already-linked HTML.
    escaped = escape(text)
    risks = sorted(
        Risk.objects.only("id", "title"), key=lambda r: len(r.title), reverse=True
    )
    if not risks:
        return mark_safe(escaped)

    by_escaped_title = {escape(r.title): r for r in risks}
    pattern = "|".join(re.escape(t) for t in by_escaped_title)

    def _replace(match):
        risk = by_escaped_title[match.group(0)]
        return f'<a href="/admin/risks/risk/{risk.id}/change/">{match.group(0)}</a>'

    return mark_safe(re.sub(pattern, _replace, escaped))


def _overdue_mitigations():
    today = timezone.localdate()
    overdue = list(
        Mitigation.objects.filter(due_date__lt=today)
        .exclude(status=Mitigation.Status.COMPLETE)
        .select_related("risk", "owner")
        .order_by("due_date")
    )
    for mitigation in overdue:
        mitigation.days_overdue = (today - mitigation.due_date).days
    return overdue


def _build_portfolio_context(grid, trend_data, overdue_mitigations):
    # Grounds the AI insight prompt in the same data the page shows —
    # real risk titles/scores/dates, not a description of the UI. Keeps
    # the model from having to infer anything it could get wrong.
    lines = ["Top risks by current score:"]
    cells = sorted(
        (c for row in grid for c in row["cells"] if c["count"]),
        key=lambda c: c["score"],
        reverse=True,
    )
    for cell in cells[:5]:
        for title in cell["risk_titles"]:
            lines.append(f"- {title} (score {cell['score']}, {cell['band']})")

    scores = [s for s in trend_data["scores"] if s is not None]
    if len(scores) >= 2:
        lines.append(
            f"\nPortfolio average score trend: {scores[0]} "
            f"({trend_data['labels'][0]}) -> {scores[-1]} "
            f"({trend_data['labels'][-1]})."
        )

    lines.append(f"\nOverdue mitigations: {len(overdue_mitigations)}")
    for mitigation in overdue_mitigations[:5]:
        lines.append(
            f"- {mitigation.risk.title} ({mitigation.get_treatment_type_display()}, "
            f"{mitigation.days_overdue} days overdue)"
        )

    return "\n".join(lines)


AI_INSIGHT_SYSTEM_PROMPT = (
    "You are a GRC risk analyst assistant. Given this risk portfolio data, "
    "write a concise 3-4 sentence executive summary highlighting the "
    "biggest concerns and any notable trend. When naming a risk, quote its "
    "title exactly as given — this lets the app turn it into a link. "
    "Reference specific risk names and numbers from the data provided. Do "
    "not invent risks not listed. Plain prose only — no markdown "
    "formatting (no **bold**, no bullet points, no headers)."
)


def heatmap(request):
    latest_by_risk = _latest_assessments_by_risk()

    cells = {}
    for assessment in latest_by_risk.values():
        key = (assessment.likelihood, assessment.impact)
        cells.setdefault(key, []).append(assessment.risk)

    grid = []
    for likelihood in range(5, 0, -1):
        row_cells = []
        for impact in range(1, 6):
            risks = cells.get((likelihood, impact), [])
            score = likelihood * impact
            row_cells.append(
                {
                    "impact": impact,
                    "score": score,
                    "band": _score_band(score),
                    "count": len(risks),
                    "risk_titles": [r.title for r in risks],
                }
            )
        grid.append({"likelihood": likelihood, "cells": row_cells})

    trend_data = _monthly_trend()
    overdue_mitigations = _overdue_mitigations()

    ai_insight = None
    ai_error = None
    if request.method == "POST" and request.POST.get("action") == "generate_insight":
        try:
            portfolio_context = _build_portfolio_context(
                grid, trend_data, overdue_mitigations
            )
            raw_insight = ai.generate_text(AI_INSIGHT_SYSTEM_PROMPT, portfolio_context)
            ai_insight = _linkify_risk_mentions(raw_insight)
        except ai.AIError as exc:
            ai_error = str(exc)

    context = {
        "grid": grid,
        "total_risks": Risk.objects.count(),
        "assessed_risks": len(latest_by_risk),
        "trend_data": trend_data,
        "overdue_mitigations": overdue_mitigations,
        "ai_insight": ai_insight,
        "ai_error": ai_error,
    }
    return render(request, "risks/heatmap.html", context)


def ai_settings(request):
    settings_obj = AISettings.load()
    if request.method == "POST":
        model = request.POST.get("model", "").strip()
        api_key = request.POST.get("api_key", "").strip()
        if model:
            settings_obj.model = model
        if api_key:
            settings_obj.api_key = api_key
        settings_obj.save()
        return redirect("risks:ai_settings")

    key_preview = None
    if settings_obj.api_key:
        key_preview = "•" * 8 + settings_obj.api_key[-4:]

    return render(
        request,
        "risks/ai_settings.html",
        {"settings": settings_obj, "key_preview": key_preview},
    )


def register(request):
    status = request.GET.get("status", "")
    category_id = request.GET.get("category", "")
    department_id = request.GET.get("department", "")

    risks_qs = Risk.objects.select_related("category", "department", "owner").order_by(
        "-date_identified"
    )
    if status:
        risks_qs = risks_qs.filter(status=status)
    if category_id:
        risks_qs = risks_qs.filter(category_id=category_id)
    if department_id:
        risks_qs = risks_qs.filter(department_id=department_id)

    risks = list(risks_qs)
    latest_by_risk = _latest_assessments_by_risk()
    for risk in risks:
        assessment = latest_by_risk.get(risk.id)
        risk.current_score = assessment.score if assessment else None
        risk.current_band = _score_band(assessment.score) if assessment else None

    context = {
        "risks": risks,
        "result_count": len(risks),
        "statuses": Risk.Status.choices,
        "categories": RiskCategory.objects.order_by("name"),
        "departments": Department.objects.order_by("name"),
        "selected_status": status,
        "selected_category": category_id,
        "selected_department": department_id,
    }
    return render(request, "risks/register.html", context)


AI_DRAFT_SYSTEM_PROMPT = (
    "You are a GRC risk analyst. Given a risk title and category, draft a "
    "plausible, specific risk record for it. Respond as a JSON object with "
    "exactly these keys: description (2-3 sentence string), likelihood "
    "(integer 1-5), impact (integer 1-5), treatment_type (one of: accept, "
    "mitigate, transfer, avoid), mitigation_action_plan (2-3 sentence "
    "string). Plain prose only, no markdown."
)


def _clamp_1_5(value, default=3):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(5, n))


def ai_draft(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid request body"}, status=400)

    title = (payload.get("title") or "").strip()
    if not title:
        return JsonResponse({"error": "Enter a title first."}, status=400)

    category_name = ""
    category_id = payload.get("category")
    if category_id:
        category = RiskCategory.objects.filter(id=category_id).first()
        category_name = category.name if category else ""

    user_prompt = f"Risk title: {title}\nCategory: {category_name or 'unspecified'}"

    try:
        draft = ai.generate_json(AI_DRAFT_SYSTEM_PROMPT, user_prompt)
    except ai.AIError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    valid_treatments = {choice[0] for choice in Mitigation.TreatmentType.choices}
    treatment_type = draft.get("treatment_type")
    if treatment_type not in valid_treatments:
        treatment_type = Mitigation.TreatmentType.MITIGATE

    return JsonResponse(
        {
            "description": draft.get("description", ""),
            "likelihood": _clamp_1_5(draft.get("likelihood")),
            "impact": _clamp_1_5(draft.get("impact")),
            "treatment_type": treatment_type,
            "mitigation_action_plan": draft.get("mitigation_action_plan", ""),
        }
    )


def new_risk(request):
    if request.method == "POST":
        date_identified_raw = request.POST.get("date_identified")
        date_identified = (
            date.fromisoformat(date_identified_raw)
            if date_identified_raw
            else timezone.localdate()
        )
        owner_id = request.POST.get("owner")

        risk = Risk.objects.create(
            title=request.POST.get("title", "").strip(),
            description=request.POST.get("description", "").strip(),
            category_id=request.POST.get("category"),
            department_id=request.POST.get("department"),
            owner_id=owner_id,
            status=request.POST.get("status", Risk.Status.IDENTIFIED),
            date_identified=date_identified,
        )

        likelihood = request.POST.get("likelihood")
        impact = request.POST.get("impact")
        if likelihood and impact:
            RiskAssessment.objects.create(
                risk=risk,
                kind=RiskAssessment.Kind.INHERENT,
                likelihood=_clamp_1_5(likelihood),
                impact=_clamp_1_5(impact),
                assessed_by_id=owner_id,
                assessed_date=date_identified,
            )

        treatment_type = request.POST.get("treatment_type")
        action_plan = request.POST.get("mitigation_action_plan", "").strip()
        if treatment_type and action_plan:
            due_date_raw = request.POST.get("due_date")
            due_date = (
                date.fromisoformat(due_date_raw)
                if due_date_raw
                else date_identified + timedelta(days=90)
            )
            Mitigation.objects.create(
                risk=risk,
                treatment_type=treatment_type,
                action_plan=action_plan,
                owner_id=owner_id,
                due_date=due_date,
                status=Mitigation.Status.NOT_STARTED,
            )

        return redirect(f"/admin/risks/risk/{risk.id}/change/")

    context = {
        "categories": RiskCategory.objects.order_by("name"),
        "departments": Department.objects.order_by("name"),
        "owners": get_user_model().objects.order_by("username"),
        "statuses": Risk.Status.choices,
        "treatment_types": Mitigation.TreatmentType.choices,
        "today": timezone.localdate(),
    }
    return render(request, "risks/new_risk.html", context)


AI_ASK_SYSTEM_PROMPT = (
    "You are a GRC risk analyst assistant answering questions about this "
    "organization's risk register. Answer ONLY using the data provided — "
    "do not invent risks, scores, owners, or details not present in it. "
    "When naming a specific risk, quote its title exactly as given — this "
    "lets the app turn it into a link. If the question can't be answered "
    "from the data, say so plainly. Keep answers concise. Plain prose "
    "only, no markdown."
)


def _register_context():
    # Full context, not a retrieval subset — dataset is small enough
    # (dozens of risks) that passing everything is simpler and more
    # reliable than trying to guess which rows are relevant to a given
    # question.
    latest_by_risk = _latest_assessments_by_risk()
    risks = (
        Risk.objects.select_related("category", "department", "owner")
        .prefetch_related("mitigations")
        .order_by("-date_identified")
    )

    blocks = []
    for risk in risks:
        assessment = latest_by_risk.get(risk.id)
        score = assessment.score if assessment else "unassessed"
        lines = [
            f"Risk: {risk.title}",
            f"Category: {risk.category.name} | Department: {risk.department.name} "
            f"| Owner: {risk.owner.get_full_name() or risk.owner.username}",
            f"Status: {risk.get_status_display()} | Current score: {score}",
            f"Description: {risk.description}",
        ]
        mitigation = risk.mitigations.first()
        if mitigation:
            overdue = " (OVERDUE)" if mitigation.is_overdue else ""
            lines.append(
                f"Mitigation: {mitigation.get_treatment_type_display()}, "
                f"status {mitigation.get_status_display()}, due "
                f"{mitigation.due_date}{overdue} — {mitigation.action_plan}"
            )
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def ai_ask(request):
    question = ""
    answer = None
    error = None
    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        if question:
            try:
                user_prompt = (
                    f"Risk register data:\n{_register_context()}\n\n"
                    f"Question: {question}"
                )
                raw_answer = ai.generate_text(AI_ASK_SYSTEM_PROMPT, user_prompt)
                answer = _linkify_risk_mentions(raw_answer)
            except ai.AIError as exc:
                error = str(exc)

    return render(
        request,
        "risks/ai_ask.html",
        {"question": question, "answer": answer, "error": error},
    )
