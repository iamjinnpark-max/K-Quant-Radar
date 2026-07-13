import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from platform_api.auth import _unsign_cookie, decode_identity
from platform_api.config import Settings
from platform_api.entitlements import (
    effective_plan,
    enforce_scan_limit,
    entitlements_for,
    filter_recommendation_payload,
)
from platform_api.ratelimit import rate_limit_key
from platform_api.tasks import public_error
from platform_api.main import get_job


def cognito_settings():
    return SimpleNamespace(
        auth_mode="cognito",
        cognito_region="ap-northeast-2",
        cognito_user_pool_id="ap-northeast-2_example",
        cognito_app_client_id="example-client",
    )


class FakeJwkClient:
    def get_signing_key_from_jwt(self, _token):
        return SimpleNamespace(key="public-key")


class SecurityBoundaryTests(unittest.TestCase):
    def test_authentication_defaults_to_server_session(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.auth_mode, "session")

    def test_signed_cookie_rejects_tampering(self):
        import base64
        import hashlib
        import hmac

        signing_material = "a-strong-test-value-that-is-not-production"
        value = "opaque-session-id"
        signature = base64.b64encode(
            hmac.new(signing_material.encode(), value.encode(), hashlib.sha256).digest()
        ).decode().rstrip("=")
        signed = f"s:{value}.{signature}"
        self.assertEqual(_unsign_cookie(signed, signing_material), value)
        self.assertIsNone(_unsign_cookie(signed + "tampered", signing_material))
        self.assertIsNone(_unsign_cookie(signed, "different-secret"))

    def test_worker_errors_redact_api_credentials(self):
        error = RuntimeError(
            "request failed: https://example.invalid?crtfc_key=private-value&x=1"
        )
        message = public_error(error)
        self.assertNotIn("private-value", message)
        self.assertIn("crtfc_key=[redacted]", message)

    @patch("platform_api.main.record_event")
    def test_job_lookup_is_always_scoped_to_current_account(self, _audit):
        db = Mock()
        db.scalar.return_value = None
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/api/v1/recommendation-jobs/private-job",
            "headers": [],
            "client": ("127.0.0.1", 1234),
        })
        user = SimpleNamespace(id="current-user-id")

        with self.assertRaises(HTTPException) as raised:
            get_job("private-job-id", request, db, user)

        self.assertEqual(raised.exception.status_code, 404)
        statement = db.scalar.call_args.args[0]
        self.assertIn("recommendation_jobs.user_id", str(statement))
        self.assertIn("current-user-id", statement.compile().params.values())

    def test_unknown_authentication_mode_is_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(auth_mode="anything-else", _env_file=None)

    @patch("platform_api.auth.get_settings", return_value=cognito_settings())
    def test_cognito_mode_requires_bearer_token(self, _settings):
        with self.assertRaises(HTTPException) as raised:
            decode_identity(None)
        self.assertEqual(raised.exception.status_code, 401)

    @patch("platform_api.auth._jwk_client", return_value=FakeJwkClient())
    @patch("platform_api.auth.get_settings", return_value=cognito_settings())
    @patch("platform_api.auth.jwt.decode")
    def test_verified_id_token_is_accepted(
        self,
        decode,
        _settings,
        _client,
    ):
        decode.return_value = {
            "sub": "user-123",
            "email": "user@example.com",
            "token_use": "id",
            "cognito:groups": ["members"],
        }
        identity = decode_identity("Bearer signed-token")
        self.assertEqual(identity.sub, "user-123")
        self.assertEqual(identity.groups, ["members"])
        decode.assert_called_once()

    @patch("platform_api.auth._jwk_client", return_value=FakeJwkClient())
    @patch("platform_api.auth.get_settings", return_value=cognito_settings())
    @patch("platform_api.auth.jwt.decode")
    def test_non_id_token_is_rejected(
        self,
        decode,
        _settings,
        _client,
    ):
        decode.return_value = {
            "sub": "user-123",
            "token_use": "access",
            "cognito:groups": [],
        }
        with self.assertRaises(HTTPException) as raised:
            decode_identity("Bearer signed-token")
        self.assertEqual(raised.exception.status_code, 401)

    def test_forged_jwt_subject_does_not_change_rate_limit_bucket(self):
        request_one = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (b"authorization", b"Bearer forged-subject-one"),
                (b"x-forwarded-for", b"203.0.113.9"),
            ],
            "client": ("172.20.0.5", 1234),
        })
        request_two = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [
                (b"authorization", b"Bearer forged-subject-two"),
                (b"x-forwarded-for", b"203.0.113.9"),
            ],
            "client": ("172.20.0.5", 5678),
        })
        self.assertEqual(rate_limit_key(request_one), rate_limit_key(request_two))

    def test_owner_receives_full_current_entitlements(self):
        owner = SimpleNamespace(
            is_owner=True,
            subscription_status="inactive",
            plan="free",
        )
        entitlements = entitlements_for(owner)
        self.assertEqual(effective_plan(owner), "owner")
        self.assertTrue(entitlements.ai_recommendations)
        self.assertTrue(entitlements.detailed_ai_reports)
        self.assertTrue(entitlements.personalized_recommendations)

    def test_free_member_is_limited_to_five_stocks(self):
        member = SimpleNamespace(
            is_owner=False,
            subscription_status="inactive",
            plan="free",
        )
        self.assertEqual(
            enforce_scan_limit(member, 5, mode="manual").manual_stock_limit,
            5,
        )
        with self.assertRaises(HTTPException) as raised:
            enforce_scan_limit(member, 6, mode="manual")
        self.assertEqual(raised.exception.status_code, 403)

    def test_free_member_cannot_use_ai_recommendations(self):
        member = SimpleNamespace(
            is_owner=False,
            subscription_status="inactive",
            plan="free",
        )
        with self.assertRaises(HTTPException) as raised:
            enforce_scan_limit(member, 5, mode="recommendations")
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(
            raised.exception.detail["code"],
            "ai_recommendations_required",
        )

    def test_inactive_paid_plan_falls_back_to_free(self):
        member = SimpleNamespace(
            is_owner=False,
            subscription_status="inactive",
            plan="premium",
        )
        self.assertEqual(effective_plan(member), "free")

    def test_active_premium_member_receives_personalization(self):
        member = SimpleNamespace(
            is_owner=False,
            subscription_status="active",
            plan="premium",
        )
        entitlements = entitlements_for(member)
        self.assertTrue(entitlements.ai_recommendations)
        self.assertTrue(entitlements.detailed_ai_reports)
        self.assertTrue(entitlements.personalized_recommendations)

    def test_active_pro_member_has_limited_recommendations_without_detail(self):
        member = SimpleNamespace(
            is_owner=False,
            subscription_status="active",
            plan="pro",
        )
        entitlements = entitlements_for(member)
        self.assertTrue(entitlements.ai_recommendations)
        self.assertEqual(entitlements.weekly_ai_recommendation_limit, 5)
        self.assertFalse(entitlements.detailed_ai_reports)

    def test_free_payload_does_not_expose_ai_report(self):
        member = SimpleNamespace(
            is_owner=False,
            subscription_status="inactive",
            plan="free",
        )
        payload = {
            "Alpha Score": 70,
            "AI Analysis": "English report",
            "AI Analysis (KO)": "한국어 리포트",
        }
        filtered = filter_recommendation_payload(member, payload)
        self.assertNotIn("AI Analysis", filtered)
        self.assertNotIn("AI Analysis (KO)", filtered)

    def test_pro_payload_does_not_expose_premium_ai_detail(self):
        member = SimpleNamespace(
            is_owner=False,
            subscription_status="active",
            plan="pro",
        )
        payload = {
            "Alpha Score": 70,
            "AI Analysis": "English report",
            "AI Analysis (KO)": "한국어 리포트",
        }
        filtered = filter_recommendation_payload(member, payload)
        self.assertNotIn("AI Analysis", filtered)
        self.assertNotIn("AI Analysis (KO)", filtered)


if __name__ == "__main__":
    unittest.main()
