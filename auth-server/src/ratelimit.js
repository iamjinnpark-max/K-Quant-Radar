import { createHash } from "node:crypto";

import { config } from "./config.js";
import { redis } from "./redis.js";

const { loginRateLimit: limits } = config;

// Raw emails and IPs never become Redis key material directly; hashing
// keeps the keyspace uniform and keeps PII out of Redis key listings.
export function bucketKey(kind, value) {
  const digest = createHash("sha256").update(value).digest("hex").slice(0, 32);
  return `auth:rl:${kind}:${digest}`;
}

async function bumpCounter(key, windowSeconds) {
  const count = await redis.incr(key);
  if (count === 1) {
    await redis.expire(key, windowSeconds);
  }
  return count;
}

export function nextLockoutSeconds(previousLockouts) {
  // Backoff: 15m, 30m, 60m, capped at maxLockoutSeconds.
  const scaled = limits.baseLockoutSeconds * 2 ** previousLockouts;
  return Math.min(scaled, limits.maxLockoutSeconds);
}

async function lockAccount(accountKey) {
  const lockCountKey = `${accountKey}:lockcount`;
  const previousLockouts = Number((await redis.get(lockCountKey)) || 0);
  const lockSeconds = nextLockoutSeconds(previousLockouts);

  await redis.set(`${accountKey}:locked`, "1", { EX: lockSeconds });
  // Remember escalation for 24h so repeated lockouts back off harder.
  await redis.set(lockCountKey, String(previousLockouts + 1), {
    EX: 60 * 60 * 24,
  });
  return lockSeconds;
}

export async function checkLoginAllowed(email, ip) {
  const accountKey = bucketKey("acct", email);
  const ipKey = bucketKey("ip", ip);

  const lockTtl = await redis.ttl(`${accountKey}:locked`);
  if (lockTtl > 0) {
    return { allowed: false, reason: "locked", retryAfterSeconds: lockTtl };
  }

  const ipCount = Number((await redis.get(ipKey)) || 0);
  if (ipCount >= limits.ipMaxAttempts) {
    const ttl = await redis.ttl(ipKey);
    return {
      allowed: false,
      reason: "rate_limited",
      retryAfterSeconds: Math.max(ttl, 1),
    };
  }

  return { allowed: true };
}

export async function recordFailedLogin(email, ip) {
  const accountKey = bucketKey("acct", email);
  const ipKey = bucketKey("ip", ip);

  await bumpCounter(ipKey, limits.ipWindowSeconds);
  const attempts = await bumpCounter(accountKey, limits.accountWindowSeconds);

  if (attempts >= limits.accountMaxAttempts) {
    await redis.del(accountKey);
    const lockSeconds = await lockAccount(accountKey);
    return { locked: true, retryAfterSeconds: lockSeconds };
  }

  return {
    locked: false,
    attemptsRemaining: limits.accountMaxAttempts - attempts,
  };
}

export async function recordSuccessfulLogin(email) {
  const accountKey = bucketKey("acct", email);
  // A correct password clears the failure counter but NOT an active lock
  // and NOT the escalation history -- an attacker who eventually guesses
  // right during a spray should not be able to reset the backoff ladder.
  await redis.del(accountKey);
}

export async function checkActionAllowed(action, ip, maxAttempts, windowSeconds) {
  const key = bucketKey(action, ip);
  const current = Number((await redis.get(key)) || 0);
  if (current >= maxAttempts) {
    return { allowed: false, retryAfterSeconds: Math.max(await redis.ttl(key), 1) };
  }
  await bumpCounter(key, windowSeconds);
  return { allowed: true };
}
