import hmac
import os
import secrets
import threading
import time

import streamlit as st


# Brute-force throttling for the shared access password. Session state is
# per-browser, so a determined attacker can reset the counter by opening a new
# session; this raises the cost of online guessing but is not a substitute for
# IP-level rate limiting at the reverse proxy (Caddy) in front of Streamlit.
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60


class _AttemptStore:
    """Process-wide attempt tracking shared by all Streamlit sessions."""

    def __init__(self):
        self.lock = threading.Lock()
        self.records: dict[str, tuple[int, float, float]] = {}


@st.cache_resource
def _attempt_store() -> _AttemptStore:
    return _AttemptStore()


def _get_secret(name: str):
    value = os.getenv(name)
    if value:
        return value

    try:
        return st.secrets.get(name)
    except (FileNotFoundError, KeyError, AttributeError):
        return None


def _client_key() -> str:
    """Use the Caddy-supplied client IP, with a session fallback for local use."""
    try:
        forwarded = st.context.headers.get("X-Forwarded-For", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
    except (AttributeError, KeyError):
        pass

    if "auth_client_key" not in st.session_state:
        st.session_state["auth_client_key"] = secrets.token_urlsafe(24)
    return f"session:{st.session_state['auth_client_key']}"


def _locked_remaining(client_key: str) -> int:
    now = time.monotonic()
    store = _attempt_store()
    with store.lock:
        attempts, locked_until, _ = store.records.get(
            client_key,
            (0, 0.0, now),
        )
        if locked_until <= now:
            if attempts:
                store.records[client_key] = (attempts, 0.0, now)
            else:
                store.records.pop(client_key, None)
            return 0
        return max(1, int(locked_until - now))


def _record_failure(client_key: str) -> int:
    now = time.monotonic()
    store = _attempt_store()
    with store.lock:
        attempts, locked_until, _ = store.records.get(
            client_key,
            (0, 0.0, now),
        )
        if locked_until > now:
            return max(1, int(locked_until - now))

        attempts += 1
        if attempts >= _MAX_ATTEMPTS:
            locked_until = now + _LOCKOUT_SECONDS
            attempts = 0
        store.records[client_key] = (attempts, locked_until, now)

        # Bound memory if a public client intentionally rotates addresses.
        if len(store.records) > 10_000:
            stale_before = now - max(_LOCKOUT_SECONDS * 2, 300)
            store.records = {
                key: record
                for key, record in store.records.items()
                if record[1] > now or record[2] > stale_before
            }
        return max(0, int(locked_until - now))


def _clear_failures(client_key: str) -> None:
    store = _attempt_store()
    with store.lock:
        store.records.pop(client_key, None)


def require_access_password():
    expected_password = _get_secret("APP_ACCESS_PASSWORD")
    if not expected_password:
        st.error(
            "Access is disabled because APP_ACCESS_PASSWORD is not configured."
        )
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("K-Quant")
    st.caption("Enter the platform access password.")

    client_key = _client_key()
    remaining = _locked_remaining(client_key)
    if remaining:
        st.error(f"Too many attempts. Try again in {remaining}s.")
        st.stop()

    supplied_password = st.text_input(
        "Password",
        type="password",
        autocomplete="current-password",
    )

    if st.button("Sign in"):
        if hmac.compare_digest(supplied_password, expected_password):
            st.session_state["authenticated"] = True
            _clear_failures(client_key)
            st.rerun()
        else:
            lockout = _record_failure(client_key)
            if lockout:
                st.error(
                    f"Too many attempts. Locked for {_LOCKOUT_SECONDS}s."
                )
            else:
                st.error("Invalid password.")

    st.stop()
