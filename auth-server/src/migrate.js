import { pool } from "./db.js";

// Idempotent bootstrap migrations, applied at startup. This service owns
// only its own auth_* tables; the FastAPI/Alembic world owns everything else.
const MIGRATIONS = [
  `CREATE TABLE IF NOT EXISTS auth_users (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     email VARCHAR(320) NOT NULL UNIQUE,
     password_hash TEXT NOT NULL,
     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
     updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
   )`,
  `CREATE TABLE IF NOT EXISTS auth_password_resets (
     id BIGSERIAL PRIMARY KEY,
     user_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
     token_hash CHAR(64) NOT NULL UNIQUE,
     expires_at TIMESTAMPTZ NOT NULL,
     created_at TIMESTAMPTZ NOT NULL DEFAULT now()
   )`,
  `CREATE INDEX IF NOT EXISTS ix_auth_password_resets_user_id
     ON auth_password_resets (user_id)`,
  `CREATE TABLE IF NOT EXISTS auth_email_verifications (
     id BIGSERIAL PRIMARY KEY,
     user_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
     token_hash CHAR(64) NOT NULL UNIQUE,
     expires_at TIMESTAMPTZ NOT NULL,
     created_at TIMESTAMPTZ NOT NULL DEFAULT now()
   )`,
  `CREATE INDEX IF NOT EXISTS ix_auth_email_verifications_user_id
     ON auth_email_verifications (user_id)`,
];

async function addEmailVerifiedColumn() {
  const existing = await pool.query(
    `SELECT 1 FROM information_schema.columns
     WHERE table_name = 'auth_users' AND column_name = 'email_verified_at'`,
  );
  if (existing.rowCount > 0) {
    return;
  }
  await pool.query(
    "ALTER TABLE auth_users ADD COLUMN email_verified_at TIMESTAMPTZ",
  );
  // Accounts that predate email verification were created when a session
  // alone granted API access; locking every existing customer out of the
  // product retroactively is not acceptable, so they are grandfathered in.
  // Every account created after this migration starts unverified.
  await pool.query(
    "UPDATE auth_users SET email_verified_at = created_at WHERE email_verified_at IS NULL",
  );
}

export async function runMigrations() {
  for (const statement of MIGRATIONS) {
    await pool.query(statement);
  }
  await addEmailVerifiedColumn();
  console.log("auth migrations applied");
}

// Expired reset/verification tokens are dead weight and a needless liability
// (their hashes outlive their usefulness). Swept hourly from index.js.
export async function cleanupExpiredTokens() {
  const resets = await pool.query(
    "DELETE FROM auth_password_resets WHERE expires_at <= now()",
  );
  const verifications = await pool.query(
    "DELETE FROM auth_email_verifications WHERE expires_at <= now()",
  );
  return {
    resetsDeleted: resets.rowCount,
    verificationsDeleted: verifications.rowCount,
  };
}

// Allow `npm run migrate` standalone.
if (import.meta.url === `file://${process.argv[1]}`) {
  await runMigrations();
  await pool.end();
}
