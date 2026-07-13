"use client";

// Client for the K-Quant auth service (auth-server/). Sessions live in an
// httpOnly cookie the browser attaches automatically -- no token ever
// touches localStorage. CSRF double-submit: fetch a token once, echo it in
// a header on every state-changing call.

export type AuthUser = {
  id: string;
  email: string;
  createdAt: string;
  emailVerified: boolean;
};

export type AuthFailure = {
  status: number;
  error: string;
  message: string;
  retryAfterSeconds?: number;
};

export class AuthError extends Error {
  failure: AuthFailure;

  constructor(failure: AuthFailure) {
    super(failure.message);
    this.failure = failure;
  }
}

let csrfToken: string | null = null;

async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) {
    return csrfToken;
  }
  const response = await fetch("/auth/csrf", { credentials: "include" });
  const body = await response.json();
  csrfToken = body.csrfToken as string;
  return csrfToken;
}

export async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("X-CSRF-Token", await ensureCsrfToken());
  }
  return fetch(input, { ...init, headers, credentials: "include" });
}

async function post<T>(path: string, payload: unknown): Promise<T> {
  const send = async () => fetch(path, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": await ensureCsrfToken(),
      },
      body: JSON.stringify(payload),
    });
  let response = await send();

  if (response.status === 403) {
    const possibleCsrfFailure = await response.clone().json().catch(() => ({}));
    if (possibleCsrfFailure.error === "csrf") {
      csrfToken = null;
      response = await send();
    }
  }

  let body: Record<string, unknown> = {};
  try {
    body = await response.json();
  } catch {
    // fall through to the generic failure below
  }

  if (!response.ok) {
    throw new AuthError({
      status: response.status,
      error: (body.error as string) || "unknown",
      message:
        (body.message as string) || "Something went wrong. Try again shortly.",
      retryAfterSeconds: body.retryAfterSeconds as number | undefined,
    });
  }
  return body as T;
}

export function loginRequest(email: string, password: string) {
  return post<{ user: AuthUser }>("/auth/login", { email, password });
}

export function signupRequest(email: string, password: string) {
  return post<{ user: AuthUser; verificationRequired?: boolean }>(
    "/auth/signup",
    { email, password },
  );
}

export function verifyEmailRequest(token: string) {
  return post<{ ok: boolean }>("/auth/verify-email", { token });
}

export function resendVerificationRequest() {
  return post<{ ok: boolean; alreadyVerified?: boolean }>(
    "/auth/resend-verification",
    {},
  );
}

export function deleteAccountRequest(password: string) {
  return post<{ ok: boolean }>("/auth/delete-account", { password });
}

export function logoutRequest() {
  return post<{ ok: boolean }>("/auth/logout", {});
}

export function forgotPasswordRequest(email: string) {
  return post<{ ok: boolean; message: string }>("/auth/forgot-password", {
    email,
  });
}

export function resetPasswordRequest(token: string, password: string) {
  return post<{ ok: boolean }>("/auth/reset-password", { token, password });
}

export async function currentUser(): Promise<AuthUser | null> {
  try {
    const response = await fetch("/auth/me", { credentials: "include" });
    if (!response.ok) {
      return null;
    }
    const body = await response.json();
    return body.user as AuthUser;
  } catch {
    return null;
  }
}
