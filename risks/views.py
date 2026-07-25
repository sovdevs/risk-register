from collections import defaultdict
from datetime import date

from django.shortcuts import render
from django.utils import timezone

from .models import Department, Mitigation, Risk, RiskAssessment, RiskCategory

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

    context = {
        "grid": grid,
        "total_risks": Risk.objects.count(),
        "assessed_risks": len(latest_by_risk),
        "trend_data": _monthly_trend(),
        "overdue_mitigations": _overdue_mitigations(),
    }
    return render(request, "risks/heatmap.html", context)


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
