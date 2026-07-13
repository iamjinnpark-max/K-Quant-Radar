import { createClient } from "redis";

import { config } from "./config.js";

export const redis = createClient({ url: config.redisUrl });

redis.on("error", (error) => {
  // Never include command arguments here -- they can carry session ids.
  console.error("redis error:", error.message);
});

export async function connectRedis() {
  if (!redis.isOpen) {
    await redis.connect();
  }
  return redis;
}

export async function closeRedis() {
  if (redis.isOpen) {
    await redis.quit();
  }
}
