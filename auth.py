import hmac
import os

import streamlit as st


def _get_secret(name: str):
    value = os.getenv(name)
    if value:
        return value

    try:
        return st.secrets.get(name)
    except (FileNotFoundError, KeyError, AttributeError):
        return None


def require_access_password():
    expected_password = _get_secret("APP_ACCESS_PASSWORD")
    if not expected_password:
        return

    if st.session_state.get("authenticated"):
        return

    st.title("K-Quant")
    st.caption("Enter the platform access password.")
    supplied_password = st.text_input(
        "Password",
        type="password",
        autocomplete="current-password",
    )

    if st.button("Sign in"):
        if hmac.compare_digest(supplied_password, expected_password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid password.")

    st.stop()
