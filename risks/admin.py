from django.contrib import admin

from .models import Department, Risk, RiskAssessment, RiskCategory


class RiskAssessmentInline(admin.TabularInline):
    model = RiskAssessment
    extra = 0
    fields = ["kind", "likelihood", "impact", "score_display", "assessed_by", "assessed_date", "notes"]
    readonly_fields = ["score_display"]

    @admin.display(description="Score")
    def score_display(self, obj):
        return obj.score if obj.pk else "—"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(RiskCategory)
class RiskCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "description"]
    search_fields = ["name"]


@admin.register(Risk)
class RiskAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "department",
        "owner",
        "status",
        "date_identified",
        "next_review_date",
    ]
    list_filter = ["status", "category", "department"]
    search_fields = ["title", "description"]
    date_hierarchy = "date_identified"
    inlines = [RiskAssessmentInline]
