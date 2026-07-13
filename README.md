# K-Quant

K-Quant is a Korean-equity recommendation platform with:

- Next.js 16 frontend;
- app-style recommendation dashboard with per-stock model analysis;
- FastAPI job, account, and billing API;
- PostgreSQL persistence and Alembic migrations;
- Redis and Celery for long-running market scans;
- first-party email/password login and Stripe subscriptions;
- the existing KRX/DART/news quant engine;
- hardened, non-root Docker services.

## Local platform

The local services are:

- web: `http://127.0.0.1:3000`;
- API docs: `http://127.0.0.1:8000/api/docs`;
- PostgreSQL and Redis: private Docker networks only.

Commands:

```bash
make platform-build
make platform-local
make platform-logs
make platform-stop
```

Configure `.env` locally before running real recommendations. Never commit it.
The local Compose override binds the services to `127.0.0.1` and uses the same
cookie-based login boundary as production. Accounts are stored by the auth
service using argon2id password hashes and server-side Redis sessions with a
rolling 12-hour idle window and a 7-day absolute cap. New accounts must verify
their email address before the private API opens; in local development the
verification and password-reset tokens are printed to the auth container log
(`make platform-logs`) instead of being emailed, and self-service signup is
open. In production, signup is closed unless `AUTH_ALLOW_SIGNUP=true` and
account email (verification, password reset) is delivered through the SMTP
relay configured in `.env`. Free accounts can analyze up
to five stocks per scan, Pro adds unlimited scan runs and AI reports, and
Premium adds personalized recommendations. Portfolio analysis and real-time
alerts are shown as upcoming Premium features until those workflows ship.
Plaintext passwords and session tokens are never exposed to browser JavaScript.
Users can delete their account (password re-entry required), which removes the
credential row, application user record, scan jobs and results, and every
session.

## Architecture and deployment

See [PLATFORM.md](PLATFORM.md) for the architecture decision, AWS recommendation,
account-storage model, Cognito/Stripe setup, and remaining launch work.
See [SECURITY.md](SECURITY.md) for secret and container security requirements.

The original Streamlit application remains available as a research/admin
interface while the Next.js platform is developed.

## Streamlit Community Cloud

The redesigned Streamlit interface is contained in `app.py`, with its committed
theme in `.streamlit/config.toml`. After these files are pushed to the GitHub
branch connected to Streamlit Community Cloud, the app rebuilds from
`requirements.txt`.

Add `DART_API_KEY` and `APP_ACCESS_PASSWORD` through the Streamlit app's
**Settings → Secrets** panel. Never commit `.env` or `secrets.toml`.

Streamlit publishes the research interface only. Platform login, PostgreSQL user
accounts, Stripe subscriptions, webhooks, and the owner bypass belong to the
Next.js/FastAPI platform and require the platform deployment described in
[PLATFORM.md](PLATFORM.md).
