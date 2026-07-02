"use client";

import { authEnabled, login } from "@/lib/auth";

export default function LoginPage() {
  return (
    <main className="login-page">
      <section className="login-card">
        <div className="brand-mark">KQ</div>
        <p className="eyebrow">K-QUANT PLATFORM</p>
        <h1>Research the market with a system.</h1>
        <p>
          Sign in securely to save profiles, run personalized scans, and
          revisit every stock analysis.
        </p>
        <button
          className="submit"
          onClick={() => authEnabled ? login() : location.assign("/")}
        >
          {authEnabled ? "Continue to secure sign in" : "Enter local workspace"}
        </button>
        <small>
          Authentication is handled by Amazon Cognito. K-Quant never stores
          your password in its database.
        </small>
      </section>
    </main>
  );
}
