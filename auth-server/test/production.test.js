import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { promisify } from "node:util";
import { test } from "node:test";

// config.js resolves its environment once at import, so production behavior
// is asserted in child processes with a controlled environment.

const run = promisify(execFile);
const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const PROD_ENV = {
  NODE_ENV: "production",
  DATABASE_URL: "postgresql://test:test@localhost/test",
  REDIS_URL: "redis://localhost:6379/9",
  AUTH_COOKIE_SECRET: "a".repeat(48),
  SMTP_HOST: "smtp.example.invalid",
  MAIL_FROM: "K-Quant <no-reply@example.invalid>",
  PATH: process.env.PATH,
};

async function evalInProd(source, extraEnv = {}) {
  return run(
    process.execPath,
    ["--input-type=module", "-e", source],
    { cwd: root, env: { ...PROD_ENV, ...extraEnv } },
  );
}

test("production defaults signup to closed unless explicitly enabled", async () => {
  const source = `
    const { config } = await import("./src/config.js");
    console.log(JSON.stringify({ allowSignup: config.allowSignup }));
  `;
  const closed = await evalInProd(source);
  assert.deepEqual(JSON.parse(closed.stdout), { allowSignup: false });

  const stillClosed = await evalInProd(source, { AUTH_ALLOW_SIGNUP: "yes" });
  assert.deepEqual(JSON.parse(stillClosed.stdout), { allowSignup: false });

  const open = await evalInProd(source, { AUTH_ALLOW_SIGNUP: "true" });
  assert.deepEqual(JSON.parse(open.stdout), { allowSignup: true });
});

test("production refuses to boot without an SMTP host", async () => {
  const source = `await import("./src/config.js");`;
  await assert.rejects(
    evalInProd(source, { SMTP_HOST: "" }),
    /SMTP_HOST must be set in production/,
  );
});

test("production never logs reset or verification tokens", async () => {
  // A transport that always fails forces every logging path in the mailer;
  // none of them may contain the token.
  const source = `
    const mailer = await import("./src/mailer.js");
    mailer.setTransportForTests({
      sendMail: async () => { throw new Error("delivery down"); },
    });
    const ok = await mailer.sendPasswordResetEmail(
      "user@example.invalid",
      "SECRET-RESET-TOKEN",
    );
    await mailer.sendVerificationEmail(
      "user@example.invalid",
      "SECRET-VERIFY-TOKEN",
    );
    if (ok !== false) { throw new Error("failed delivery must report false"); }
  `;
  const { stdout, stderr } = await evalInProd(source);
  const output = stdout + stderr;
  assert.ok(!output.includes("SECRET-RESET-TOKEN"), "reset token leaked to logs");
  assert.ok(!output.includes("SECRET-VERIFY-TOKEN"), "verify token leaked to logs");
  assert.match(stderr, /delivery failed/);
});

test("development without SMTP prints the token so flows can be exercised", async () => {
  const source = `
    const mailer = await import("./src/mailer.js");
    await mailer.sendPasswordResetEmail("dev@example.invalid", "DEV-TOKEN");
  `;
  const { stdout } = await run(
    process.execPath,
    ["--input-type=module", "-e", source],
    {
      cwd: root,
      env: {
        NODE_ENV: "development",
        DATABASE_URL: "postgresql://test:test@localhost/test",
        REDIS_URL: "redis://localhost:6379/9",
        PATH: process.env.PATH,
      },
    },
  );
  assert.ok(stdout.includes("DEV-TOKEN"));
});
