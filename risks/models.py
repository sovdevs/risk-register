from django.conf import settings
from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RiskCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "risk categories"

    def __str__(self):
        return self.name


class Risk(models.Model):
    class Status(models.TextChoices):
        IDENTIFIED = "identified", "Identified"
        ASSESSING = "assessing", "Assessing"
        MITIGATING = "mitigating", "Mitigating"
        MONITORING = "monitoring", "Monitoring"
        CLOSED = "closed", "Closed"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        RiskCategory, on_delete=models.PROTECT, related_name="risks"
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="risks"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_risks"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IDENTIFIED
    )
    date_identified = models.DateField()
    next_review_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-date_identified"]

    def __str__(self):
        return self.title


class RiskAssessment(models.Model):
    class Kind(models.TextChoices):
        INHERENT = "inherent", "Inherent"
        RESIDUAL = "residual", "Residual"

    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="assessments")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.INHERENT)
    likelihood = models.PositiveSmallIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)]
    )
    impact = models.PositiveSmallIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)]
    )
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="risk_assessments"
    )
    assessed_date = models.DateField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-assessed_date"]

    @property
    def score(self):
        return self.likelihood * self.impact

    def __str__(self):
        return f"{self.risk.title} — {self.get_kind_display()} ({self.score})"


class Mitigation(models.Model):
    class TreatmentType(models.TextChoices):
        ACCEPT = "accept", "Accept"
        MITIGATE = "mitigate", "Mitigate"
        TRANSFER = "transfer", "Transfer"
        AVOID = "avoid", "Avoid"

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETE = "complete", "Complete"

    risk = models.ForeignKey(Risk, on_delete=models.CASCADE, related_name="mitigations")
    treatment_type = models.CharField(max_length=20, choices=TreatmentType.choices)
    action_plan = models.TextField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_mitigations"
    )
    due_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NOT_STARTED
    )

    class Meta:
        ordering = ["due_date"]

    @property
    def is_overdue(self):
        return self.status != self.Status.COMPLETE and self.due_date < timezone.localdate()

    def __str__(self):
        return f"{self.get_treatment_type_display()} — {self.risk.title}"
