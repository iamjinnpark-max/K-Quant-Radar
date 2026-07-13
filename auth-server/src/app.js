import cookieParser from "cookie-parser";
import express from "express";

import { config } from "./config.js";
import { pool } from "./db.js";
import { redis } from "./redis.js";
import { router } from "./routes.js";

export function buildApp() {
  const app = express();

  // Caddy terminates TLS one hop away; trust exactly that hop so
  // req.secure and X-Forwarded-For behave.
  app.set("trust proxy", 1);
  app.disable("x-powered-by");

  app.use(express.json({ limit: "16kb" }));
  app.use(cookieParser(config.cookieSecret));

  app.use((req, res, next) => {
    res.set("Cache-Control", "no-store");
    next();
  });

  app.get("/auth/health", async (req, res) => {
    try {
      await pool.query("SELECT 1");
      await redis.ping();
      res.json({ status: "ok" });
    } catch {
      res.status(503).json({ status: "degraded" });
    }
  });

  app.use("/auth", router);

  // Uniform JSON errors. The message is generic on purpose: stack traces
  // and driver errors must never reach the client. Request bodies are
  // never logged anywhere in this service -- they can contain passwords.
  // eslint-disable-next-line no-unused-vars
  app.use((error, req, res, next) => {
    console.error(`unhandled error on ${req.method} ${req.path}:`, error.stack);
    res.status(500).json({ error: "internal", message: "Something went wrong." });
  });

  return app;
}
