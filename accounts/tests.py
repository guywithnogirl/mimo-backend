from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class HealthCheckTests(TestCase):
    def test_health_reports_database_ready(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("accounts.views.connection.cursor", side_effect=OperationalError("unavailable"))
    def test_health_hides_database_error_details(self, _cursor):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})


@override_settings(AUTHORIZED_USERNAMES=("alice", "bob"))
class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        user_model.objects.create_user(username="alice", password="test-password-a")
        user_model.objects.create_user(username="bob", password="test-password-b")
        user_model.objects.create_user(username="outsider", password="test-password-c")

    def setUp(self):
        self.client = APIClient()

    def test_each_authorized_account_can_obtain_tokens(self):
        for username, password in (
            ("alice", "test-password-a"),
            ("bob", "test-password-b"),
        ):
            with self.subTest(username=username):
                response = self.client.post(
                    "/api/auth/token/",
                    {"username": username, "password": password},
                    format="json",
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("access", response.json())
                self.assertIn("refresh", response.json())

    def test_other_valid_account_cannot_obtain_tokens(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "outsider", "password": "test-password-c"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_authenticated_identity_requires_a_token(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 401)
