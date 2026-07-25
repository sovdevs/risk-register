import random
from datetime import timedelta
from pathlib import Path

import yaml
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from faker import Faker

from risks.models import Department, Mitigation, Risk, RiskAssessment, RiskCategory

fake = Faker()

SEED_DATA_PATH = Path(__file__).resolve().parents[2] / "seed_data.yaml"

STATUS_WEIGHTS = {
    Risk.Status.IDENTIFIED: 0.15,
    Risk.Status.ASSESSING: 0.2,
    Risk.Status.MITIGATING: 0.35,
    Risk.Status.MONITORING: 0.2,
    Risk.Status.CLOSED: 0.1,
}

# Risks in these statuses have moved past "just identified" and get a
# Mitigation record. Mitigation.status follows from Risk.status: still
# mitigating means the treatment is underway; monitoring/closed means it's
# done (and earns a residual RiskAssessment showing the risk reduced).
MITIGATION_STATUSES = {
    Risk.Status.MITIGATING: (
        [Mitigation.Status.NOT_STARTED, Mitigation.Status.IN_PROGRESS],
        [0.3, 0.7],
    ),
    Risk.Status.MONITORING: ([Mitigation.Status.COMPLETE], [1.0]),
    Risk.Status.CLOSED: ([Mitigation.Status.COMPLETE], [1.0]),
}

TREATMENT_TYPE_WEIGHTS = {
    Mitigation.TreatmentType.MITIGATE: 0.6,
    Mitigation.TreatmentType.TRANSFER: 0.15,
    Mitigation.TreatmentType.ACCEPT: 0.15,
    Mitigation.TreatmentType.AVOID: 0.1,
}


def load_seed_data():
    with SEED_DATA_PATH.open() as f:
        return yaml.safe_load(f)


class Command(BaseCommand):
    help = (
        "Seed demo Departments, Risk Categories, owners, Risks, RiskAssessments "
        "(inherent + residual), and Mitigations from risks/seed_data.yaml."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete previously seeded risks/categories/departments first",
        )

    def handle(self, *args, **options):
        random.seed(42)
        Faker.seed(42)

        data = load_seed_data()

        if options["flush"]:
            Mitigation.objects.all().delete()
            RiskAssessment.objects.all().delete()
            Risk.objects.all().delete()
            RiskCategory.objects.all().delete()
            Department.objects.all().delete()
            # is_superuser=False, is_staff=False excludes real accounts like
            # your own createsuperuser login — only seeded demo owners match.
            get_user_model().objects.filter(is_superuser=False, is_staff=False).delete()

        departments = [
            Department.objects.get_or_create(name=n)[0] for n in data["departments"]
        ]

        categories = {}
        for name, cat_data in data["categories"].items():
            cat, _ = RiskCategory.objects.get_or_create(
                name=name, defaults={"description": cat_data["description"]}
            )
            categories[name] = (cat, tuple(cat_data["severity_range"]))

        owners = self._seed_owners()
        statuses = list(STATUS_WEIGHTS.keys())
        weights = list(STATUS_WEIGHTS.values())

        risks_created = 0
        assessments_created = 0
        mitigations_created = 0
        for cat_name, entries in data["risks"].items():
            category, (lo, hi) = categories[cat_name]
            for entry in entries:
                title = entry["title"]
                if Risk.objects.filter(title=title).exists():
                    continue

                date_identified = fake.date_between(start_date="-18M", end_date="-1M")
                risk = Risk.objects.create(
                    title=title,
                    description=entry["description"],
                    category=category,
                    department=random.choice(departments),
                    owner=random.choice(owners),
                    status=random.choices(statuses, weights=weights)[0],
                    date_identified=date_identified,
                    next_review_date=date_identified
                    + timedelta(days=random.choice([90, 180, 365])),
                )
                risks_created += 1

                inherent_likelihood = random.randint(lo, hi)
                inherent_impact = random.randint(lo, hi)
                RiskAssessment.objects.create(
                    risk=risk,
                    kind=RiskAssessment.Kind.INHERENT,
                    likelihood=inherent_likelihood,
                    impact=inherent_impact,
                    assessed_by=random.choice(owners),
                    assessed_date=date_identified + timedelta(days=random.randint(1, 14)),
                    notes=fake.sentence(),
                )
                assessments_created += 1

                if risk.status in MITIGATION_STATUSES:
                    mitigation_statuses, mitigation_weights = MITIGATION_STATUSES[risk.status]
                    mitigation_status = random.choices(
                        mitigation_statuses, weights=mitigation_weights
                    )[0]
                    due_date = date_identified + timedelta(days=random.randint(30, 180))
                    Mitigation.objects.create(
                        risk=risk,
                        treatment_type=random.choices(
                            list(TREATMENT_TYPE_WEIGHTS),
                            weights=list(TREATMENT_TYPE_WEIGHTS.values()),
                        )[0],
                        action_plan=entry["mitigation_action_plan"],
                        owner=random.choice(owners),
                        due_date=due_date,
                        status=mitigation_status,
                    )
                    mitigations_created += 1

                    if mitigation_status == Mitigation.Status.COMPLETE:
                        RiskAssessment.objects.create(
                            risk=risk,
                            kind=RiskAssessment.Kind.RESIDUAL,
                            likelihood=max(1, inherent_likelihood - random.randint(1, 2)),
                            impact=max(1, inherent_impact - random.randint(1, 2)),
                            assessed_by=random.choice(owners),
                            assessed_date=due_date + timedelta(days=random.randint(1, 10)),
                            notes=fake.sentence(),
                        )
                        assessments_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(departments)} departments, {len(categories)} categories, "
                f"{len(owners)} owners, {risks_created} risks, "
                f"{assessments_created} assessments, {mitigations_created} mitigations."
            )
        )

    def _seed_owners(self):
        # Mixed German/American names, not a --locale toggle: this is a
        # multinational org, not a localized build of the app. Titles,
        # categories, and departments stay English regardless.
        User = get_user_model()
        en_fake = Faker("en_US")
        de_fake = Faker("de_DE")
        en_fake.seed_instance(42)
        de_fake.seed_instance(43)

        owners = []
        for i in range(8):
            locale_fake = de_fake if i % 2 == 0 else en_fake
            first, last = locale_fake.first_name(), locale_fake.last_name()
            username = self._slug(f"{first}.{last}")
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

    _UMLAUT_MAP = str.maketrans(
        {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
    )

    def _slug(self, value):
        return value.translate(self._UMLAUT_MAP).encode("ascii", "ignore").decode("ascii").lower()
