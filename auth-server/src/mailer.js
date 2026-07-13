import nodemailer from "nodemailer";

import { config } from "./config.js";

// All account email (password reset, address verification) leaves through
// this module and nowhere else. Invariants:
//   - in production a token is NEVER written to any log, only to the mail
//     provider; if delivery fails we log the failure without the token;
//   - in development, when no SMTP host is configured, the token is printed
//     so the flow can be exercised without a mail account;
//   - recipient handling never changes the HTTP response shape, so mail
//     behavior cannot become an account-enumeration oracle.

let transport = null;

function getTransport() {
  if (transport) {
    return transport;
  }
  if (!config.mail.smtpHost) {
    return null;
  }
  transport = nodemailer.createTransport({
    host: config.mail.smtpHost,
    port: config.mail.smtpPort,
    secure: config.mail.smtpSecure,
    auth: config.mail.smtpUsername
      ? { user: config.mail.smtpUsername, pass: config.mail.smtpPassword }
      : undefined,
  });
  return transport;
}

// Tests inject a capturing fake here; production code never calls this.
export function setTransportForTests(fake) {
  transport = fake;
}

async function deliver(kind, email, subject, text) {
  const active = getTransport();
  if (!active) {
    if (config.isProduction) {
      // Boot-time config validation should make this unreachable, but if a
      // transport ever goes missing we still refuse to leak the token.
      console.error(`mail: no transport configured; ${kind} email not sent`);
      return false;
    }
    // Development fallback: print the message body (which contains the
    // token) so the flow can be completed locally.
    console.log(`[dev] ${kind} email for ${email}:\n${text}`);
    return true;
  }

  try {
    await active.sendMail({
      from: config.mail.from,
      to: email,
      subject,
      text,
    });
    return true;
  } catch (error) {
    // Never include the message body or token here.
    console.error(`mail: ${kind} delivery failed: ${error.message}`);
    return false;
  }
}

export async function sendPasswordResetEmail(email, token) {
  const link = `${config.publicBaseUrl}/login?mode=reset&token=${token}`;
  return deliver(
    "password-reset",
    email,
    "Reset your K-Quant password",
    [
      "A password reset was requested for your K-Quant account.",
      "",
      `Reset link (valid for ${Math.round(config.resetToken.ttlSeconds / 60)} minutes, single use):`,
      link,
      "",
      `If the link does not open, enter this reset code manually: ${token}`,
      "",
      "If you did not request this, you can ignore this email.",
    ].join("\n"),
  );
}

export async function sendVerificationEmail(email, token) {
  const link = `${config.publicBaseUrl}/login?mode=verify&token=${token}`;
  return deliver(
    "verification",
    email,
    "Verify your K-Quant email address",
    [
      "Welcome to K-Quant. Confirm this email address to activate your account.",
      "",
      `Verification link (valid for ${Math.round(config.verificationToken.ttlSeconds / 3600)} hours):`,
      link,
      "",
      `If the link does not open, enter this verification code manually: ${token}`,
      "",
      "If you did not create this account, you can ignore this email.",
    ].join("\n"),
  );
}
