import assert from "node:assert/strict";
import { test } from "node:test";

process.env.DATABASE_URL ||= "postgresql://test:test@localhost/test";
process.env.REDIS_URL ||= "redis://localhost:6379/9";

const { bucketKey, nextLockoutSeconds } = await import("../src/ratelimit.js");

test("bucketKey never embeds the raw identifier", () => {
  const email = "victim@example.com";
  const key = bucketKey("acct", email);
  assert.ok(!key.includes(email));
  assert.ok(!key.includes("victim"));
  assert.match(key, /^auth:rl:acct:[0-9a-f]{32}$/);
});

test("bucketKey is deterministic and kind-scoped", () => {
  assert.equal(bucketKey("acct", "a@b.com"), bucketKey("acct", "a@b.com"));
  assert.notEqual(bucketKey("acct", "a@b.com"), bucketKey("ip", "a@b.com"));
});

test("lockout backoff doubles and caps at two hours", () => {
  assert.equal(nextLockoutSeconds(0), 15 * 60);
  assert.equal(nextLockoutSeconds(1), 30 * 60);
  assert.equal(nextLockoutSeconds(2), 60 * 60);
  assert.equal(nextLockoutSeconds(3), 2 * 60 * 60);
  assert.equal(nextLockoutSeconds(10), 2 * 60 * 60);
});
