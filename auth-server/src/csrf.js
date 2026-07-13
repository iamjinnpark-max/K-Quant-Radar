import { randomBytes, timingSafeEqual } from "node:crypto";

import { config } from "./config.js";

const { csrf: csrfConfig } = config;

// Double-submit token: a random value lives in a signed (but JS-readable)
// cookie, and state-changing requests must echo it in a header. A cross-site
// attacker can force the browser to SEND the cookie but cannot READ it to
// copy it into a header. SameSite=Lax on the session cookie is the first
// layer; this survives even if that attribute is ever loosened.
export function issueCsrfToken(res) {
  const token = randomBytes(32).toString("base64url");
  res.cookie(csrfConfig.cookieName, token, {
    httpOnly: false, // the client must read it to echo it back
    secure: config.isProduction,
    sameSite: "lax",
    signed: true,
    path: "/",
  });
  return token;
}

export function requireCsrf(req, res, next) {
  const cookieToken = req.signedCookies[csrfConfig.cookieName];
  const headerToken = req.get(csrfConfig.headerName);

  if (
    typeof cookieToken !== "string" ||
    typeof headerToken !== "string" ||
    cookieToken.length === 0 ||
    cookieToken.length !== headerToken.length ||
    !timingSafeEqual(Buffer.from(cookieToken), Buffer.from(headerToken))
  ) {
    return res.status(403).json({ error: "csrf", message: "Invalid CSRF token." });
  }
  return next();
}
