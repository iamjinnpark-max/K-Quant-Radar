import assert from "node:assert/strict";
import { test } from "node:test";

process.env.DATABASE_URL ||= "postgresql://test:test@localhost/test";
process.env.REDIS_URL ||= "redis://localhost:6379/9";

const { hashPassword, verifyPassword } = await import("../src/password.js");

test("hash round-trips and never stores plaintext", async () => {
  const hash = await hashPassword("correct horse battery staple");
  assert.ok(hash.startsWith("$argon2id$"), "must be argon2id");
  assert.ok(!hash.includes("correct horse"), "plaintext must not appear in hash");
  assert.equal(await verifyPassword(hash, "correct horse battery staple"), true);
  assert.equal(await verifyPassword(hash, "wrong password entirely"), false);
});

test("two hashes of the same password differ (salted)", async () => {
  const first = await hashPassword("repeatable-password-1");
  const second = await hashPassword("repeatable-password-1");
  assert.notEqual(first, second);
});

test("verify tolerates garbage stored hashes", async () => {
  assert.equal(await verifyPassword("not-a-hash", "anything"), false);
  assert.equal(await verifyPassword("", "anything"), false);
});
