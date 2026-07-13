import assert from "node:assert/strict";
import { test } from "node:test";

process.env.DATABASE_URL ||= "postgresql://test:test@localhost/test";
process.env.REDIS_URL ||= "redis://localhost:6379/9";

const { normalizeEmail, validatePassword } = await import("../src/validate.js");

test("normalizeEmail lowercases and trims", () => {
  assert.equal(normalizeEmail("  User@Example.COM "), "user@example.com");
});

test("normalizeEmail rejects malformed addresses", () => {
  for (const bad of [
    "",
    "plainaddress",
    "no@dot",
    "two@@example.com",
    "spaces in@example.com",
    "a@b." + "x".repeat(400),
    42,
    null,
    undefined,
    { email: "a@b.com" },
  ]) {
    assert.equal(normalizeEmail(bad), null, `should reject: ${String(bad)}`);
  }
});

test("validatePassword enforces minimum length", () => {
  assert.equal(validatePassword("short").ok, false);
  assert.equal(validatePassword("long-enough-password").ok, true);
});

test("validatePassword rejects common passwords case-insensitively", () => {
  assert.equal(validatePassword("Password123").ok, false);
  assert.equal(validatePassword("qwertyuiop").ok, false);
});

test("validatePassword rejects oversized input", () => {
  assert.equal(validatePassword("x".repeat(500)).ok, false);
});

test("validatePassword rejects non-strings without crashing", () => {
  assert.equal(validatePassword(null).ok, false);
  assert.equal(validatePassword(12345678901).ok, false);
  assert.equal(validatePassword(["a-long-enough-array"]).ok, false);
});
