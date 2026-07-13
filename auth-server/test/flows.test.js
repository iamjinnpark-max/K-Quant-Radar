import assert from "node:assert/strict";
import { after, before, beforeEach, test } from "node:test";

process.env.DATABASE_URL ||= "postgresql://test:test@localhost/test";
process.env.REDIS_URL ||= "redis://localhost:6379/9";

const { buildApp } = await import("../src/app.js");
const { config } = await import("../src/config.js");
const { pool } = await import("../src/db.js");
const { redis } = await import("../src/redis.js");
const mailer = await import("../src/mailer.js");
const { cleanupExpiredTokens } = await import("../src/migrate.js");
const { createFakeDb, createFakeRedis } = await import("./fakes.js");
const { Client, startServer } = await import("./harness.js");

let db;
let fakeRedis;
let sentMail;
let server;

const DAY_MS = 24 * 60 * 60 * 1000;
const PASSWORD = "a-strong-password-1";

before(async () => {
  server = await startServer(buildApp);
});

after(async () => {
  await server.close();
});

beforeEach(() => {
  db = createFakeDb();
  fakeRedis = createFakeRedis();
  sentMail = [];
  pool.query = db.query;
  pool.connect = db.connect;
  for (const method of [
    "ping", "get", "set", "expire", "ttl", "del", "incr",
    "sAdd", "sRem", "sMembers",
  ]) {
    redis[method] = fakeRedis[method];
  }
  mailer.setTransportForTests({
    sendMail: async (message) => {
      sentMail.push(message);
    },
  });
});

const lastToken = () => {
  const match = sentMail.at(-1)?.text.match(/manually: (\S+)/);
  assert.ok(match, "expected an email containing a token");
  return match[1];
};

const sessionEntry = () => {
  const key = [...fakeRedis.store.keys()].find((k) => k.startsWith("auth:sess:"));
  assert.ok(key, "expected a live session key");
  return { key, record: JSON.parse(fakeRedis.store.get(key).value) };
};

async function signup(client, email = "user@example.com") {
  const response = await client.post("/auth/signup", { email, password: PASSWORD });
  assert.equal(response.status, 201);
  return (await response.json()).user;
}

// ---------------------------------------------------------------------------
test("signup requires email verification before the account is verified", async () => {
  const client = new Client(server.baseUrl);
  const user = await signup(client);
  assert.equal(user.emailVerified, false);
  assert.equal(sentMail.length, 1);
  assert.equal(sentMail[0].to, "user@example.com");

  const verify = await client.post("/auth/verify-email", { token: lastToken() });
  assert.equal(verify.status, 200);

  const me = await client.get("/auth/me");
  assert.equal(me.status, 200);
  assert.equal((await me.json()).user.emailVerified, true);
});

test("verification tokens are single-use and expire", async () => {
  const client = new Client(server.baseUrl);
  await signup(client);
  const token = lastToken();

  assert.equal((await client.post("/auth/verify-email", { token })).status, 200);
  assert.equal((await client.post("/auth/verify-email", { token })).status, 400);

  // An expired token is rejected and swept by cleanup.
  db.tables.verifications.push({
    user_id: "someone",
    token_hash: "x".repeat(64),
    expires_at: new Date(Date.now() - 1000),
  });
  const swept = await cleanupExpiredTokens();
  assert.equal(swept.verificationsDeleted, 1);
});

// ---------------------------------------------------------------------------
test("concurrent signups for one email produce exactly one account and no 500", async () => {
  const clients = [new Client(server.baseUrl), new Client(server.baseUrl)];
  await Promise.all(clients.map((c) => c.bootstrapCsrf()));
  const responses = await Promise.all(
    clients.map((c) =>
      c.post("/auth/signup", { email: "race@example.com", password: PASSWORD }),
    ),
  );
  const statuses = responses.map((r) => r.status).sort();
  assert.deepEqual(statuses, [201, 409]);
  assert.equal(db.tables.authUsers.size, 1);
});

// ---------------------------------------------------------------------------
test("state-changing requests without a CSRF token are rejected", async () => {
  const client = new Client(server.baseUrl);
  const response = await client.post(
    "/auth/login",
    { email: "user@example.com", password: PASSWORD },
    { csrf: false },
  );
  assert.equal(response.status, 403);
  assert.equal((await response.json()).error, "csrf");
});

// ---------------------------------------------------------------------------
test("password reset delivers by email, is single-use, and kills sessions", async () => {
  const client = new Client(server.baseUrl);
  await signup(client);
  sentMail = [];

  const forgot = await client.post("/auth/forgot-password", {
    email: "user@example.com",
  });
  assert.equal(forgot.status, 200);
  assert.equal(sentMail.length, 1);
  const token = lastToken();
  assert.ok(!token.includes("@"), "token must not be the email");

  const newPassword = "an-even-stronger-password-2";
  const reset = await client.post("/auth/reset-password", {
    token,
    password: newPassword,
  });
  assert.equal(reset.status, 200);

  // Every session died with the password change.
  assert.equal((await client.get("/auth/me")).status, 401);
  // The token cannot be replayed.
  const replay = await client.post("/auth/reset-password", {
    token,
    password: "yet-another-password-3",
  });
  assert.equal(replay.status, 400);

  // Old password no longer works; the new one does.
  const oldLogin = await client.post("/auth/login", {
    email: "user@example.com",
    password: PASSWORD,
  });
  assert.equal(oldLogin.status, 401);
  const newLogin = await client.post("/auth/login", {
    email: "user@example.com",
    password: newPassword,
  });
  assert.equal(newLogin.status, 200);
});

test("forgot-password answers identically for unknown accounts and sends nothing", async () => {
  const client = new Client(server.baseUrl);
  const response = await client.post("/auth/forgot-password", {
    email: "nobody@example.com",
  });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).ok, true);
  assert.equal(sentMail.length, 0);
});

// ---------------------------------------------------------------------------
test("session expiry rolls on activity in both Redis and the cookie", async () => {
  const client = new Client(server.baseUrl);
  await signup(client);

  const { key } = sessionEntry();
  assert.equal(await fakeRedis.ttl(key), config.session.idleTtlSeconds);

  const me = await client.get("/auth/me");
  assert.equal(me.status, 200);
  // Redis TTL was re-armed and the cookie re-issued with a matching window.
  assert.equal(await fakeRedis.ttl(key), config.session.idleTtlSeconds);
  const cookie = client.cookies.get(config.session.cookieName);
  assert.equal(cookie.maxAge, config.session.idleTtlSeconds);
});

test("rolling expiry never extends a session past the absolute cap", async () => {
  const client = new Client(server.baseUrl);
  await signup(client);

  // Age the session to one hour short of the 7-day absolute limit.
  const { key, record } = sessionEntry();
  record.createdAt = Date.now() - (config.session.absoluteTtlSeconds - 3600) * 1000;
  fakeRedis.store.get(key).value = JSON.stringify(record);

  const me = await client.get("/auth/me");
  assert.equal(me.status, 200);
  const ttl = await fakeRedis.ttl(key);
  assert.ok(ttl <= 3600 && ttl > 3500, `ttl capped at remaining hour, got ${ttl}`);
  const cookie = client.cookies.get(config.session.cookieName);
  assert.ok(
    cookie.maxAge <= 3600 && cookie.maxAge > 3500,
    `cookie follows the cap, got ${cookie.maxAge}`,
  );
});

test("a session past the absolute cap is destroyed even if Redis kept the key", async () => {
  const client = new Client(server.baseUrl);
  await signup(client);

  const { key, record } = sessionEntry();
  record.createdAt = Date.now() - 8 * DAY_MS;
  fakeRedis.store.get(key).value = JSON.stringify(record);

  assert.equal((await client.get("/auth/me")).status, 401);
  assert.equal(await fakeRedis.get(key), null);
});

// ---------------------------------------------------------------------------
test("account deletion needs the password and removes account-owned records", async () => {
  const client = new Client(server.baseUrl);
  const user = await signup(client);
  await client.post("/auth/verify-email", { token: lastToken() });
  db.tables.appUsers.set(`password:${user.id}`, true);

  const wrong = await client.post("/auth/delete-account", {
    password: "not-the-password",
  });
  assert.equal(wrong.status, 403);

  const ok = await client.post("/auth/delete-account", { password: PASSWORD });
  assert.equal(ok.status, 200);

  assert.equal(db.tables.authUsers.size, 0);
  assert.equal(db.tables.appUsers.size, 0);
  assert.equal((await client.get("/auth/me")).status, 401);
  // No lingering session keys in Redis.
  const leftover = [...fakeRedis.store.keys()].filter((k) => k.startsWith("auth:sess:"));
  assert.deepEqual(leftover, []);
});
