import { buildApp } from "./app.js";
import { config } from "./config.js";
import { cleanupExpiredTokens, runMigrations } from "./migrate.js";
import { warmDummyHash } from "./password.js";
import { connectRedis } from "./redis.js";

const app = buildApp();

await connectRedis();
await runMigrations();
await warmDummyHash();

// Sweep expired reset/verification tokens at boot and then hourly. The
// tokens are already unusable (every consumer checks expires_at); this keeps
// dead hashes from accumulating in the tables.
async function sweepTokens() {
  try {
    const { resetsDeleted, verificationsDeleted } = await cleanupExpiredTokens();
    if (resetsDeleted || verificationsDeleted) {
      console.log(
        `token sweep: removed ${resetsDeleted} reset, ${verificationsDeleted} verification token(s)`,
      );
    }
  } catch (error) {
    console.error("token sweep failed:", error.message);
  }
}

await sweepTokens();
setInterval(sweepTokens, config.tokenCleanup.intervalSeconds * 1000).unref();

app.listen(config.port, "0.0.0.0", () => {
  console.log(`kquant-auth listening on :${config.port}`);
});
