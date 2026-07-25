import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from faker import Faker

from risks.models import Department, Risk, RiskAssessment, RiskCategory

fake = Faker()

DEPARTMENTS = [
    "IT",
    "Finance",
    "Legal",
    "Operations",
    "HR",
    "Third-Party Management",
    "Sales",
]

# category name -> (description, likelihood/impact range used for inherent
# assessments, so the heatmap/dashboard built in later cycles has a
# believable shape instead of uniform noise)
CATEGORIES = {
    "Cyber": (
        "Threats to confidentiality, integrity, or availability of systems and data.",
        (3, 5),
    ),
    "Third-Party": (
        "Risks introduced by vendors, suppliers, and partners.",
        (3, 5),
    ),
    "Legal & Regulatory": (
        "Risks from non-compliance with laws and regulations.",
        (2, 4),
    ),
    "Financial": (
        "Risks affecting the organization's financial position.",
        (2, 4),
    ),
    "Operational": (
        "Risks from failed internal processes, people, or systems.",
        (2, 4),
    ),
    "Reputational": (
        "Risks to the organization's public standing or trust.",
        (2, 4),
    ),
    "Compliance": (
        "Risks from failing internal policy or external standards.",
        (1, 3),
    ),
}

RISK_TITLES = {
    "Cyber": [
        "Unpatched critical vulnerability on internet-facing systems",
        "Ransomware infection via phishing email",
        "Weak MFA enforcement for privileged accounts",
        "Sensitive data exposed in misconfigured cloud storage",
        "Insider threat: unauthorized access to production data",
    ],
    "Third-Party": [
        "Critical vendor lacks SOC 2 attestation",
        "No exit plan for sole-sourced cloud hosting provider",
        "Vendor security questionnaire responses unverified",
        "Fourth-party subcontractor risk not assessed",
    ],
    "Legal & Regulatory": [
        "Non-compliance with NIS2 incident reporting timelines",
        "GDPR data subject request backlog exceeding SLA",
        "Outdated data processing agreements with sub-processors",
        "Missing records of processing activities (Art. 30 GDPR)",
    ],
    "Financial": [
        "Currency exposure from unhedged foreign supplier contracts",
        "Budget overrun on multi-year infrastructure project",
        "Delayed customer payments impacting cash flow",
        "Inaccurate revenue recognition in new billing system",
    ],
    "Operational": [
        "Single point of failure in core order-processing system",
        "Inadequate backup and disaster recovery testing",
        "Key-person dependency on undocumented legacy process",
        "Manual data entry errors in financial reporting pipeline",
    ],
    "Reputational": [
        "Public disclosure risk from unresolved data breach",
        "Negative press exposure from vendor's ethical violations",
        "Customer trust erosion from repeated service outages",
    ],
    "Compliance": [
        "ISO 27001 surveillance audit findings not remediated",
        "Access reviews not performed on required quarterly cadence",
        "Security awareness training completion below policy threshold",
    ],
}

STATUS_WEIGHTS = {
    Risk.Status.IDENTIFIED: 0.15,
    Risk.Status.ASSESSING: 0.2,
    Risk.Status.MITIGATING: 0.35,
    Risk.Status.MONITORING: 0.2,
    Risk.Status.CLOSED: 0.1,
}


class Command(BaseCommand):
    help = "Seed demo Departments, Risk Categories, owners, Risks, and inherent RiskAssessments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete previously seeded risks/categories/departments first",
        )

    def handle(self, *args, **options):
        random.seed(42)
        Faker.seed(42)

        if options["flush"]:
            RiskAssessment.objects.all().delete()
            Risk.objects.all().delete()
            RiskCategory.objects.all().delete()
            Department.objects.all().delete()

        departments = [Department.objects.get_or_create(name=n)[0] for n in DEPARTMENTS]

        categories = {}
        for name, (description, severity_range) in CATEGORIES.items():
            cat, _ = RiskCategory.objects.get_or_create(
                name=name, defaults={"description": description}
            )
            categories[name] = (cat, severity_range)

        owners = self._seed_owners()
        statuses = list(STATUS_WEIGHTS.keys())
        weights = list(STATUS_WEIGHTS.values())

        risks_created = 0
        assessments_created = 0
        for cat_name, titles in RISK_TITLES.items():
            category, (lo, hi) = categories[cat_name]
            for title in titles:
                if Risk.objects.filter(title=title).exists():
                    continue

                date_identified = fake.date_between(start_date="-18M", end_date="-1M")
                risk = Risk.objects.create(
                    title=title,
                    description=fake.paragraph(nb_sentences=3),
                    category=category,
                    department=random.choice(departments),
                    owner=random.choice(owners),
                    status=random.choices(statuses, weights=weights)[0],
                    date_identified=date_identified,
                    next_review_date=date_identified
                    + timedelta(days=random.choice([90, 180, 365])),
                )
                risks_created += 1

                RiskAssessment.objects.create(
                    risk=risk,
                    kind=RiskAssessment.Kind.INHERENT,
                    likelihood=random.randint(lo, hi),
                    impact=random.randint(lo, hi),
                    assessed_by=random.choice(owners),
                    assessed_date=date_identified + timedelta(days=random.randint(1, 14)),
                    notes=fake.sentence(),
                )
                assessments_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(departments)} departments, {len(categories)} categories, "
                f"{len(owners)} owners, {risks_created} risks, "
                f"{assessments_created} inherent assessments."
            )
        )

    def _seed_owners(self):
        User = get_user_model()
        owners = []
        for _ in range(8):
            first, last = fake.first_name(), fake.last_name()
            username = f"{first}.{last}".lower()
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@example.com",
                },
            )
            if created:
                user.set_unusable_password()
                user.save()
            owners.append(user)
        return owners
