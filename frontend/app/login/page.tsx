"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import {
  AuthError,
  forgotPasswordRequest,
  loginRequest,
  resendVerificationRequest,
  resetPasswordRequest,
  signupRequest,
  verifyEmailRequest,
} from "@/lib/authClient";
import { useLanguage } from "@/lib/language";
import { QuoteLoadingScreen } from "../FinanceQuotes";

const PASSWORD_MIN_LENGTH = 10;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Mode = "login" | "signup" | "forgot" | "reset" | "verify";

const COPY = {
  en: {
    eyebrow: "K-QUANT PLATFORM",
    title: "Sign in to the terminal",
    signupTitle: "Create your account",
    forgotTitle: "Reset your password",
    resetTitle: "Choose a new password",
    verifyTitle: "Verify your email",
    subtitle:
      "Sessions are held in secure, httpOnly cookies. Your password is verified with argon2id and never logged or returned by any API.",
    email: "Email",
    password: "Password",
    newPassword: "New password",
    resetToken: "Reset code",
    verifyToken: "Verification code",
    signIn: "Sign in",
    signingIn: "Signing in…",
    createAccount: "Create account",
    creating: "Creating account…",
    sendReset: "Send reset link",
    sending: "Sending…",
    setPassword: "Set new password",
    setting: "Updating…",
    verify: "Verify email",
    verifying: "Verifying…",
    resend: "Resend verification email",
    resent: "Verification email sent. Check your inbox.",
    verifyNotice:
      "We sent a verification link to your email. Enter the code here or open the link to activate your account.",
    forgot: "Forgot password?",
    backToLogin: "← Back to sign in",
    haveCode: "Already have a reset code?",
    noAccount: "New to K-Quant?",
    haveAccount: "Already have an account?",
    ssoDivider: "or continue with",
    ssoSoon: "SSO (coming soon)",
    emailInvalid: "Enter a valid email address.",
    passwordShort: `At least ${PASSWORD_MIN_LENGTH} characters.`,
    resetSent: "If that account exists, a reset link has been sent.",
    resetDone: "Password updated. Sign in with your new password.",
    landing: "← K-Quant home",
  },
  ko: {
    eyebrow: "K-QUANT PLATFORM",
    title: "터미널에 로그인",
    signupTitle: "계정 만들기",
    forgotTitle: "비밀번호 재설정",
    resetTitle: "새 비밀번호 설정",
    verifyTitle: "이메일 인증",
    subtitle:
      "세션은 httpOnly 보안 쿠키로만 유지됩니다. 비밀번호는 argon2id로 검증되며 어떤 API 응답이나 로그에도 남지 않습니다.",
    email: "이메일",
    password: "비밀번호",
    newPassword: "새 비밀번호",
    resetToken: "재설정 코드",
    verifyToken: "인증 코드",
    signIn: "로그인",
    signingIn: "로그인 중…",
    createAccount: "계정 생성",
    creating: "생성 중…",
    sendReset: "재설정 링크 보내기",
    sending: "전송 중…",
    setPassword: "비밀번호 변경",
    setting: "변경 중…",
    verify: "이메일 인증",
    verifying: "인증 중…",
    resend: "인증 메일 다시 보내기",
    resent: "인증 메일을 보냈습니다. 받은편지함을 확인하세요.",
    verifyNotice:
      "인증 링크를 이메일로 보냈습니다. 링크를 열거나 코드를 입력하면 계정이 활성화됩니다.",
    forgot: "비밀번호를 잊으셨나요?",
    backToLogin: "← 로그인으로 돌아가기",
    haveCode: "재설정 코드가 있으신가요?",
    noAccount: "처음이신가요?",
    haveAccount: "이미 계정이 있으신가요?",
    ssoDivider: "또는 다음으로 계속",
    ssoSoon: "SSO (준비 중)",
    emailInvalid: "올바른 이메일 주소를 입력하세요.",
    passwordShort: `${PASSWORD_MIN_LENGTH}자 이상이어야 합니다.`,
    resetSent: "해당 계정이 존재하면 재설정 링크가 전송되었습니다.",
    resetDone: "비밀번호가 변경되었습니다. 새 비밀번호로 로그인하세요.",
    landing: "← K-Quant 홈",
  },
} as const;

function useFieldValidation(copy: { emailInvalid: string; passwordShort: string }) {
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const validateEmail = (value: string) => {
    const error =
      value.length > 0 && !EMAIL_PATTERN.test(value) ? copy.emailInvalid : null;
    setEmailError(error);
    return error === null && value.length > 0;
  };
  const validatePassword = (value: string) => {
    const error =
      value.length > 0 && value.length < PASSWORD_MIN_LENGTH
        ? copy.passwordShort
        : null;
    setPasswordError(error);
    return error === null && value.length > 0;
  };

  return { emailError, passwordError, validateEmail, validatePassword };
}

export default function LoginPage() {
  const router = useRouter();
  const { language, setLanguage } = useLanguage();
  const copy = COPY[language];

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [verifyToken, setVerifyToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [entering, setEntering] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formNotice, setFormNotice] = useState<string | null>(null);

  const { emailError, passwordError, validateEmail, validatePassword } =
    useFieldValidation(copy);

  // Email links land here as /login?mode=reset|verify&token=…; prefill the
  // matching form so the user only has to confirm.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const linkMode = params.get("mode");
    const token = params.get("token") ?? "";
    if (linkMode === "reset") {
      setMode("reset");
      setResetToken(token);
    } else if (linkMode === "verify") {
      setMode("verify");
      setVerifyToken(token);
    }
  }, []);

  const switchMode = (next: Mode) => {
    setMode(next);
    setFormError(null);
    setFormNotice(null);
    setPassword("");
  };

  const failureMessage = (error: unknown): string => {
    if (error instanceof AuthError) {
      const { failure } = error;
      if (failure.retryAfterSeconds) {
        const minutes = Math.max(1, Math.ceil(failure.retryAfterSeconds / 60));
        return `${failure.message} (${language === "ko" ? `약 ${minutes}분 후 재시도` : `retry in ~${minutes} min`})`;
      }
      return failure.message;
    }
    return language === "ko"
      ? "네트워크 오류입니다. 잠시 후 다시 시도하세요."
      : "Network error. Try again shortly.";
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    setFormNotice(null);

    if (mode !== "reset" && mode !== "verify" && !validateEmail(email)) {
      setFormError(copy.emailInvalid);
      return;
    }
    if (mode !== "forgot" && mode !== "verify" && !validatePassword(password)) {
      setFormError(copy.passwordShort);
      return;
    }

    // After a successful sign-in, hold on a quote loading screen while the
    // dashboard route warms up, then enter the terminal.
    const enterTerminal = () => {
      setEntering(true);
      router.prefetch("/dashboard");
      setTimeout(() => router.push("/dashboard"), 3200);
    };

    setBusy(true);
    try {
      if (mode === "login") {
        const { user } = await loginRequest(email, password);
        if (user && user.emailVerified === false) {
          switchMode("verify");
          setFormNotice(copy.verifyNotice);
          return;
        }
        enterTerminal();
        return;
      } else if (mode === "signup") {
        const result = await signupRequest(email, password);
        if (result.verificationRequired || result.user?.emailVerified === false) {
          switchMode("verify");
          setFormNotice(copy.verifyNotice);
          return;
        }
        enterTerminal();
        return;
      } else if (mode === "verify") {
        await verifyEmailRequest(verifyToken.trim());
        enterTerminal();
        return;
      } else if (mode === "forgot") {
        await forgotPasswordRequest(email);
        setFormNotice(copy.resetSent);
      } else if (mode === "reset") {
        await resetPasswordRequest(resetToken.trim(), password);
        setFormNotice(copy.resetDone);
        setMode("login");
        setPassword("");
        setResetToken("");
      }
    } catch (error) {
      setFormError(failureMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const onResendVerification = async () => {
    setFormError(null);
    setFormNotice(null);
    setBusy(true);
    try {
      await resendVerificationRequest();
      setFormNotice(copy.resent);
    } catch (error) {
      setFormError(failureMessage(error));
    } finally {
      setBusy(false);
    }
  };

  const title =
    mode === "signup"
      ? copy.signupTitle
      : mode === "forgot"
        ? copy.forgotTitle
        : mode === "reset"
          ? copy.resetTitle
          : mode === "verify"
            ? copy.verifyTitle
            : copy.title;

  const submitLabel = busy
    ? mode === "signup"
      ? copy.creating
      : mode === "forgot"
        ? copy.sending
        : mode === "reset"
          ? copy.setting
          : mode === "verify"
            ? copy.verifying
            : copy.signingIn
    : mode === "signup"
      ? copy.createAccount
      : mode === "forgot"
        ? copy.sendReset
        : mode === "reset"
          ? copy.setPassword
          : mode === "verify"
            ? copy.verify
            : copy.signIn;

  const inputClass =
    "kq-focus w-full rounded border border-terminal-line bg-terminal-raised px-3.5 py-2.5 text-sm text-terminal-ink placeholder:text-terminal-faint";
  const labelClass =
    "font-mono text-[11px] font-medium tracking-[0.2em] text-terminal-muted";

  return (
    <div className="flex min-h-screen bg-terminal-bg font-sans text-terminal-ink">
      {entering && (
        <QuoteLoadingScreen
          language={language}
          label={language === "ko" ? "터미널 입장 중" : "Entering the terminal"}
        />
      )}
      {/* Brand panel */}
      <aside className="relative hidden w-[42%] flex-col justify-between border-r border-terminal-line bg-terminal-panel p-10 lg:flex">
        <Link href="/" className="kq-focus flex w-fit items-center gap-3 rounded">
          <span className="flex h-8 w-8 items-center justify-center rounded bg-signal-dim font-mono text-sm font-bold text-signal">
            KQ
          </span>
          <span className="text-sm font-semibold tracking-wide">K-QUANT</span>
        </Link>
        <div>
          <p className="font-mono text-[11px] tracking-[0.35em] text-signal">
            {copy.eyebrow}
          </p>
          <p className="mt-5 max-w-sm text-2xl font-semibold leading-snug tracking-tight">
            {language === "ko"
              ? "감이 아닌 시스템으로, 리서치를 계량화합니다."
              : "Research the market with a system, not a feeling."}
          </p>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-terminal-muted">
            {copy.subtitle}
          </p>
        </div>
        <p className="font-mono text-[11px] text-terminal-faint">
          KOSPI · KOSDAQ · DART · {new Date().getFullYear()}
        </p>
      </aside>

      {/* Form panel */}
      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center justify-between lg:justify-end">
            <Link
              href="/"
              className="kq-focus rounded text-xs text-terminal-faint hover:text-terminal-muted lg:hidden"
            >
              {copy.landing}
            </Link>
            <div className="flex gap-1 font-mono text-[11px]">
              <button
                onClick={() => setLanguage("ko")}
                className={`kq-focus rounded px-2 py-1 ${language === "ko" ? "bg-terminal-raised text-terminal-ink" : "text-terminal-faint"}`}
              >
                KO
              </button>
              <button
                onClick={() => setLanguage("en")}
                className={`kq-focus rounded px-2 py-1 ${language === "en" ? "bg-terminal-raised text-terminal-ink" : "text-terminal-faint"}`}
              >
                EN
              </button>
            </div>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>

          <form onSubmit={onSubmit} noValidate className="mt-8 space-y-5">
            {mode !== "reset" && mode !== "verify" && (
              <div className="space-y-1.5">
                <label htmlFor="email" className={labelClass}>
                  {copy.email.toUpperCase()}
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onBlur={(e) => validateEmail(e.target.value)}
                  className={inputClass}
                  aria-invalid={emailError !== null}
                  aria-describedby="email-feedback"
                />
                <p
                  id="email-feedback"
                  className="kq-error-region text-xs text-down"
                  aria-live="polite"
                >
                  {emailError}
                </p>
              </div>
            )}

            {mode === "reset" && (
              <div className="space-y-1.5">
                <label htmlFor="reset-token" className={labelClass}>
                  {copy.resetToken.toUpperCase()}
                </label>
                <input
                  id="reset-token"
                  type="text"
                  autoComplete="one-time-code"
                  required
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  className={`${inputClass} font-mono`}
                />
                <p className="kq-error-region text-xs text-terminal-faint" />
              </div>
            )}

            {mode === "verify" && (
              <div className="space-y-1.5">
                <label htmlFor="verify-token" className={labelClass}>
                  {copy.verifyToken.toUpperCase()}
                </label>
                <input
                  id="verify-token"
                  type="text"
                  autoComplete="one-time-code"
                  required
                  value={verifyToken}
                  onChange={(e) => setVerifyToken(e.target.value)}
                  className={`${inputClass} font-mono`}
                />
                <p className="kq-error-region text-xs text-terminal-faint" />
              </div>
            )}

            {mode !== "forgot" && mode !== "verify" && (
              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between">
                  <label htmlFor="password" className={labelClass}>
                    {(mode === "reset"
                      ? copy.newPassword
                      : copy.password
                    ).toUpperCase()}
                  </label>
                  {mode === "login" && (
                    <button
                      type="button"
                      onClick={() => switchMode("forgot")}
                      className="kq-focus rounded text-xs text-terminal-faint hover:text-terminal-muted"
                    >
                      {copy.forgot}
                    </button>
                  )}
                </div>
                <input
                  id="password"
                  type="password"
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  required
                  minLength={PASSWORD_MIN_LENGTH}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onBlur={(e) => validatePassword(e.target.value)}
                  className={inputClass}
                  aria-invalid={passwordError !== null}
                  aria-describedby="password-feedback"
                />
                <p
                  id="password-feedback"
                  className="kq-error-region text-xs text-down"
                  aria-live="polite"
                >
                  {passwordError}
                </p>
              </div>
            )}

            {/* Form-level status: fixed height, no layout shift */}
            <div
              className="kq-error-region text-sm"
              role="status"
              aria-live="polite"
            >
              {formError && <span className="text-down">{formError}</span>}
              {formNotice && <span className="text-signal">{formNotice}</span>}
            </div>

            <button
              type="submit"
              disabled={busy}
              className="kq-focus flex w-full items-center justify-center gap-2 rounded bg-signal px-4 py-2.5 text-sm font-semibold text-terminal-bg transition-opacity disabled:opacity-60"
            >
              {busy && (
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-terminal-bg/40 border-t-terminal-bg" />
              )}
              {submitLabel}
            </button>
          </form>

          {/* Mode switches */}
          <div className="mt-6 space-y-2 text-sm text-terminal-muted">
            {mode === "login" && (
              <p>
                {copy.noAccount}{" "}
                <button
                  onClick={() => switchMode("signup")}
                  className="kq-focus rounded font-medium text-signal hover:underline"
                >
                  {copy.createAccount}
                </button>
              </p>
            )}
            {mode === "signup" && (
              <p>
                {copy.haveAccount}{" "}
                <button
                  onClick={() => switchMode("login")}
                  className="kq-focus rounded font-medium text-signal hover:underline"
                >
                  {copy.signIn}
                </button>
              </p>
            )}
            {mode === "forgot" && (
              <>
                <p>
                  {copy.haveCode}{" "}
                  <button
                    onClick={() => switchMode("reset")}
                    className="kq-focus rounded font-medium text-signal hover:underline"
                  >
                    {copy.resetToken}
                  </button>
                </p>
                <button
                  onClick={() => switchMode("login")}
                  className="kq-focus rounded text-terminal-faint hover:text-terminal-muted"
                >
                  {copy.backToLogin}
                </button>
              </>
            )}
            {mode === "reset" && (
              <button
                onClick={() => switchMode("login")}
                className="kq-focus rounded text-terminal-faint hover:text-terminal-muted"
              >
                {copy.backToLogin}
              </button>
            )}
            {mode === "verify" && (
              <>
                <button
                  onClick={onResendVerification}
                  disabled={busy}
                  className="kq-focus block rounded font-medium text-signal hover:underline disabled:opacity-60"
                >
                  {copy.resend}
                </button>
                <button
                  onClick={() => switchMode("login")}
                  className="kq-focus rounded text-terminal-faint hover:text-terminal-muted"
                >
                  {copy.backToLogin}
                </button>
              </>
            )}
          </div>

          {/* SSO slot -- scaffolded, not wired */}
          {(mode === "login" || mode === "signup") && (
            <div className="mt-8">
              <div className="flex items-center gap-3">
                <span className="h-px flex-1 bg-terminal-line" />
                <span className="font-mono text-[10px] tracking-[0.2em] text-terminal-faint">
                  {copy.ssoDivider.toUpperCase()}
                </span>
                <span className="h-px flex-1 bg-terminal-line" />
              </div>
              <button
                disabled
                title="SSO is not configured yet"
                className="mt-4 w-full cursor-not-allowed rounded border border-terminal-line px-4 py-2.5 text-sm text-terminal-faint"
              >
                {copy.ssoSoon}
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
