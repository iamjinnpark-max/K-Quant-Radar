const required = (name) => {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
};

const isProduction = process.env.NODE_ENV === "production";

const cookieSecret = process.env.AUTH_COOKIE_SECRET || "";
if (isProduction && cookieSecret.length < 32) {
  // Fail closed: a guessable signing secret would let anyone forge the
  // session cookie's signature wrapper.
  throw new Error("AUTH_COOKIE_SECRET must be set (>= 32 chars) in production");
}

// Self-service signup is opt-in for production deployments: an operator must
// set AUTH_ALLOW_SIGNUP=true explicitly. Development keeps the permissive
// default so the flow can be exercised locally.
const allowSignup = isProduction
  ? process.env.AUTH_ALLOW_SIGNUP === "true"
  : process.env.AUTH_ALLOW_SIGNUP !== "false";

const smtpHost = process.env.SMTP_HOST || "";
if (isProduction && !smtpHost) {
  // Reset and verification tokens can only leave this service by email.
  // Without a mail path in production those flows would silently dead-end,
  // so the misconfiguration is rejected at boot instead.
  throw new Error(
    "SMTP_HOST must be set in production so reset/verification email can be delivered",
  );
}

export const config = {
  isProduction,
  port: Number(process.env.AUTH_PORT || 4000),
  databaseUrl: required("DATABASE_URL"),
  redisUrl: required("REDIS_URL"),
  cookieSecret: cookieSecret || "dev-only-cookie-secret-not-for-production",
  allowSignup,

  // Absolute base URL of the web app, used to build email links. Never
  // derived from request headers -- a spoofed Host header must not be able
  // to poison reset links.
  publicBaseUrl: (process.env.AUTH_PUBLIC_URL || "http://localhost:3000").replace(/\/+$/, ""),

  mail: {
    smtpHost,
    smtpPort: Number(process.env.SMTP_PORT || 587),
    // "true" => implicit TLS (usually port 465); otherwise STARTTLS upgrade.
    smtpSecure: process.env.SMTP_SECURE === "true",
    smtpUsername: process.env.SMTP_USERNAME || "",
    smtpPassword: process.env.SMTP_PASSWORD || "",
    from: process.env.MAIL_FROM || "K-Quant <no-reply@localhost>",
  },

  session: {
    cookieName: "kq_session",
    idleTtlSeconds: 60 * 60 * 12, // rolling: expires after 12h of inactivity
    absoluteTtlSeconds: 60 * 60 * 24 * 7, // hard cap regardless of activity
  },

  csrf: {
    cookieName: "kq_csrf",
    headerName: "x-csrf-token",
  },

  loginRateLimit: {
    // Requirement: max 5 attempts per account per 15 minutes, with backoff.
    accountMaxAttempts: 5,
    accountWindowSeconds: 15 * 60,
    // A shared office/NAT IP legitimately serves many users, so the IP cap
    // is looser than the per-account cap while still stopping wide sprays.
    ipMaxAttempts: 20,
    ipWindowSeconds: 15 * 60,
    baseLockoutSeconds: 15 * 60,
    maxLockoutSeconds: 60 * 60 * 2, // backoff doubles per lockout, capped at 2h
  },

  resetToken: {
    ttlSeconds: 30 * 60,
  },

  verificationToken: {
    ttlSeconds: 60 * 60 * 24, // a signup verification link is good for 24h
  },

  tokenCleanup: {
    intervalSeconds: 60 * 60, // sweep expired reset/verification rows hourly
  },

  password: {
    minLength: 10,
    maxLength: 256,
  },
};
