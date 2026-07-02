# K-Quant

K-Quant is a Korean-equity recommendation platform with:

- Next.js 16 frontend;
- app-style recommendation dashboard with per-stock model analysis;
- FastAPI job, account, and billing API;
- PostgreSQL persistence and Alembic migrations;
- Redis and Celery for long-running market scans;
- Cognito JWT login and Stripe subscriptions for production;
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
Local mode treats you as the owner and does not require payment. For production,
set `AUTH_MODE=cognito`, create the `owners` Cognito group, and add your account
to it. Other users require an active Stripe subscription to start scans.

## Architecture and deployment

See [PLATFORM.md](PLATFORM.md) for the architecture decision, AWS recommendation,
account-storage model, Cognito/Stripe setup, and remaining launch work.
See [SECURITY.md](SECURITY.md) for secret and container security requirements.

The original Streamlit application remains available as a research/admin
interface while the Next.js platform is developed.
