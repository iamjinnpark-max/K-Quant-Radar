# K-Quant deployment security

## Secret setup

The DART credential is never stored in application code.

For local Streamlit development:

1. Rotate any credential that previously appeared in source control.
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
3. Put the rotated credential in `secrets.toml`.

For Docker deployment:

1. Copy `.env.example` to `.env`.
2. Put the rotated credential in `.env`.
3. Set separate random values for `APP_ACCESS_PASSWORD` and
   `STREAMLIT_SERVER_COOKIE_SECRET`.
4. Point the DNS record for `DOMAIN` at the deployment server.
5. Allow inbound TCP ports 80 and 443 and UDP port 443.
6. Restrict `.env` to its owner with `chmod 600 .env`.
7. Run `make deploy-check`.
8. Run `make deploy`.

Both local secret files are excluded from Git and Docker build context.

## Platform API controls

The FastAPI platform backend adds:

- **Rate limiting** — a global default of 120 requests/minute plus a tighter
  10/minute cap on recommendation-job creation, keyed by the authenticated
  verified account identity (falling back to client IP) and stored in Redis so limits
  hold across every worker process.
- **Audit logging** — an append-only `audit_logs` table records job creation,
  job views, denied job access, and all billing actions (checkout, portal,
  subscription changes) with the acting user, resource id, client IP, and
  timestamp.

The Streamlit access-password gate fails closed when its password is missing
and throttles guessing with a process-wide, per-client-IP attempt counter and a
temporary lockout. Caddy replaces untrusted forwarding headers before they
reach Streamlit. The authenticated Next.js/FastAPI platform should remain
the primary customer-facing interface.

## First-party auth service (auth-server/)

The web platform's front door is a dedicated Node service that owns email +
password accounts directly. **This means K-Quant now stores password hashes**
(the earlier Cognito-only claim no longer applies to this flow):

- passwords are hashed with **argon2id** (OWASP parameters: m=19456, t=2,
  p=1); plaintext is never stored, logged, or returned by any endpoint;
- sessions are opaque random ids in **signed, httpOnly, Secure,
  SameSite=Lax cookies**, stored server-side in Redis with a 12h rolling and
  7-day absolute expiry — nothing auth-related is kept in localStorage; the
  cookie Max-Age and Redis TTL are re-derived from the same formula on every
  authenticated request, so browser and server expiry roll together and
  neither can outlive the absolute cap;
- **new accounts must verify their email address** (single-use, 24h,
  SHA-256-stored token) before the FastAPI private API accepts their session;
  accounts predating the verification feature are grandfathered as verified;
- self-service signup is **closed in production by default**; it opens only
  when `AUTH_ALLOW_SIGNUP` is exactly `true`;
- password-reset and verification email is sent through the SMTP relay
  configured in `.env` (any transactional provider's SMTP endpoint works);
  the auth service refuses to boot in production without `SMTP_HOST`, and
  **tokens are never logged in production** — in development without SMTP
  they are printed to the auth container log instead;
- password changes destroy **every** session for that user, and
  `POST /auth/logout-all` provides "log out everywhere";
- login is rate limited per account (5 attempts / 15 min, lockouts doubling
  15m → 30m → 60m → 2h) and per source IP, with counters in Redis;
- unknown-email logins burn a dummy argon2 verification so response timing
  does not reveal which addresses have accounts, and the reset flow answers
  identically whether or not the account exists — including when mail
  delivery fails;
- all state-changing routes require a **double-submit CSRF token**;
- every SQL statement uses parameterized placeholders;
- reset tokens are stored as SHA-256 digests, expire after 30 minutes, and
  are single-use; expired reset/verification tokens are swept hourly;
- account creation in the API layer is race-safe: simultaneous first
  requests for the same identity recover from the unique-constraint conflict
  instead of failing;
- `POST /auth/delete-account` (session + password re-entry + CSRF) deletes
  the credential row, cascaded reset/verification tokens, the application
  user record with its recommendation jobs and results, and every session;
  audit log rows are retained with the user reference nulled.

Production platform access fails closed:

- `AUTH_MODE=session` or `AUTH_MODE=cognito` is mandatory in deployment
  preflight; `disabled` is rejected;
- first-party sessions are verified independently by the API before an account
  record is loaded, and all cookie-authenticated API writes require CSRF;
- in optional Cognito mode, token signature, issuer, audience, expiry, token
  purpose, and group claims are verified;
- authenticated Free users can analyze at most five stocks per scan and never
  receive AI-report fields from the API;
- Pro and Premium entitlements require an active or trialing subscription;
- only Premium and verified owners activate personalized ranking;
- Cognito owner bypass is available only in optional Cognito mode; first-party
  accounts receive ordinary plan entitlements;
- first-party passwords are stored only as salted argon2id hashes.

## Backend protection

Deploy the Streamlit container on infrastructure you control and give users
only the HTTPS application URL. Do not distribute the repository.

The supplied container:

- runs as an unprivileged user;
- makes the root filesystem read-only at runtime;
- removes Linux capabilities;
- prevents privilege escalation;
- requires a production access password;
- limits memory, CPU usage, and process count;
- includes a health check;
- keeps Streamlit port 8501 private to the container network;
- terminates public HTTPS through Caddy;
- sends HSTS, clickjacking, MIME-sniffing, referrer, and permissions headers;
- makes application files non-writable.

Every container build runs `python scripts/security_check.py` and fails if a
local secret file or hardcoded sensitive Python variable is found. Run that
command manually before publishing any release.

`make deploy-check` additionally verifies that:

- Docker is installed;
- `.env` exists and has owner-only permissions;
- required values are present and are not example placeholders;
- passwords and cookie secrets meet minimum lengths and differ;
- `DOMAIN` is a valid hostname;
- `AUTH_ALLOW_SIGNUP`, when set, is exactly `true` or `false`;
- session-mode deployments configure `SMTP_HOST` and `MAIL_FROM` so reset
  and verification email can actually be delivered;
- Docker Compose accepts the production configuration.

The check reports only the failed requirement and never prints secret values.

An administrator who controls the host or receives the source/container image
can still copy or replace the code. No source-level mechanism can prevent that.
Use access-controlled hosting and restrict production shell access.
