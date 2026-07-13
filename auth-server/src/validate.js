import { config } from "./config.js";

// Pragmatic email shape check: one @, non-empty local part, a dot in the
// domain, no whitespace. Deliverability is proven by the reset-email flow,
// not by a longer regex.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const EMAIL_MAX_LENGTH = 320;

// A tiny deny-list of the passwords that dominate credential-stuffing
// wordlists. Length is the primary control (NIST 800-63B); composition
// rules are intentionally not enforced.
const COMMON_PASSWORDS = new Set([
  "password", "password1", "password12", "password123",
  "1234567890", "12345678910", "qwertyuiop", "qwerty12345",
  "iloveyou12", "letmein123", "admin12345", "welcome123",
  "sunshine123", "monkey12345", "dragon12345", "baseball123",
]);

export function normalizeEmail(raw) {
  if (typeof raw !== "string") {
    return null;
  }
  const email = raw.trim().toLowerCase();
  if (email.length === 0 || email.length > EMAIL_MAX_LENGTH) {
    return null;
  }
  if (!EMAIL_PATTERN.test(email)) {
    return null;
  }
  return email;
}

export function validatePassword(raw) {
  if (typeof raw !== "string") {
    return { ok: false, reason: "Password is required." };
  }
  if (raw.length < config.password.minLength) {
    return {
      ok: false,
      reason: `Password must be at least ${config.password.minLength} characters.`,
    };
  }
  if (raw.length > config.password.maxLength) {
    return {
      ok: false,
      reason: `Password must be at most ${config.password.maxLength} characters.`,
    };
  }
  if (COMMON_PASSWORDS.has(raw.toLowerCase())) {
    return { ok: false, reason: "That password is too common." };
  }
  return { ok: true };
}
