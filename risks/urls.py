from django.urls import path

from . import views

app_name = "risks"

urlpatterns = [
    path("", views.heatmap, name="heatmap"),
]
