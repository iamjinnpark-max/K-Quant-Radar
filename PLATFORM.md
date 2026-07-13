# K-Quant platform architecture

## Architecture decision

The launch architecture is:

```text
Browser
  -> Caddy / cloud load balancer
      -> Next.js frontend
      -> first-party auth service
          -> signed httpOnly cookie + Redis session
      -> FastAPI API
          -> PostgreSQL
          -> Stripe Checkout + webhooks
          -> Redis queue
              -> Celery quant worker
                  -> KRX, DART, and news sources
```

The scan is intentionally asynchronous. FastAPI creates a job and returns
HTTP 202; the worker runs the existing quant engine; PostgreSQL persists job
state and ranked results; the frontend polls the job resource.

## Cloud judgment

Use AWS first, not AWS and GCP simultaneously.

The always-on Celery worker and private Redis/PostgreSQL dependencies map
cleanly to:

- ECS Fargate: Next.js, FastAPI, and worker services;
- RDS PostgreSQL: encrypted, private database with automated backups;
- ElastiCache Redis: private Celery broker;
- Application Load Balancer and ACM: routing and TLS;
- Cognito: user authentication and JWT issuance;
- Secrets Manager: DART and application secrets;
- CloudWatch: logs, alarms, and worker monitoring;
- ECR and GitHub Actions: image registry and CI/CD.

GCP Cloud Run is attractive for stateless HTTP containers, but the
continuously running Celery worker and private broker make an all-Cloud-Run
design awkward. Supporting both clouds before product-market fit doubles
infrastructure, security, and incident-response work without helping users.

## Accounts, storage, and subscriptions

Production authentication defaults to the first-party auth service. It stores
only salted argon2id password hashes and keeps opaque sessions in Redis. The API
verifies the same signed session before loading the application account:

- stable auth subject ID and email/display name;
- owner flag and plan;
- Stripe customer ID and subscription status;
- each user's recommendation jobs and ranked results.

For the default first-party flow:

1. Generate a unique `AUTH_COOKIE_SECRET` of at least 32 characters.
2. Set `AUTH_MODE=session`; never use `disabled` on a public host.
3. Decide whether self-service signup is allowed with `AUTH_ALLOW_SIGNUP`.
4. Configure a transactional mail provider before enabling password-reset
   emails for a public launch.

Cognito remains an optional alternative. To use it:

1. Create a Cognito user pool and public app client with authorization-code
   flow and PKCE. Do not create a client secret for the browser app.
2. Add `https://YOUR_DOMAIN` as the sign-in and sign-out callback URL.
3. Create a Cognito group named exactly `owners`.
4. Create your own Cognito account and add it to `owners`. Owner accounts have
   permanent access and are never sent to Stripe Checkout. Do not put your
   username, password, or email address in source code or send them to another
   person for setup; group membership in Cognito is the only owner marker.
5. Create a recurring Stripe Price and configure a Stripe webhook endpoint at
   `https://YOUR_DOMAIN/api/v1/billing/webhook`. Subscribe it to
   `customer.subscription.created`, `customer.subscription.updated`, and
   `customer.subscription.deleted`.
6. Put the Cognito identifiers in the deployment secret store, set
   `AUTH_MODE=cognito`, then rebuild the frontend image. Add Stripe identifiers
   and secrets only when billing is ready. Values whose names begin with
   `NEXT_PUBLIC_` are public configuration; Stripe keys and the webhook secret
   remain server-side only.

`AUTH_MODE=disabled` is intentionally a localhost-only development mode. It
creates a synthetic owner identity so the builder can work without paying or
signing in. Never deploy publicly with authentication disabled.

The default `AUTH_MODE=session` uses the first-party auth service
(`auth-server/`) instead of Cognito. Its production requirements:

1. Set `AUTH_COOKIE_SECRET` (>= 32 random chars) in the deployment secret
   store.
2. Configure an SMTP relay (`SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURE`,
   `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM`). Password-reset and
   email-verification tokens are delivered only by email; the auth container
   refuses to boot in production without `SMTP_HOST`, and tokens are never
   written to logs in production.
3. Decide whether self-service signup is open. It is closed by default in
   production; set `AUTH_ALLOW_SIGNUP=true` explicitly to open it.
4. New accounts must verify their email address before the private API
   accepts their session. Sessions roll on activity (12h idle window) up to
   a 7-day absolute maximum, enforced identically by the browser cookie and
   the Redis record.
5. Users can delete their own account (`POST /auth/delete-account`, password
   re-entry required). This removes the credential row, the application user
   record, all recommendation jobs/results, outstanding tokens, and every
   session; audit rows are kept with the user reference nulled.

### Bootstrapping your own account (session mode)

Database migrations run automatically and idempotently at container start
(Alembic for the API tables, guarded SQL for the auth tables). The permanent
"owner" bypass exists only in Cognito mode, where it is derived from the
`owners` group on every request. For first-party accounts, grant yourself a
plan directly after signing up:

```bash
docker compose -f compose.platform.yaml exec postgres \
  psql -U kquant -d kquant -c \
  "UPDATE users SET plan = 'premium', subscription_status = 'active' \
   WHERE email = 'you@example.com';"
```

Sign up (and verify your email) once first so the `users` row exists. Keep
`AUTH_ALLOW_SIGNUP=false` afterwards if the platform should stay invite-only.

The product tiers are enforced by the API:

- **Free:** up to five stocks per scan, core metrics, and original sources;
- **Pro:** unlimited scan runs (up to 60 stocks per run) and AI reports;
- **Premium:** Pro features plus personalized recommendations;
- **Owner:** current implemented features without payment.

Portfolio analysis and real-time alerts are presented as upcoming Premium
features. They are not marked available in API entitlements until their
storage, delivery, and user controls are implemented.

## Required before public launch

- Add infrastructure-level quotas/WAF rules appropriate to expected traffic.
- Add retention rules for profile and recommendation data (self-service
  account deletion is implemented; scheduled retention sweeps are not).
- Add terms, privacy policy, and explicit non-advice disclosures.
- Add Sentry or OpenTelemetry tracing plus CloudWatch alarms.
- Add database backups and a tested restore procedure.
- Run dependency, container, and infrastructure security scans in CI.

Authentication, per-user job ownership, plan entitlements, and owner bypass
are implemented. Stripe still needs separate prices for Pro and Premium before
paid plan assignment is production-ready. The remaining items above still make
this a private beta foundation rather than a finished public financial product.
