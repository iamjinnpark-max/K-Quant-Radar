# K-Quant platform architecture

## Architecture decision

The launch architecture is:

```text
Browser
  -> Caddy / cloud load balancer
      -> Next.js frontend
          -> Cognito managed login
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

Production authentication uses an Amazon Cognito user pool. Cognito stores and
validates passwords; K-Quant never receives or stores them. After a valid JWT is
verified, PostgreSQL stores only the application record needed to operate the
platform:

- Cognito subject ID and email/display name;
- owner flag and plan;
- Stripe customer ID and subscription status;
- each user's recommendation jobs and ranked results.

To configure production access:

1. Create a Cognito user pool and public app client with authorization-code
   flow and PKCE. Do not create a client secret for the browser app.
2. Add `https://YOUR_DOMAIN` as the sign-in and sign-out callback URL.
3. Create a Cognito group named exactly `owners`.
4. Create your own Cognito account and add it to `owners`. Owner accounts have
   permanent access and are never sent to Stripe Checkout.
5. Create a recurring Stripe Price and configure a Stripe webhook endpoint at
   `https://YOUR_DOMAIN/api/v1/billing/webhook`. Subscribe it to
   `customer.subscription.created`, `customer.subscription.updated`, and
   `customer.subscription.deleted`.
6. Put the Cognito and Stripe identifiers/secrets in the deployment secret
   store, set `AUTH_MODE=cognito`, then rebuild the frontend image. Values whose
   names begin with `NEXT_PUBLIC_` are public configuration; Stripe keys and
   the webhook secret remain server-side only.

`AUTH_MODE=disabled` is intentionally a localhost-only development mode. It
creates a synthetic owner identity so the builder can work without paying or
signing in. Never deploy publicly with authentication disabled.

## Required before public launch

- Add per-user rate limits and quotas.
- Add retention/deletion rules for profile and recommendation data.
- Add terms, privacy policy, and explicit non-advice disclosures.
- Add Sentry or OpenTelemetry tracing plus CloudWatch alarms.
- Add database backups and a tested restore procedure.
- Run dependency, container, and infrastructure security scans in CI.

Authentication, per-user job ownership, Stripe subscription gating, and owner
bypass are implemented. The remaining items above still make this a private
beta foundation rather than a finished public financial product.
