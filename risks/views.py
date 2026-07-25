from django.shortcuts import render

from .models import Department, Risk, RiskAssessment, RiskCategory

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
