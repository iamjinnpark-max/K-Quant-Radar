"""Account lifecycle security tests.

Covers the concurrent-creation recovery in get_current_user, the email
verification gate and rolling/absolute session expiry enforced by
_decode_session_identity, and cross-account denial on job reads. Uses SQLite
plus fakes, so it runs without Postgres/Redis (inside the api container:
``python -m unittest tests.test_auth_accounts``).
"""

import base64
import hashlib
import hmac
import json
import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool
from starlette.requests import Request

import platform_api.auth as auth
from platform_api.database import Base
from platform_api.models import RecommendationJob, User


def make_sqlite_sessionmaker():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def make_file_sqlite_sessionmaker(path: str):
    """Separate connections per session, like Postgres gives each request.

    A shared in-memory connection would entangle the two threads'
    transactions and test an artifact instead of the real race.
    """
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def disabled_settings():
    return SimpleNamespace(auth_mode="disabled")


def http_request(cookies: str | None = None) -> Request:
    headers = []
    if cookies:
        headers.append((b"cookie", cookies.encode()))
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/v1/me",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
    })


class ConcurrentUserCreationTests(unittest.TestCase):
    def setUp(self):
        self.sessions = make_sqlite_sessionmaker()

    def test_lost_insert_race_recovers_instead_of_500(self):
        # Simulate the exact race: the SELECT misses, another request commits
        # the row before our INSERT flushes, and the unique constraint on
        # cognito_sub fires. get_current_user must recover and return the
        # winner's row.
        with self.sessions() as other:
            existing = User(
                cognito_sub="local-owner",
                email="owner@local.invalid",
                display_name="K-Quant Owner",
            )
            other.add(existing)
            other.commit()
            existing_id = existing.id

        real_select = auth._select_user
        calls = {"count": 0}

        def select_that_misses_once(session, sub):
            calls["count"] += 1
            if calls["count"] == 1:
                return None  # the losing request's stale read
            return real_select(session, sub)

        with (
            patch.object(auth, "get_settings", disabled_settings),
            patch.object(auth, "SessionLocal", self.sessions),
            patch.object(auth, "_select_user", side_effect=select_that_misses_once),
        ):
            user = auth.get_current_user(http_request(), None)

        self.assertEqual(user.id, existing_id)
        with self.sessions() as session:
            count = session.query(User).count()
        self.assertEqual(count, 1)

    def test_parallel_first_requests_create_exactly_one_user(self):
        db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_file.close()
        self.addCleanup(os.unlink, db_file.name)
        self.sessions = make_file_sqlite_sessionmaker(db_file.name)

        barrier = threading.Barrier(2)
        results, errors = [], []

        def first_request():
            barrier.wait()
            try:
                with (
                    patch.object(auth, "get_settings", disabled_settings),
                    patch.object(auth, "SessionLocal", self.sessions),
                ):
                    results.append(auth.get_current_user(http_request(), None))
            except Exception as error:  # noqa: BLE001 - the test asserts none
                errors.append(error)

        threads = [threading.Thread(target=first_request) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len({user.id for user in results}), 1)
        with self.sessions() as session:
            self.assertEqual(session.query(User).count(), 1)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expire_calls = []
        self.deleted = []

    def get(self, key):
        return self.values.get(key)

    def expire(self, key, seconds):
        self.expire_calls.append((key, seconds))

    def delete(self, key):
        self.deleted.append(key)
        self.values.pop(key, None)


def session_settings():
    return SimpleNamespace(
        auth_mode="session",
        auth_session_cookie_name="kq_session",
        auth_cookie_secret="test-cookie-secret-material-32chars",
        redis_url="redis://unused:6379/0",
        auth_session_idle_ttl_seconds=60 * 60 * 12,
        auth_session_absolute_ttl_seconds=60 * 60 * 24 * 7,
    )


def signed_cookie(sid: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), sid.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode().rstrip("=")
    return f"kq_session={quote(f's:{sid}.{signature}')}"


class SessionIdentityTests(unittest.TestCase):
    IDLE = 60 * 60 * 12
    ABSOLUTE = 60 * 60 * 24 * 7

    def setUp(self):
        self.sessions = make_sqlite_sessionmaker()
        with self.sessions() as session:
            session.execute(text(
                "CREATE TABLE auth_users ("
                "id TEXT PRIMARY KEY, email TEXT, email_verified_at TIMESTAMP)"
            ))
            session.execute(text(
                "INSERT INTO auth_users VALUES "
                "('verified-id', 'v@example.com', '2026-01-01 00:00:00'),"
                "('unverified-id', 'u@example.com', NULL)"
            ))
            session.commit()
        self.redis = FakeRedis()
        self.settings = session_settings()

    def decode(self, user_id: str, age_seconds: float = 0.0):
        sid = "test-session-id"
        self.redis.values[f"auth:sess:{sid}"] = json.dumps({
            "userId": user_id,
            "createdAt": (time.time() - age_seconds) * 1000,
        })
        request = http_request(
            signed_cookie(sid, self.settings.auth_cookie_secret)
        )
        with (
            patch.object(auth, "get_settings", lambda: self.settings),
            patch.object(auth, "_redis_client", lambda _url: self.redis),
            patch.object(auth, "SessionLocal", self.sessions),
        ):
            return auth._decode_session_identity(request)

    def test_verified_user_gets_identity_and_full_idle_window(self):
        identity = self.decode("verified-id")
        self.assertEqual(identity.sub, "password:verified-id")
        self.assertEqual(identity.email, "v@example.com")
        (_, ttl), = self.redis.expire_calls
        self.assertEqual(ttl, self.IDLE)

    def test_unverified_user_is_denied_private_api_access(self):
        with self.assertRaises(HTTPException) as raised:
            self.decode("unverified-id")
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail["code"], "email_unverified")

    def test_rolling_ttl_is_capped_by_the_absolute_limit(self):
        age = self.ABSOLUTE - 3600  # one hour of absolute life left
        self.decode("verified-id", age_seconds=age)
        (_, ttl), = self.redis.expire_calls
        self.assertLessEqual(ttl, 3600)
        self.assertGreater(ttl, 3500)

    def test_session_past_absolute_cap_is_rejected_and_deleted(self):
        with self.assertRaises(HTTPException) as raised:
            self.decode("verified-id", age_seconds=self.ABSOLUTE + 60)
        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(self.redis.deleted, ["auth:sess:test-session-id"])
        self.assertEqual(self.redis.expire_calls, [])


class CrossAccountDenialTests(unittest.TestCase):
    def setUp(self):
        self.sessions = make_sqlite_sessionmaker()
        with self.sessions() as session:
            self.owner = User(cognito_sub="password:owner", email="a@example.com")
            self.other = User(cognito_sub="password:other", email="b@example.com")
            session.add_all([self.owner, self.other])
            session.commit()
            job = RecommendationJob(
                user_id=self.owner.id,
                profile={"mode": "manual", "manual_tickers": ["005930"]},
            )
            session.add(job)
            session.commit()
            self.job_id = job.id

    def test_other_accounts_job_reads_as_404(self):
        from platform_api.main import get_job

        request = http_request()
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as raised:
                get_job(self.job_id, request, db, self.other)
            self.assertEqual(raised.exception.status_code, 404)

            # The owner still reads their own job.
            result = get_job(self.job_id, request, db, self.owner)
            self.assertEqual(result.id, self.job_id)


if __name__ == "__main__":
    unittest.main()
