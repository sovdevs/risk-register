from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Department, Mitigation, Risk, RiskCategory
from .views import _action_requires_approval, _execute_agent_action

User = get_user_model()


class AgentActionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("jsmith", password="x")
        self.dept = Department.objects.create(name="IT")
        self.category = RiskCategory.objects.create(name="Cyber")
        self.risk = Risk.objects.create(
            title="Ransomware",
            category=self.category,
            department=self.dept,
            owner=self.owner,
            date_identified=date(2026, 1, 1),
        )

    def test_create_mitigation_action(self):
        text, url = _execute_agent_action({
            "tool": "create_mitigation",
            "args": {
                "risk_title": "ransomware",
                "treatment_type": "mitigate",
                "action_plan": "Deploy EDR",
                "owner_username": "jsmith",
                "due_date": "2026-09-01",
            },
        })
        mitigation = Mitigation.objects.get()
        self.assertIn("Created mitigation", text)
        self.assertEqual(url, f"/admin/risks/risk/{self.risk.id}/change/")
        self.assertEqual(mitigation.risk, self.risk)

    def test_update_mitigation_action_requires_existing_mitigation(self):
        with self.assertRaises(ValueError):
            _execute_agent_action({
                "tool": "update_mitigation",
                "args": {"risk_title": "Ransomware", "status": "complete"},
            })

    def test_unknown_risk_raises(self):
        with self.assertRaises(ValueError):
            _execute_agent_action({
                "tool": "create_mitigation",
                "args": {
                    "risk_title": "Nonexistent",
                    "treatment_type": "mitigate",
                    "action_plan": "x",
                    "owner_username": "jsmith",
                    "due_date": "2026-09-01",
                },
            })

    def test_requires_approval_defaults_true(self):
        self.assertTrue(_action_requires_approval(
            {"args": {"risk_title": "Ransomware"}}
        ))

    def test_requires_approval_false_when_category_opts_out(self):
        self.category.requires_approval = False
        self.category.save()
        self.assertFalse(_action_requires_approval(
            {"args": {"risk_title": "Ransomware"}}
        ))

    def test_ai_ask_surfaces_overdue_mitigation_unprompted(self):
        Mitigation.objects.create(
            risk=self.risk, treatment_type="mitigate", action_plan="Deploy EDR",
            owner=self.owner, due_date=date(2020, 1, 1),
        )
        self.client.force_login(self.owner)
        response = self.client.get("/ai/ask/")
        self.assertContains(response, "1 mitigation overdue")
