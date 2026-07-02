#!/usr/bin/env python3
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
REQUIRED_VALUES = {
    "DART_API_KEY": 20,
    "APP_ACCESS_PASSWORD": 20,
    "STREAMLIT_SERVER_COOKIE_SECRET": 32,
    "DOMAIN": 4,
    "POSTGRES_PASSWORD": 24,
}
PLACEHOLDER_MARKERS = {
    "replace_with_your_rotated_key",
    "replace_with_a_long_random_password",
    "replace_with_a_different_random_value",
    "kquant.example.com",
    "replace_with_a_long_random_database_password",
    "replace_with_cognito_user_pool_id",
    "replace_with_cognito_app_client_id",
    "replace_with_cognito_domain",
    "replace_with_stripe_secret_key",
    "replace_with_stripe_webhook_secret",
    "replace_with_stripe_recurring_price_id",
}
DOMAIN_PATTERN = re.compile(
    r"^(?=.{4,253}$)(?!-)(?:[a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,63}$"
)


def load_env(path: Path):
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip("\"'")
    return values


def check_env_file():
    if not ENV_FILE.exists():
        return {}, [
            ".env is missing; copy .env.example and configure it locally."
        ]

    findings = []
    mode = stat.S_IMODE(ENV_FILE.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        findings.append(
            ".env permissions are too broad; set them to owner-only (0600)."
        )

    values = load_env(ENV_FILE)
    for name, minimum_length in REQUIRED_VALUES.items():
        value = values.get(name, "")
        if not value:
            findings.append(f"{name} is missing from .env.")
        elif value in PLACEHOLDER_MARKERS:
            findings.append(f"{name} still contains an example placeholder.")
        elif len(value) < minimum_length:
            findings.append(
                f"{name} is too short; use at least {minimum_length} characters."
            )

    domain = values.get("DOMAIN", "")
    if domain and domain not in PLACEHOLDER_MARKERS:
        if domain.startswith(("http://", "https://")):
            findings.append("DOMAIN must be a hostname without http:// or https://.")
        elif not DOMAIN_PATTERN.fullmatch(domain):
            findings.append("DOMAIN is not a valid public hostname.")

    password = values.get("APP_ACCESS_PASSWORD")
    cookie_secret = values.get("STREAMLIT_SERVER_COOKIE_SECRET")
    if password and cookie_secret and password == cookie_secret:
        findings.append(
            "APP_ACCESS_PASSWORD and STREAMLIT_SERVER_COOKIE_SECRET "
            "must be different."
        )

    if values.get("AUTH_MODE") == "cognito":
        production_values = {
            "COGNITO_REGION": 4,
            "COGNITO_USER_POOL_ID": 8,
            "COGNITO_APP_CLIENT_ID": 8,
            "COGNITO_DOMAIN": 8,
            "STRIPE_SECRET_KEY": 12,
            "STRIPE_WEBHOOK_SECRET": 12,
            "STRIPE_PRICE_ID": 8,
        }
        for name, minimum_length in production_values.items():
            value = values.get(name, "")
            if not value:
                findings.append(f"{name} is required when AUTH_MODE=cognito.")
            elif value in PLACEHOLDER_MARKERS:
                findings.append(f"{name} still contains an example placeholder.")
            elif len(value) < minimum_length:
                findings.append(
                    f"{name} is too short; expected at least "
                    f"{minimum_length} characters."
                )

    return values, findings


def check_command(command, label):
    if shutil.which(command):
        return []
    return [f"{label} is not installed or not available on PATH."]


def run_check(command, label, env=None):
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [f"{label} could not be executed."]

    if result.returncode != 0:
        return [f"{label} failed."]
    return []


def main():
    values, findings = check_env_file()
    findings += check_command("docker", "Docker")

    security_check = [sys.executable, "scripts/security_check.py"]
    findings += run_check(security_check, "Application security check")

    if shutil.which("docker") and values and not findings:
        environment = os.environ.copy()
        environment.update(values)
        findings += run_check(
            [
                "docker",
                "compose",
                "-f",
                "compose.platform.yaml",
                "config",
                "--quiet",
            ],
            "Platform Docker Compose configuration check",
            env=environment,
        )

    if findings:
        print("Deployment preflight failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("Deployment preflight passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
