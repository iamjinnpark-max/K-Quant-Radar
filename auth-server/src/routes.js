import { createHash, randomBytes } from "node:crypto";

import { Router } from "express";

import { config } from "./config.js";
import { issueCsrfToken, requireCsrf } from "./csrf.js";
import { pool } from "./db.js";
import { sendPasswordResetEmail, sendVerificationEmail } from "./mailer.js";
import {
  burnDummyVerification,
  hashPassword,
  verifyPassword,
} from "./password.js";
import {
  checkLoginAllowed,
  checkActionAllowed,
  recordFailedLogin,
  recordSuccessfulLogin,
} from "./ratelimit.js";
import {
  createSession,
  destroyAllSessions,
  destroySession,
  readSession,
  rollSessionCookie,
  sessionCookieOptions,
} from "./session.js";
import { normalizeEmail, validatePassword } from "./validate.js";

export const router = Router();

const GENERIC_LOGIN_ERROR = "Incorrect email or password.";

function clientIp(req) {
  // req.ip honors `trust proxy = 1`: it takes the X-Forwarded-For entry
  // appended by the one trusted hop (Caddy), not the client-controlled
  // first entry -- a spoofed XFF header cannot rotate rate-limit buckets.
  return req.ip || req.socket.remoteAddress || "unknown";
}

function publicUser(row) {
  // The password hash column must never leave this process; this is the
  // only shape any endpoint is allowed to return.
  return {
    id: row.id,
    email: row.email,
    createdAt: row.created_at,
    emailVerified: row.email_verified_at != null,
  };
}

async function currentSession(req, res) {
  const sid = req.signedCookies[config.session.cookieName];
  if (!sid) {
    return null;
  }
  const record = await readSession(sid);
  if (!record) {
    return null;
  }
  // Keep the browser cookie's expiry rolling in lockstep with the Redis
  // key: same idle window, same absolute cap.
  rollSessionCookie(res, sid, record.createdAt);
  return { sid, ...record };
}

const hashToken = (token) => createHash("sha256").update(token).digest("hex");

async function issueVerificationToken(userId) {
  const token = randomBytes(32).toString("base64url");
  // One outstanding verification token per user: a resend invalidates the
  // previous link instead of accumulating live tokens.
  await pool.query(
    "DELETE FROM auth_email_verifications WHERE user_id = $1",
    [userId],
  );
  await pool.query(
    `INSERT INTO auth_email_verifications (user_id, token_hash, expires_at)
     VALUES ($1, $2, now() + make_interval(secs => $3))`,
    [userId, hashToken(token), config.verificationToken.ttlSeconds],
  );
  return token;
}

// ---------------------------------------------------------------------------
// CSRF bootstrap -- the SPA calls this once on load, then echoes the token.
router.get("/csrf", (req, res) => {
  const token = issueCsrfToken(res);
  res.json({ csrfToken: token });
});

// ---------------------------------------------------------------------------
router.post("/signup", requireCsrf, async (req, res) => {
  if (!config.allowSignup) {
    return res.status(403).json({
      error: "signup_disabled",
      message: "Self-service signup is disabled.",
    });
  }

  const signupGate = await checkActionAllowed("signup", clientIp(req), 10, 60 * 60);
  if (!signupGate.allowed) {
    res.set("Retry-After", String(signupGate.retryAfterSeconds));
    return res.status(429).json({
      error: "rate_limited",
      message: "Too many signup attempts. Try again later.",
      retryAfterSeconds: signupGate.retryAfterSeconds,
    });
  }

  const email = normalizeEmail(req.body?.email);
  if (!email) {
    return res.status(400).json({
      error: "invalid_email",
      message: "Enter a valid email address.",
    });
  }

  const passwordCheck = validatePassword(req.body?.password);
  if (!passwordCheck.ok) {
    return res.status(400).json({
      error: "invalid_password",
      message: passwordCheck.reason,
    });
  }

  const passwordHash = await hashPassword(req.body.password);
  const result = await pool.query(
    `INSERT INTO auth_users (email, password_hash)
     VALUES ($1, $2)
     ON CONFLICT (email) DO NOTHING
     RETURNING id, email, created_at, email_verified_at`,
    [email, passwordHash],
  );

  if (result.rowCount === 0) {
    // Known enumeration trade-off: signup reveals existing accounts. Noted
    // in the security review; acceptable for an invite-scale product.
    return res.status(409).json({
      error: "email_taken",
      message: "An account with that email already exists.",
    });
  }

  const user = result.rows[0];
  const verificationToken = await issueVerificationToken(user.id);
  await sendVerificationEmail(user.email, verificationToken);

  const sid = await createSession(user.id);
  res.cookie(config.session.cookieName, sid, sessionCookieOptions());
  return res.status(201).json({
    user: publicUser(user),
    verificationRequired: true,
  });
});

// ---------------------------------------------------------------------------
router.post("/login", requireCsrf, async (req, res) => {
  const email = normalizeEmail(req.body?.email);
  const password = req.body?.password;

  if (!email || typeof password !== "string" || password.length === 0) {
    return res.status(400).json({
      error: "invalid_request",
      message: "Email and password are required.",
    });
  }

  const ip = clientIp(req);
  const gate = await checkLoginAllowed(email, ip);
  if (!gate.allowed) {
    res.set("Retry-After", String(gate.retryAfterSeconds));
    return res.status(gate.reason === "locked" ? 423 : 429).json({
      error: gate.reason,
      message:
        gate.reason === "locked"
          ? "Too many failed attempts. This account is temporarily locked."
          : "Too many attempts from this network. Try again later.",
      retryAfterSeconds: gate.retryAfterSeconds,
    });
  }

  const result = await pool.query(
    `SELECT id, email, password_hash, created_at, email_verified_at
     FROM auth_users WHERE email = $1`,
    [email],
  );

  let valid = false;
  if (result.rowCount === 1) {
    valid = await verifyPassword(result.rows[0].password_hash, password);
  } else {
    // Unknown account: burn an equivalent argon2 verification so response
    // timing does not distinguish "no such user" from "wrong password".
    await burnDummyVerification();
  }

  if (!valid) {
    const failure = await recordFailedLogin(email, ip);
    if (failure.locked) {
      res.set("Retry-After", String(failure.retryAfterSeconds));
      return res.status(423).json({
        error: "locked",
        message: "Too many failed attempts. This account is temporarily locked.",
        retryAfterSeconds: failure.retryAfterSeconds,
      });
    }
    return res.status(401).json({
      error: "invalid_credentials",
      message: GENERIC_LOGIN_ERROR,
    });
  }

  await recordSuccessfulLogin(email);
  const user = result.rows[0];
  const sid = await createSession(user.id);
  res.cookie(config.session.cookieName, sid, sessionCookieOptions());
  return res.json({ user: publicUser(user) });
});

// ---------------------------------------------------------------------------
router.get("/me", async (req, res) => {
  const session = await currentSession(req, res);
  if (!session) {
    return res.status(401).json({ error: "unauthenticated" });
  }
  const result = await pool.query(
    `SELECT id, email, created_at, email_verified_at
     FROM auth_users WHERE id = $1`,
    [session.userId],
  );
  if (result.rowCount === 0) {
    await destroySession(session.sid, session.userId);
    return res.status(401).json({ error: "unauthenticated" });
  }
  return res.json({ user: publicUser(result.rows[0]) });
});

// ---------------------------------------------------------------------------
router.post("/logout", requireCsrf, async (req, res) => {
  const session = await currentSession(req, res);
  if (session) {
    await destroySession(session.sid, session.userId);
  }
  res.clearCookie(config.session.cookieName, { path: "/" });
  return res.json({ ok: true });
});

router.post("/logout-all", requireCsrf, async (req, res) => {
  const session = await currentSession(req, res);
  if (!session) {
    return res.status(401).json({ error: "unauthenticated" });
  }
  const cleared = await destroyAllSessions(session.userId);
  res.clearCookie(config.session.cookieName, { path: "/" });
  return res.json({ ok: true, sessionsCleared: cleared });
});

// ---------------------------------------------------------------------------
router.post("/verify-email", requireCsrf, async (req, res) => {
  const token = req.body?.token;
  if (typeof token !== "string" || token.length === 0 || token.length > 128) {
    return res.status(400).json({
      error: "invalid_token",
      message: "That verification link is invalid or has expired.",
    });
  }

  // Single use: consume the token in the same statement that selects it.
  const consumed = await pool.query(
    `DELETE FROM auth_email_verifications
     WHERE token_hash = $1 AND expires_at > now()
     RETURNING user_id`,
    [hashToken(token)],
  );
  if (consumed.rowCount === 0) {
    return res.status(400).json({
      error: "invalid_token",
      message: "That verification link is invalid or has expired.",
    });
  }

  await pool.query(
    `UPDATE auth_users
     SET email_verified_at = COALESCE(email_verified_at, now()), updated_at = now()
     WHERE id = $1`,
    [consumed.rows[0].user_id],
  );
  return res.json({ ok: true });
});

router.post("/resend-verification", requireCsrf, async (req, res) => {
  const session = await currentSession(req, res);
  if (!session) {
    return res.status(401).json({ error: "unauthenticated" });
  }

  const resendGate = await checkActionAllowed(
    "resend-verify", clientIp(req), 5, 15 * 60,
  );
  if (!resendGate.allowed) {
    res.set("Retry-After", String(resendGate.retryAfterSeconds));
    return res.status(429).json({
      error: "rate_limited",
      message: "Too many verification emails requested. Try again later.",
      retryAfterSeconds: resendGate.retryAfterSeconds,
    });
  }

  const result = await pool.query(
    "SELECT id, email, email_verified_at FROM auth_users WHERE id = $1",
    [session.userId],
  );
  if (result.rowCount === 0) {
    await destroySession(session.sid, session.userId);
    return res.status(401).json({ error: "unauthenticated" });
  }
  const user = result.rows[0];
  if (user.email_verified_at != null) {
    return res.json({ ok: true, alreadyVerified: true });
  }

  const token = await issueVerificationToken(user.id);
  await sendVerificationEmail(user.email, token);
  return res.json({ ok: true });
});

// ---------------------------------------------------------------------------
router.post("/forgot-password", requireCsrf, async (req, res) => {
  const email = normalizeEmail(req.body?.email);

  // Anti-enumeration: identical response whether or not the account exists,
  // whether or not mail delivery succeeds.
  const respond = () =>
    res.json({
      ok: true,
      message: "If that account exists, a reset link has been sent.",
    });

  const resetGate = await checkActionAllowed(
    "forgot", clientIp(req), 5, 15 * 60,
  );
  if (!resetGate.allowed) {
    // Preserve the same anti-enumeration response even while throttled.
    return respond();
  }

  if (!email) {
    return respond();
  }

  const result = await pool.query(
    "SELECT id FROM auth_users WHERE email = $1",
    [email],
  );
  if (result.rowCount === 0) {
    return respond();
  }

  const token = randomBytes(32).toString("base64url");
  await pool.query(
    `INSERT INTO auth_password_resets (user_id, token_hash, expires_at)
     VALUES ($1, $2, now() + make_interval(secs => $3))`,
    [result.rows[0].id, hashToken(token), config.resetToken.ttlSeconds],
  );

  // The token reaches the user only through the mailer, which never logs it
  // in production. Delivery failure is invisible to the caller by design.
  await sendPasswordResetEmail(email, token);

  return respond();
});

router.post("/reset-password", requireCsrf, async (req, res) => {
  const token = req.body?.token;
  if (typeof token !== "string" || token.length === 0 || token.length > 128) {
    return res.status(400).json({
      error: "invalid_token",
      message: "That reset link is invalid or has expired.",
    });
  }

  const passwordCheck = validatePassword(req.body?.password);
  if (!passwordCheck.ok) {
    return res.status(400).json({
      error: "invalid_password",
      message: passwordCheck.reason,
    });
  }

  // Single use: consume the token in the same statement that selects it.
  const consumed = await pool.query(
    `DELETE FROM auth_password_resets
     WHERE token_hash = $1 AND expires_at > now()
     RETURNING user_id`,
    [hashToken(token)],
  );
  if (consumed.rowCount === 0) {
    return res.status(400).json({
      error: "invalid_token",
      message: "That reset link is invalid or has expired.",
    });
  }

  const userId = consumed.rows[0].user_id;
  const passwordHash = await hashPassword(req.body.password);
  await pool.query(
    "UPDATE auth_users SET password_hash = $1, updated_at = now() WHERE id = $2",
    [passwordHash, userId],
  );

  // Requirement: invalidate every session on password change.
  await destroyAllSessions(userId);
  // Invalidate any other outstanding reset tokens for this user too.
  await pool.query(
    "DELETE FROM auth_password_resets WHERE user_id = $1",
    [userId],
  );

  return res.json({ ok: true });
});

// ---------------------------------------------------------------------------
// Account deletion. Requires a live session AND the current password -- a
// hijacked browser tab must not be able to destroy the account silently.
// Removes the credential row (cascading reset/verification tokens), the
// application user row (cascading recommendation jobs and results via the
// FK), and every session.
router.post("/delete-account", requireCsrf, async (req, res) => {
  const session = await currentSession(req, res);
  if (!session) {
    return res.status(401).json({ error: "unauthenticated" });
  }

  const password = req.body?.password;
  if (typeof password !== "string" || password.length === 0) {
    return res.status(400).json({
      error: "password_required",
      message: "Confirm your password to delete the account.",
    });
  }

  const gate = await checkActionAllowed("delete", clientIp(req), 5, 15 * 60);
  if (!gate.allowed) {
    res.set("Retry-After", String(gate.retryAfterSeconds));
    return res.status(429).json({
      error: "rate_limited",
      message: "Too many attempts. Try again later.",
      retryAfterSeconds: gate.retryAfterSeconds,
    });
  }

  const result = await pool.query(
    "SELECT id, password_hash FROM auth_users WHERE id = $1",
    [session.userId],
  );
  if (result.rowCount === 0) {
    await destroySession(session.sid, session.userId);
    return res.status(401).json({ error: "unauthenticated" });
  }

  const valid = await verifyPassword(result.rows[0].password_hash, password);
  if (!valid) {
    return res.status(403).json({
      error: "invalid_credentials",
      message: "Incorrect password.",
    });
  }

  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    // The application user row lives in the Alembic-owned `users` table,
    // keyed by the composite subject this service presents to the API.
    // Deleting it cascades recommendation jobs and ranked results; audit
    // log rows are retained with user_id set to NULL (they contain no
    // account-identifying detail beyond that id).
    const appTable = await client.query("SELECT to_regclass('public.users') AS t");
    if (appTable.rows[0].t) {
      await client.query(
        "DELETE FROM users WHERE cognito_sub = $1",
        [`password:${session.userId}`],
      );
    }
    // Cascades auth_password_resets and auth_email_verifications.
    await client.query("DELETE FROM auth_users WHERE id = $1", [session.userId]);
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }

  await destroyAllSessions(session.userId);
  res.clearCookie(config.session.cookieName, { path: "/" });
  return res.json({ ok: true });
});
