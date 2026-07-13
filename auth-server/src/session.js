import { randomBytes } from "node:crypto";

import { config } from "./config.js";
import { redis } from "./redis.js";

const { session: sessionConfig } = config;

const sessionKey = (sid) => `auth:sess:${sid}`;
const userSessionsKey = (userId) => `auth:usersess:${userId}`;

// The single source of truth for how long a session may live from "now":
// the 12h idle window, but never past the 7-day absolute cap measured from
// createdAt. Returns 0 when the absolute cap has passed. Both the Redis key
// TTL and the browser cookie Max-Age are derived from this so the two
// expirations can never drift apart.
export function computeSessionTtlSeconds(createdAtMs, nowMs = Date.now()) {
  const ageSeconds = (nowMs - createdAtMs) / 1000;
  const remainingAbsolute = sessionConfig.absoluteTtlSeconds - ageSeconds;
  if (remainingAbsolute <= 0) {
    return 0;
  }
  return Math.floor(Math.min(sessionConfig.idleTtlSeconds, remainingAbsolute));
}

export function sessionCookieOptions(ttlSeconds = sessionConfig.idleTtlSeconds) {
  return {
    httpOnly: true,
    secure: config.isProduction,
    sameSite: "lax",
    signed: true,
    path: "/",
    maxAge: ttlSeconds * 1000,
  };
}

// Re-issue the session cookie with the current remaining lifetime. Called on
// every authenticated request so browser expiry rolls exactly like the Redis
// key does.
export function rollSessionCookie(res, sid, createdAtMs) {
  const ttl = computeSessionTtlSeconds(createdAtMs);
  if (ttl > 0) {
    res.cookie(sessionConfig.cookieName, sid, sessionCookieOptions(ttl));
  }
}

export async function createSession(userId) {
  const sid = randomBytes(32).toString("base64url");
  const record = {
    userId,
    createdAt: Date.now(),
  };
  await redis.set(sessionKey(sid), JSON.stringify(record), {
    EX: sessionConfig.idleTtlSeconds,
  });
  await redis.sAdd(userSessionsKey(userId), sid);
  await redis.expire(userSessionsKey(userId), sessionConfig.absoluteTtlSeconds);
  return sid;
}

export async function readSession(sid) {
  if (!sid || typeof sid !== "string" || sid.length > 128) {
    return null;
  }
  const raw = await redis.get(sessionKey(sid));
  if (!raw) {
    return null;
  }

  let record;
  try {
    record = JSON.parse(raw);
  } catch {
    return null;
  }

  const ttl = computeSessionTtlSeconds(record.createdAt);
  if (ttl <= 0) {
    await destroySession(sid, record.userId);
    return null;
  }

  // Rolling idle expiry: activity extends the session, but only up to the
  // absolute cap -- the Redis TTL never outlives createdAt + absoluteTtl.
  await redis.expire(sessionKey(sid), ttl);
  return record;
}

export async function destroySession(sid, userId) {
  await redis.del(sessionKey(sid));
  if (userId) {
    await redis.sRem(userSessionsKey(userId), sid);
  }
}

export async function destroyAllSessions(userId) {
  const sids = await redis.sMembers(userSessionsKey(userId));
  if (sids.length > 0) {
    await redis.del(sids.map(sessionKey));
  }
  await redis.del(userSessionsKey(userId));
  return sids.length;
}
