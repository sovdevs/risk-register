from django.urls import path

from . import views

app_name = "risks"

urlpatterns = [
    path("", views.heatmap, name="heatmap"),
    path("register/", views.register, name="register"),
    path("new/", views.new_risk, name="new_risk"),
    path("ai/settings/", views.ai_settings, name="ai_settings"),
    path("ai/draft/", views.ai_draft, name="ai_draft"),
]
