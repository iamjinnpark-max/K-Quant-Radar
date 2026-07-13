import assert from "node:assert/strict";
import { test } from "node:test";

process.env.DATABASE_URL ||= "postgresql://test:test@localhost/test";
process.env.REDIS_URL ||= "redis://localhost:6379/9";

const { computeSessionTtlSeconds } = await import("../src/session.js");
const { config } = await import("../src/config.js");

const { idleTtlSeconds, absoluteTtlSeconds } = config.session;
const NOW = 1_800_000_000_000;

test("a fresh session gets the full idle window", () => {
  assert.equal(computeSessionTtlSeconds(NOW, NOW), idleTtlSeconds);
});

test("mid-life activity still gets the idle window", () => {
  const createdAt = NOW - 3 * 24 * 60 * 60 * 1000;
  assert.equal(computeSessionTtlSeconds(createdAt, NOW), idleTtlSeconds);
});

test("near the absolute cap the ttl shrinks to the remainder", () => {
  const createdAt = NOW - (absoluteTtlSeconds - 3600) * 1000;
  assert.equal(computeSessionTtlSeconds(createdAt, NOW), 3600);
});

test("past the absolute cap the ttl is zero", () => {
  const exactly = NOW - absoluteTtlSeconds * 1000;
  assert.equal(computeSessionTtlSeconds(exactly, NOW), 0);
  const past = NOW - (absoluteTtlSeconds + 1) * 1000;
  assert.equal(computeSessionTtlSeconds(past, NOW), 0);
});

test("the ttl is never negative and never exceeds the idle window", () => {
  for (const ageSeconds of [0, 1, 999, absoluteTtlSeconds - 1, absoluteTtlSeconds * 2]) {
    const ttl = computeSessionTtlSeconds(NOW - ageSeconds * 1000, NOW);
    assert.ok(ttl >= 0);
    assert.ok(ttl <= idleTtlSeconds);
  }
});
