"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { currentUser } from "@/lib/authClient";
import { useLanguage } from "@/lib/language";
import { QuoteLine } from "./FinanceQuotes";
import GraphField from "./GraphField";

const COPY = {
  en: {
    eyebrow: "KOREAN MARKET INTELLIGENCE · SEOUL",
    headline1: "Make Stocks",
    headline2: "Revolutionary.",
    subhead:
      "Signal-ranked research across 2,700+ KOSPI and KOSDAQ listings — probability forecasting, regime analytics, and market-structure signals in one terminal.",
    ctaLogin: "Open the terminal",
    ctaDashboard: "Open your dashboard",
    methodology: "How the models work",
    stats: [
      ["2,700+", "KRX listings scanned"],
      ["43", "model features per stock"],
      ["5-day", "probability horizon"],
      ["4", "independent signal layers"],
    ],
    features: [
      [
        "01 / FORECASTING",
        "Probability, not prediction",
        "A per-stock model estimates five-day bullish probability from price, flow, and fundamentals — surfaced as a ranked Alpha Score with its own holdout accuracy attached. You always see how often the model has been right.",
      ],
      [
        "02 / REGIME ANALYTICS",
        "Know which market you're in",
        "Rolling Hurst-exponent and entropy measurements classify every stock as trending, mean-reverting, or random-walk — because a momentum signal in a mean-reverting regime is a trap, not a trade.",
      ],
      [
        "03 / MARKET STRUCTURE",
        "Follow the informed money",
        "Foreign and institutional flow, DART regulatory filings, valuation fundamentals, and news sentiment — merged into one feature space instead of four separate tabs.",
      ],
    ],
    disclaimer:
      "K-Quant produces ranked research signals. Nothing here is investment advice, a forecast, or a guarantee of outcomes.",
    signIn: "Sign in",
  },
  ko: {
    eyebrow: "KOREAN MARKET INTELLIGENCE · SEOUL",
    headline1: "주식에,",
    headline2: "혁명을.",
    subhead:
      "KOSPI·KOSDAQ 2,700여 종목을 확률 예측, 레짐 분석, 수급 구조 신호로 정렬한 리서치 터미널입니다.",
    ctaLogin: "터미널 열기",
    ctaDashboard: "대시보드 열기",
    methodology: "모델 작동 방식",
    stats: [
      ["2,700+", "분석 대상 KRX 종목"],
      ["43", "종목당 모델 피처"],
      ["5일", "확률 예측 구간"],
      ["4", "독립 신호 레이어"],
    ],
    features: [
      [
        "01 / FORECASTING",
        "예측이 아닌 확률",
        "종목별 모델이 가격·수급·펀더멘털에서 5거래일 상승 확률을 추정하고, 검증 구간 정확도와 함께 알파 스코어로 제시합니다. 모델이 얼마나 맞아왔는지 항상 확인할 수 있습니다.",
      ],
      [
        "02 / REGIME ANALYTICS",
        "지금 어떤 시장인지 파악",
        "롤링 허스트 지수와 엔트로피로 각 종목을 추세·평균회귀·랜덤워크 레짐으로 분류합니다. 평균회귀 구간의 모멘텀 신호는 기회가 아니라 함정이기 때문입니다.",
      ],
      [
        "03 / MARKET STRUCTURE",
        "정보 우위 자금의 흐름",
        "외국인·기관 수급, DART 공시 재무, 밸류에이션, 뉴스 심리를 네 개의 탭이 아닌 하나의 피처 공간으로 통합했습니다.",
      ],
    ],
    disclaimer:
      "K-Quant는 순위형 리서치 신호를 제공합니다. 투자 자문, 예측, 수익 보장이 아닙니다.",
    signIn: "로그인",
  },
} as const;

export default function LandingPage() {
  const { language, setLanguage } = useLanguage();
  const copy = COPY[language];
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    currentUser().then((user) => {
      if (!cancelled && user) setAuthenticated(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const primaryHref = authenticated ? "/dashboard" : "/login";
  const primaryLabel = authenticated ? copy.ctaDashboard : copy.ctaLogin;

  return (
    <div className="min-h-screen bg-terminal-bg font-sans text-terminal-ink">
      {/* Top bar */}
      <header className="relative z-20 mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded bg-signal-dim font-mono text-sm font-bold text-signal">
            KQ
          </span>
          <span className="text-sm font-semibold tracking-wide">K-QUANT</span>
        </div>
        <nav className="flex items-center gap-5">
          <div className="hidden items-center gap-2 rounded-full border border-terminal-line px-3 py-1 sm:flex">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal" />
            <span className="font-mono text-[11px] tracking-widest text-terminal-muted">
              KRX DATA LIVE
            </span>
          </div>
          <div className="flex gap-1 font-mono text-[11px]">
            <button
              onClick={() => setLanguage("ko")}
              className={`kq-focus rounded px-2 py-1 ${language === "ko" ? "bg-terminal-raised text-terminal-ink" : "text-terminal-faint hover:text-terminal-muted"}`}
            >
              KO
            </button>
            <button
              onClick={() => setLanguage("en")}
              className={`kq-focus rounded px-2 py-1 ${language === "en" ? "bg-terminal-raised text-terminal-ink" : "text-terminal-faint hover:text-terminal-muted"}`}
            >
              EN
            </button>
          </div>
          <Link
            href="/login"
            className="kq-focus rounded border border-terminal-line-strong px-4 py-1.5 text-sm text-terminal-ink transition-colors hover:border-signal hover:text-signal"
          >
            {copy.signIn}
          </Link>
        </nav>
      </header>

      {/* Hero with interactive graph field */}
      <section className="relative overflow-hidden">
        <GraphField />
        {/* Fade the field into the page below; pointer-events none keeps canvas interactive */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-terminal-bg" />

        <div className="pointer-events-none relative z-10 mx-auto max-w-6xl px-6 pb-28 pt-24 sm:pt-32">
          <p className="font-mono text-[11px] font-medium tracking-[0.35em] text-signal">
            {copy.eyebrow}
          </p>
          <h1 className="mt-6 max-w-3xl text-5xl font-semibold leading-[1.05] tracking-tight sm:text-7xl">
            {copy.headline1}
            <br />
            <span className="text-terminal-muted">{copy.headline2}</span>
          </h1>
          <p className="mt-7 max-w-xl text-base leading-relaxed text-terminal-muted sm:text-lg">
            {copy.subhead}
          </p>
          <div className="pointer-events-auto mt-10 flex flex-wrap items-center gap-4">
            <Link
              href={primaryHref}
              className="kq-focus rounded bg-signal px-6 py-3 text-sm font-semibold text-terminal-bg transition-transform hover:-translate-y-0.5"
            >
              {primaryLabel} →
            </Link>
            <a
              href="#methodology"
              className="kq-focus rounded px-2 py-3 text-sm text-terminal-muted transition-colors hover:text-terminal-ink"
            >
              {copy.methodology} ↓
            </a>
          </div>

          {/* Rotating market wisdom */}
          <QuoteLine
            language={language}
            className="mt-14 max-w-xl border-l-2 border-signal/40 pl-4"
          />
        </div>
      </section>

      {/* Stat strip */}
      <section className="border-y border-terminal-line bg-terminal-panel">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-px sm:grid-cols-4">
          {copy.stats.map(([value, label]) => (
            <div key={label} className="px-6 py-6">
              <div className="font-mono text-2xl font-medium text-terminal-ink">
                {value}
              </div>
              <div className="mt-1 text-xs tracking-wide text-terminal-faint">
                {label}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Feature rows */}
      <section id="methodology" className="mx-auto max-w-6xl px-6 py-24">
        <div className="space-y-16">
          {copy.features.map(([kicker, title, body]) => (
            <div
              key={kicker}
              className="grid gap-4 border-t border-terminal-line pt-8 sm:grid-cols-[220px_1fr] sm:gap-12"
            >
              <div className="font-mono text-[11px] tracking-[0.25em] text-signal">
                {kicker}
              </div>
              <div>
                <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
                  {title}
                </h2>
                <p className="mt-3 max-w-2xl leading-relaxed text-terminal-muted">
                  {body}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-terminal-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-8 text-xs text-terminal-faint sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-xl leading-relaxed">{copy.disclaimer}</p>
          <p className="font-mono">© {new Date().getFullYear()} K-QUANT</p>
        </div>
      </footer>
    </div>
  );
}
