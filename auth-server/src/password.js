import { hash, verify } from "@node-rs/argon2";

// OWASP-recommended argon2id parameters (2024 guidance): m=19456 KiB,
// t=2, p=1. Explicit rather than library defaults so a dependency bump
// can never silently weaken stored hashes.
const ARGON2_OPTIONS = {
  memoryCost: 19456,
  timeCost: 2,
  parallelism: 1,
};

export async function hashPassword(plaintext) {
  return hash(plaintext, ARGON2_OPTIONS);
}

export async function verifyPassword(storedHash, plaintext) {
  try {
    return await verify(storedHash, plaintext);
  } catch {
    // Malformed hash in storage reads as "no match", never as a crash.
    return false;
  }
}

// Constant-cost dummy verification target. When the account does not exist
// we still burn one argon2 verification so the response time does not
// reveal which emails are registered. Generated once at boot from a random
// throwaway password.
let dummyHash = null;

export async function warmDummyHash() {
  if (!dummyHash) {
    dummyHash = await hashPassword("dummy-timing-equalizer");
  }
  return dummyHash;
}

export async function burnDummyVerification() {
  const target = await warmDummyHash();
  await verifyPassword(target, "definitely-not-the-password");
}
