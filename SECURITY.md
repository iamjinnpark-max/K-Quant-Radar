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
- Docker Compose accepts the production configuration.

The check reports only the failed requirement and never prints secret values.

An administrator who controls the host or receives the source/container image
can still copy or replace the code. No source-level mechanism can prevent that.
Use access-controlled hosting and restrict production shell access.
