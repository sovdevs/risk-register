from django.shortcuts import render

from .models import Risk, RiskAssessment

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


def heatmap(request):
    # "Current" position per risk = its most recent assessment, so a risk
    # with a completed mitigation shows its residual (reduced) score
    # instead of the original inherent one.
    assessments = RiskAssessment.objects.select_related("risk").order_by(
        "risk_id", "-assessed_date", "-id"
    )
    latest_by_risk = {}
    for assessment in assessments:
        latest_by_risk.setdefault(assessment.risk_id, assessment)

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
