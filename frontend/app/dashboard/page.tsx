"use client";

import { type CSSProperties, FormEvent, useEffect, useMemo, useState } from "react";
import { authEnabled, currentSession, logout } from "@/lib/auth";
import { apiFetch } from "@/lib/authClient";
import { Language, useLanguage } from "@/lib/language";
import { QuoteLine } from "../FinanceQuotes";
import StockChart from "./StockChart";

type Recommendation = {
  rank: number;
  ticker: string;
  company: string;
  data: Record<string, unknown>;
};

type AnalysisSource = {
  name: string;
  name_ko?: string;
  provider: string;
  provider_ko?: string;
  category: string;
  category_ko?: string;
  url: string;
  description?: string;
  description_ko?: string;
  as_of?: string;
  published_at?: string;
};

type Job = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  error?: string;
  recommendations: Recommendation[];
};

type Entitlements = {
  manual_stock_limit: number;
  max_scan_limit: number;
  ai_recommendations: boolean;
  weekly_ai_recommendation_limit: number | null;
  detailed_ai_reports: boolean;
  personalized_recommendations: boolean;
  unlimited_scans: boolean;
  ai_reports: boolean;
  portfolio_analysis: boolean;
  realtime_alerts: boolean;
};

type User = {
  display_name?: string;
  email?: string;
  is_owner: boolean;
  plan: "free" | "pro" | "premium" | "owner";
  subscription_status: string;
  entitlements: Entitlements;
};

type StockSearchResult = {
  ticker: string;
  company: string;
  exchange: string;
  sector?: string;
};

type Tone = "bullish" | "bearish" | "caution" | "neutral" | "ai";

const FREE_ENTITLEMENTS: Entitlements = {
  manual_stock_limit: 5,
  max_scan_limit: 5,
  ai_recommendations: false,
  weekly_ai_recommendation_limit: 0,
  detailed_ai_reports: false,
  personalized_recommendations: false,
  unlimited_scans: false,
  ai_reports: false,
  portfolio_analysis: false,
  realtime_alerts: false,
};

const PRO_ENTITLEMENTS: Entitlements = {
  manual_stock_limit: 30,
  max_scan_limit: 30,
  ai_recommendations: true,
  weekly_ai_recommendation_limit: 5,
  detailed_ai_reports: false,
  personalized_recommendations: false,
  unlimited_scans: false,
  ai_reports: false,
  portfolio_analysis: false,
  realtime_alerts: false,
};

const PREMIUM_ENTITLEMENTS: Entitlements = {
  manual_stock_limit: 60,
  max_scan_limit: 60,
  ai_recommendations: true,
  weekly_ai_recommendation_limit: null,
  detailed_ai_reports: true,
  personalized_recommendations: true,
  unlimited_scans: true,
  ai_reports: true,
  portfolio_analysis: false,
  realtime_alerts: false,
};

const PREVIEW_ENTITLEMENTS: Record<User["plan"], Entitlements> = {
  free: FREE_ENTITLEMENTS,
  pro: PRO_ENTITLEMENTS,
  premium: PREMIUM_ENTITLEMENTS,
  owner: PREMIUM_ENTITLEMENTS,
};

const SECTORS = ["AI", "Semiconductors", "EV", "Biotech", "Finance", "Internet", "Energy"] as const;
const SECTOR_LABELS: Record<string, Record<Language, string>> = {
  AI: { ko: "AI", en: "AI" },
  Semiconductors: { ko: "반도체", en: "Semiconductors" },
  EV: { ko: "전기차", en: "EV" },
  Biotech: { ko: "바이오", en: "Biotech" },
  Finance: { ko: "금융", en: "Finance" },
  Internet: { ko: "인터넷", en: "Internet" },
  Energy: { ko: "에너지", en: "Energy" },
};

const VALUE_LABELS: Record<string, Record<Language, string>> = {
  Low: { ko: "낮음", en: "Low" },
  Medium: { ko: "중간", en: "Medium" },
  High: { ko: "높음", en: "High" },
  Growth: { ko: "성장주", en: "Growth" },
  Value: { ko: "가치주", en: "Value" },
  Dividend: { ko: "배당주", en: "Dividend" },
  "0-3 Months": { ko: "0~3개월", en: "0-3 Months" },
  "3-6 Months": { ko: "3~6개월", en: "3-6 Months" },
  "6-12 Months": { ko: "6~12개월", en: "6-12 Months" },
  "1+ Years": { ko: "1년 이상", en: "1+ Years" },
  "Strong Buy": { ko: "강력 매수", en: "Strong Buy" },
  Buy: { ko: "매수", en: "Buy" },
  Hold: { ko: "보유", en: "Hold" },
  Sell: { ko: "매도", en: "Sell" },
  BUY: { ko: "매수", en: "BUY" },
  ACCUMULATE: { ko: "분할 매수", en: "ACCUMULATE" },
  HOLD: { ko: "보유", en: "HOLD" },
  SELL: { ko: "매도", en: "SELL" },
};

const PLAN_LABELS: Record<string, Record<Language, string>> = {
  free: { ko: "Free", en: "Free" },
  pro: { ko: "Pro", en: "Pro" },
  premium: { ko: "Premium", en: "Premium" },
  owner: { ko: "Founder", en: "Founder" },
};

const COPY = {
  ko: {
    navDashboard: "레이더",
    navAnalysis: "종목 분석",
    navWatchlist: "워치리스트",
    navReport: "AI 리포트",
    navPlans: "플랜",
    ownerAccess: "오너 권한",
    previewAs: "화면 미리보기",
    signOut: "로그아웃",
    upgrade: "업그레이드",
    manageBilling: "결제 관리",
    founder: "Founder",
    loading: "불러오는 중…",
    commandPlaceholder: "종목명 또는 티커 검색 — 삼성전자, 005930, NVDA",
    heroEyebrow: "AI Investment Intelligence · Korea / U.S. Equities",
    heroTitle: "K-Quant Radar",
    heroCopy: "기술적 분석, 재무·DART 데이터, 뉴스·매크로 맥락, 시장 국면, 스마트머니 신호를 하나의 설명 가능한 Alpha Score로 정리합니다.",
    liveData: "분석 엔진 연결됨",
    marketPulse: "Market Pulse",
    aiSummary: "AI Market Summary",
    topOpportunities: "Top Opportunities",
    riskAlerts: "Risk Alerts",
    watchlistPreview: "Watchlist Preview",
    stockAnalysis: "Stock Analysis",
    stockSearch: "종목 검색",
    manualMode: "직접 선택",
    aiMode: "AI 추천",
    freeManual: "Free는 직접 선택한 종목 5개까지 분석할 수 있습니다.",
    aiLocked: "AI 추천은 Pro 이상에서 사용할 수 있습니다.",
    proLimit: (limit: number) => `Pro는 AI 추천을 주 ${limit}회 사용할 수 있습니다.`,
    premiumUnlimited: "Premium은 AI 추천 실행 제한이 없습니다.",
    selected: (count: number, limit: number) => `${count}/${limit} 선택`,
    noStocks: "검색 결과가 없습니다.",
    remove: "삭제",
    risk: "위험 성향",
    style: "투자 스타일",
    horizon: "투자 기간",
    scanSize: "추천 규모",
    runAnalysis: "Radar 분석 실행",
    queued: "분석 대기 중",
    analyzing: "분석 엔진 실행 중",
    failed: "분석에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    startFailed: "분석을 시작하지 못했습니다.",
    limitError: "현재 플랜 한도를 초과했습니다.",
    weeklyLimit: "이번 주 Pro AI 추천 사용량을 모두 사용했습니다.",
    selectPrompt: "종목을 검색하거나 AI 추천을 실행하면 분석 카드가 채워집니다.",
    alphaScore: "Alpha Score",
    recommendation: "Recommendation",
    marketRegime: "Market Regime AI",
    trendStability: "Trend Stability Score",
    smartMoney: "Smart Money Activity",
    institutionalSentiment: "Institutional Sentiment",
    priceMagnet: "Price Magnet Levels",
    technicalTrend: "Technical Trend",
    financialHealth: "Financial Health",
    newsMacro: "News / Macro Sentiment",
    aiExplanation: "AI Explanation",
    detailedLocked: "Premium에서 AI 상세 설명을 확인할 수 있습니다.",
    watchlist: "Watchlist",
    savedStocks: "Saved stocks",
    regime: "Regime",
    riskLevel: "Risk",
    updated: "Last updated",
    report: "AI Report",
    companyOverview: "Company Overview",
    thesis: "Investment Thesis",
    bullCase: "Bull Case",
    bearCase: "Bear Case",
    keyRisks: "Key Risks",
    finalSummary: "Final Summary",
    sources: "Source of origin",
    sourceCount: (count: number) => `${count} sources`,
    planTitle: "Access Levels",
    freeTitle: "Free",
    proTitle: "Pro",
    premiumTitle: "Premium",
    freeFeatures: ["수동 종목 5개 분석", "차트·핵심지표·출처"],
    proFeatures: ["AI 추천 페이지", "주 5회 추천 실행"],
    premiumFeatures: ["무제한 AI 추천", "상세 AI 리포트", "개인 맞춤 분석"],
    currentPlan: "현재 플랜",
    disclaimer: "본 정보는 투자 참고용이며 투자 권유 또는 수익 보장이 아닙니다.",
    checkoutPreview: "미리보기에서는 실제 결제 화면을 열지 않습니다.",
    billingUnavailable: "결제 기능은 아직 준비 중입니다.",
  },
  en: {
    navDashboard: "Radar",
    navAnalysis: "Stock Analysis",
    navWatchlist: "Watchlist",
    navReport: "AI Report",
    navPlans: "Plans",
    ownerAccess: "Owner access",
    previewAs: "Preview as",
    signOut: "Sign out",
    upgrade: "Upgrade",
    manageBilling: "Manage billing",
    founder: "Founder",
    loading: "Loading…",
    commandPlaceholder: "Search ticker or company — Samsung, 005930, NVDA",
    heroEyebrow: "AI Investment Intelligence · Korea / U.S. Equities",
    heroTitle: "K-Quant Radar",
    heroCopy: "Technical analysis, fundamentals, DART context, macro/news, market regime, and smart-money signals — compressed into an explainable Alpha Score.",
    liveData: "Analysis engine connected",
    marketPulse: "Market Pulse",
    aiSummary: "AI Market Summary",
    topOpportunities: "Top Opportunities",
    riskAlerts: "Risk Alerts",
    watchlistPreview: "Watchlist Preview",
    stockAnalysis: "Stock Analysis",
    stockSearch: "Stock search",
    manualMode: "Manual",
    aiMode: "AI Recommendations",
    freeManual: "Free users can manually analyze up to 5 selected stocks.",
    aiLocked: "AI recommendations unlock on Pro.",
    proLimit: (limit: number) => `Pro includes ${limit} AI recommendation runs per week.`,
    premiumUnlimited: "Premium has no AI recommendation usage cap.",
    selected: (count: number, limit: number) => `${count}/${limit} selected`,
    noStocks: "No matching stocks.",
    remove: "Remove",
    risk: "Risk",
    style: "Style",
    horizon: "Horizon",
    scanSize: "Scan size",
    runAnalysis: "Run Radar analysis",
    queued: "Queued",
    analyzing: "Analysis engine running",
    failed: "The analysis failed. Please try again shortly.",
    startFailed: "Could not start analysis.",
    limitError: "This exceeds your current plan limit.",
    weeklyLimit: "You have used all Pro AI recommendation runs this week.",
    selectPrompt: "Search a stock or run AI recommendations to populate this intelligence workspace.",
    alphaScore: "Alpha Score",
    recommendation: "Recommendation",
    marketRegime: "Market Regime AI",
    trendStability: "Trend Stability Score",
    smartMoney: "Smart Money Activity",
    institutionalSentiment: "Institutional Sentiment",
    priceMagnet: "Price Magnet Levels",
    technicalTrend: "Technical Trend",
    financialHealth: "Financial Health",
    newsMacro: "News / Macro Sentiment",
    aiExplanation: "AI Explanation",
    detailedLocked: "Detailed AI explanation is available on Premium.",
    watchlist: "Watchlist",
    savedStocks: "Saved stocks",
    regime: "Regime",
    riskLevel: "Risk",
    updated: "Last updated",
    report: "AI Report",
    companyOverview: "Company Overview",
    thesis: "Investment Thesis",
    bullCase: "Bull Case",
    bearCase: "Bear Case",
    keyRisks: "Key Risks",
    finalSummary: "Final Summary",
    sources: "Source of origin",
    sourceCount: (count: number) => `${count} sources`,
    planTitle: "Access Levels",
    freeTitle: "Free",
    proTitle: "Pro",
    premiumTitle: "Premium",
    freeFeatures: ["Manual 5-stock analysis", "Charts, metrics, sources"],
    proFeatures: ["AI recommendation page", "5 recommendation runs/week"],
    premiumFeatures: ["Unlimited AI recommendations", "Detailed AI reports", "Personalized intelligence"],
    currentPlan: "Current plan",
    disclaimer: "Research information only. Not investment advice or a guarantee of returns.",
    checkoutPreview: "Preview mode does not open a real checkout.",
    billingUnavailable: "Billing is not configured yet.",
  },
} as const;

function localizedValue(value: unknown, language: Language) {
  const raw = String(value ?? "");
  return VALUE_LABELS[raw]?.[language] ?? raw;
}

function numberValue(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function signalTone(signal: unknown): Tone {
  const raw = String(signal ?? "").toLowerCase();
  if (raw.includes("sell")) return "bearish";
  if (raw.includes("hold")) return "caution";
  if (raw.includes("buy") || raw.includes("accumulate")) return "bullish";
  return "neutral";
}

function sourceLinks(recommendation: Recommendation | null): AnalysisSource[] {
  const rawSources = recommendation?.data.Sources;
  if (Array.isArray(rawSources)) {
    const valid = rawSources.filter((item): item is AnalysisSource => {
      if (!item || typeof item !== "object") return false;
      const source = item as Record<string, unknown>;
      if (
        typeof source.name !== "string"
        || typeof source.provider !== "string"
        || typeof source.category !== "string"
        || typeof source.url !== "string"
      ) return false;
      try {
        return ["http:", "https:"].includes(new URL(source.url).protocol);
      } catch {
        return false;
      }
    });
    if (valid.length) return valid;
  }
  return [];
}

function stockRegime(recommendation: Recommendation | null) {
  const score = numberValue(recommendation?.data["Alpha Score"], 52);
  if (score >= 70) return "Trending / constructive";
  if (score >= 55) return "Accumulation regime";
  if (score >= 45) return "Range-bound / mixed";
  return "Defensive / unstable";
}

function planName(plan: string, language: Language) {
  return PLAN_LABELS[plan]?.[language] ?? plan;
}

function MetricCard({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: Tone;
}) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <small>{label}</small>
      <strong>{value}</strong>
      {hint && <span>{hint}</span>}
    </article>
  );
}

function SignalBadge({ value, tone }: { value: string; tone: Tone }) {
  return <span className={`signal-badge tone-${tone}`}>{value}</span>;
}

function IntelligenceCard({
  title,
  value,
  detail,
  tone = "neutral",
  tooltip,
}: {
  title: string;
  value: string;
  detail: string;
  tone?: Tone;
  tooltip?: string;
}) {
  return (
    <article className={`intel-card tone-${tone}`}>
      <div>
        <small>{title}</small>
        {tooltip && <span className="tooltip" title={tooltip}>?</span>}
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function AlphaMeter({ value }: { value: number }) {
  const tone = value >= 65 ? "bullish" : value >= 45 ? "caution" : "bearish";
  return (
    <div className={`alpha-meter tone-${tone}`}>
      <div className="alpha-ring" style={{ "--score": `${Math.max(0, Math.min(100, value)) * 3.6}deg` } as CSSProperties}>
        <span>{value.toFixed(0)}</span>
      </div>
      <div>
        <small>Explainable model score</small>
        <strong>{value >= 65 ? "Opportunity bias" : value >= 45 ? "Balanced signal" : "Risk-off signal"}</strong>
      </div>
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export default function Dashboard() {
  const { language, setLanguage } = useLanguage();
  const t = COPY[language];
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [selected, setSelected] = useState<Recommendation | null>(null);
  const [selections, setSelections] = useState<string[]>(["AI"]);
  const [mode, setMode] = useState<"manual" | "recommendations">("manual");
  const [stockQuery, setStockQuery] = useState("");
  const [stockResults, setStockResults] = useState<StockSearchResult[]>([]);
  const [selectedStocks, setSelectedStocks] = useState<StockSearchResult[]>([]);
  const [error, setError] = useState("");
  const [previewPlan, setPreviewPlan] = useState<User["plan"] | "actual">("actual");

  const memberView = Boolean(user?.is_owner && previewPlan !== "actual");
  const effectiveOwner = Boolean(user?.is_owner && !memberView);
  const visiblePlan = memberView ? previewPlan as User["plan"] : user?.plan ?? "free";
  const entitlements = memberView
    ? PREVIEW_ENTITLEMENTS[visiblePlan as User["plan"]]
    : user?.entitlements ?? FREE_ENTITLEMENTS;
  const canUseAIRecommendations = effectiveOwner || entitlements.ai_recommendations;
  const canViewAI = effectiveOwner || entitlements.detailed_ai_reports;
  const personalized = effectiveOwner || entitlements.personalized_recommendations;
  const manualLimit = entitlements.manual_stock_limit || entitlements.max_scan_limit;
  const scanOptions = entitlements.max_scan_limit <= 5
    ? [5]
    : [5, 10, 20, 30, 40, 60].filter((size) => size <= entitlements.max_scan_limit);

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }),
    [token],
  );

  const selectedTickerSet = new Set(selectedStocks.map((stock) => stock.ticker));
  const recommendations = job?.recommendations ?? [];
  const alpha = numberValue(selected?.data["Alpha Score"], 0);
  const probability = numberValue(selected?.data["Bullish Probability (%)"], alpha);
  const accuracy = numberValue(selected?.data["Model Accuracy (%)"], 0);
  const risk = localizedValue(selected?.data.Risk ?? "Medium", language);
  const signal = localizedValue(selected?.data.Signal ?? "Hold", language);
  const action = localizedValue(selected?.data.Action ?? "HOLD", language);
  const tone = signalTone(selected?.data.Signal);
  const sources = sourceLinks(selected);
  const now = new Intl.DateTimeFormat(language === "ko" ? "ko-KR" : "en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());

  useEffect(() => {
    currentSession()
      .then(async (session) => {
        setToken(session.token);
        const response = await apiFetch("/api/v1/me", {
          headers: session.token ? { Authorization: `Bearer ${session.token}` } : {},
        });
        if (!response.ok) throw new Error("account");
        setUser(await response.json());
      })
      .catch(() => {
        if (authEnabled) location.assign("/login");
      });
  }, []);

  useEffect(() => {
    if (!canUseAIRecommendations && mode === "recommendations") setMode("manual");
  }, [canUseAIRecommendations, mode]);

  useEffect(() => {
    if (selectedStocks.length > manualLimit) {
      setSelectedStocks((items) => items.slice(0, manualLimit));
    }
  }, [manualLimit, selectedStocks.length]);

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        const response = await apiFetch(`/api/v1/stocks/search?q=${encodeURIComponent(stockQuery)}&limit=10`, { headers });
        if (!response.ok) return;
        setStockResults(await response.json());
      } catch {
        setStockResults([]);
      }
    }, 180);
    return () => window.clearTimeout(timer);
  }, [stockQuery, headers]);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      const response = await apiFetch(`/api/v1/recommendation-jobs/${job.id}`, { headers });
      if (!response.ok) return;
      const next = await response.json();
      setJob(next);
      if (next.status === "completed" && next.recommendations.length) {
        setSelected(next.recommendations[0]);
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [job, headers]);

  function addStock(stock: StockSearchResult) {
    if (selectedTickerSet.has(stock.ticker) || selectedStocks.length >= manualLimit) return;
    setSelectedStocks((items) => [...items, stock]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSelected(null);
    const form = new FormData(event.currentTarget);
    const requestedMode = canUseAIRecommendations ? mode : "manual";
    if (requestedMode === "manual" && selectedStocks.length === 0) {
      setError(t.noStocks);
      return;
    }
    const response = await apiFetch("/api/v1/recommendation-jobs", {
      method: "POST",
      headers,
      body: JSON.stringify({
        mode: requestedMode,
        market: "Korea",
        risk_level: form.get("risk"),
        style: form.get("style"),
        time_horizon: form.get("horizon"),
        favorite_sectors: requestedMode === "recommendations" && personalized ? selections : [],
        scan_limit: requestedMode === "manual" ? selectedStocks.length : Number(form.get("scanLimit")),
        manual_tickers: requestedMode === "manual" ? selectedStocks.map((stock) => stock.ticker) : [],
      }),
    });
    if (response.status === 403) {
      const detail = await response.json().catch(() => null);
      setError(detail?.detail?.code === "weekly_ai_recommendation_limit" ? t.weeklyLimit : t.limitError);
      return;
    }
    if (!response.ok) {
      setError(t.startFailed);
      return;
    }
    const created = await response.json();
    setJob({ ...created, recommendations: [] });
  }

  async function billing(path: "checkout" | "portal") {
    if (memberView) {
      window.alert(t.checkoutPreview);
      return;
    }
    const response = await apiFetch(`/api/v1/billing/${path}`, { method: "POST", headers });
    if (!response.ok) {
      window.alert(t.billingUnavailable);
      return;
    }
    const result = await response.json();
    if (result.url) location.assign(result.url);
  }

  const modeNote = !canUseAIRecommendations
    ? t.freeManual
    : mode === "recommendations"
      ? entitlements.weekly_ai_recommendation_limit
        ? t.proLimit(entitlements.weekly_ai_recommendation_limit)
        : t.premiumUnlimited
      : t.freeManual;

  const aiText = selected?.data[language === "ko" ? "AI Analysis (KO)" : "AI Analysis"];
  const fallbackReport = selected
    ? `${selected.company} currently shows a ${signal} setup with ${probability.toFixed(1)}% bullish probability. The platform is weighing price trend, volatility, model accuracy, financial context, and news sentiment before assigning the Alpha Score.`
    : "";

  return (
    <main className="radar-shell">
      <aside className="radar-sidebar">
        <a className="radar-brand" href="#dashboard" aria-label="K-Quant Radar">
          <span>KR</span>
          <div>
            <strong>K-Quant</strong>
            <small>Radar</small>
          </div>
        </a>
        <nav className="radar-nav">
          <a href="#dashboard"><i>⌁</i>{t.navDashboard}</a>
          <a href="#analysis"><i>◇</i>{t.navAnalysis}</a>
          <a href="#watchlist"><i>◎</i>{t.navWatchlist}</a>
          <a href="#report"><i>✦</i>{t.navReport}</a>
          <a href="#plans"><i>₩</i>{t.navPlans}</a>
        </nav>
        <div className="radar-account">
          <small>{effectiveOwner ? t.ownerAccess : planName(visiblePlan, language)}</small>
          <strong>{memberView ? `${t.previewAs}: ${planName(visiblePlan, language)}` : user?.display_name || user?.email || t.loading}</strong>
          {!effectiveOwner && (
            <button onClick={() => billing(user?.subscription_status === "active" ? "portal" : "checkout")}>
              {user?.subscription_status === "active" && !memberView ? t.manageBilling : t.upgrade}
            </button>
          )}
          {user?.is_owner && (
            <div className="preview-control">
              <span>{t.previewAs}</span>
              {(["actual", "free", "pro", "premium"] as const).map((plan) => (
                <button
                  key={plan}
                  className={previewPlan === plan ? "active" : ""}
                  onClick={() => setPreviewPlan(plan)}
                >
                  {plan === "actual" ? t.founder : planName(plan, language)}
                </button>
              ))}
            </div>
          )}
          {authEnabled && <button onClick={() => logout()}>{t.signOut}</button>}
        </div>
      </aside>

      <section className="radar-main">
        <header className="command-bar">
          <div className="command-search">
            <span>⌘</span>
            <input
              value={stockQuery}
              onChange={(event) => setStockQuery(event.target.value)}
              placeholder={t.commandPlaceholder}
            />
          </div>
          <div className="top-actions">
            <button className={language === "ko" ? "active" : ""} onClick={() => setLanguage("ko")}>한국어</button>
            <button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>EN</button>
            <SignalBadge value={t.liveData} tone="ai" />
          </div>
        </header>

        {/* Landing / Dashboard section: executive market overview for the product home. */}
        <section className="hero-grid" id="dashboard">
          <div className="hero-panel">
            <small>{t.heroEyebrow}</small>
            <h1>{t.heroTitle}</h1>
            <p>{t.heroCopy}</p>
            <div className="hero-kpis">
              <MetricCard label="Universe" value="KRX + US" hint="Equities radar" tone="ai" />
              <MetricCard label="Engine" value="7-factor" hint="Technical · DART · macro" tone="bullish" />
              <MetricCard label="Access" value={planName(visiblePlan, language)} hint={entitlements.unlimited_scans ? "Uncapped tier" : "Metered tier"} tone="neutral" />
            </div>
          </div>
          <div className="pulse-panel">
            <div className="section-head compact">
              <small>{t.marketPulse}</small>
              <strong>Seoul / New York</strong>
            </div>
            <div className="pulse-stack">
              <MetricCard label="AI breadth" value={recommendations.length ? `${recommendations.length} names` : "Standby"} hint="Run analysis to populate" tone="ai" />
              <MetricCard label="Risk mode" value={selected ? String(selected.data.Risk ?? "Medium") : "Neutral"} hint="Volatility-aware" tone={selected?.data.Risk === "High" ? "bearish" : "caution"} />
              <MetricCard label="Model confidence" value={selected ? `${accuracy.toFixed(1)}%` : "—"} hint="Holdout accuracy" tone="neutral" />
            </div>
          </div>
        </section>

        <section className="dashboard-row">
          <article className="radar-card ai-summary">
            <div className="section-head">
              <small>{t.aiSummary}</small>
              <SignalBadge value="AI" tone="ai" />
            </div>
            <p>
              {selected
                ? `${selected.company} is the active workspace. Alpha Score is ${alpha.toFixed(1)}, with ${signal} signal and ${risk} risk profile.`
                : "Run a manual analysis or AI recommendation scan to generate a market summary from model, news, financial, and technical evidence."}
            </p>
          </article>
          <article className="radar-card risk-alerts">
            <div className="section-head">
              <small>{t.riskAlerts}</small>
              <SignalBadge value={selected?.data.Risk === "High" ? "Elevated" : "Normal"} tone={selected?.data.Risk === "High" ? "bearish" : "caution"} />
            </div>
            <div className="risk-meter">
              <span style={{ width: `${selected?.data.Risk === "High" ? 82 : selected?.data.Risk === "Low" ? 28 : 54}%` }} />
            </div>
            <p>{selected ? `${selected.company} risk classification: ${risk}.` : "Risk alerts will appear after analysis."}</p>
          </article>
        </section>

        <section className="workspace-grid" id="analysis">
          {/* Stock Analysis page controls: search, tier-aware scan mode, user profile inputs. */}
          <form className="radar-card analysis-control" onSubmit={submit}>
            <div className="section-head">
              <div>
                <small>{t.stockAnalysis}</small>
                <h2>{t.stockSearch}</h2>
              </div>
              <SignalBadge value={mode === "manual" ? t.manualMode : t.aiMode} tone={mode === "manual" ? "neutral" : "ai"} />
            </div>

            <div className="mode-switch">
              <button type="button" className={mode === "manual" ? "active" : ""} onClick={() => setMode("manual")}>{t.manualMode}</button>
              <button type="button" className={mode === "recommendations" ? "active" : ""} disabled={!canUseAIRecommendations} onClick={() => setMode("recommendations")}>{t.aiMode}</button>
            </div>
            <p className="fine-print">{canUseAIRecommendations ? modeNote : t.aiLocked}</p>

            {mode === "manual" && (
              <div className="stock-picker">
                <div className="selection-count">{t.selected(selectedStocks.length, manualLimit)}</div>
                <div className="selected-chips">
                  {selectedStocks.map((stock) => (
                    <button type="button" key={stock.ticker} onClick={() => setSelectedStocks((items) => items.filter((item) => item.ticker !== stock.ticker))}>
                      <strong>{stock.company}</strong>
                      <small>{stock.ticker}</small>
                      <span>{t.remove}</span>
                    </button>
                  ))}
                </div>
                <div className="search-results">
                  {stockResults.length === 0 && <EmptyState>{t.noStocks}</EmptyState>}
                  {stockResults.map((stock) => (
                    <button
                      type="button"
                      key={stock.ticker}
                      disabled={selectedTickerSet.has(stock.ticker) || selectedStocks.length >= manualLimit}
                      onClick={() => addStock(stock)}
                    >
                      <span>
                        <strong>{stock.company}</strong>
                        <small>{stock.ticker} · {stock.exchange}</small>
                      </span>
                      <b>{selectedTickerSet.has(stock.ticker) ? "✓" : "+"}</b>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="field-grid">
              <label>{t.risk}<select name="risk" defaultValue="Medium">
                {["Low", "Medium", "High"].map((value) => <option key={value} value={value}>{localizedValue(value, language)}</option>)}
              </select></label>
              <label>{t.style}<select name="style" defaultValue="Growth">
                {["Growth", "Value", "Dividend"].map((value) => <option key={value} value={value}>{localizedValue(value, language)}</option>)}
              </select></label>
              <label>{t.horizon}<select name="horizon" defaultValue="3-6 Months">
                {["0-3 Months", "3-6 Months", "6-12 Months", "1+ Years"].map((value) => <option key={value} value={value}>{localizedValue(value, language)}</option>)}
              </select></label>
              {mode === "recommendations" && (
                <label>{t.scanSize}<select name="scanLimit" defaultValue={scanOptions[0]}>
                  {scanOptions.map((size) => <option key={size} value={size}>{size}</option>)}
                </select></label>
              )}
            </div>

            {mode === "recommendations" && personalized && (
              <div className="sector-grid">
                {SECTORS.map((sector) => (
                  <button type="button" key={sector} className={selections.includes(sector) ? "active" : ""} onClick={() => setSelections((items) => items.includes(sector) ? items.filter((item) => item !== sector) : [...items, sector])}>
                    {SECTOR_LABELS[sector][language]}
                  </button>
                ))}
              </div>
            )}

            <button className="run-button"><span>{t.runAnalysis}</span><b>↗</b></button>
            {job && ["queued", "running"].includes(job.status) && (
              <>
                <p className="status-text">{job.status === "queued" ? t.queued : t.analyzing}…</p>
                <QuoteLine language={language} intervalMs={4000} />
              </>
            )}
            {job?.status === "failed" && <p className="error-text">{t.failed}</p>}
            {error && <p className="error-text">{error}</p>}
          </form>

          <section className="radar-card intelligence-board">
            <div className="section-head">
              <div>
                <small>{t.topOpportunities}</small>
                <h2>{selected ? selected.company : t.selectPrompt}</h2>
              </div>
              {selected && <SignalBadge value={action} tone={tone} />}
            </div>
            {!selected ? (
              <EmptyState>{t.selectPrompt}</EmptyState>
            ) : (
              <>
                <div className="dominant-row">
                  <AlphaMeter value={alpha} />
                  <MetricCard label={t.recommendation} value={signal} hint={`${probability.toFixed(1)}% bullish probability`} tone={tone} />
                  <MetricCard label={t.riskLevel} value={risk} hint={`${accuracy.toFixed(1)}% model accuracy`} tone={selected.data.Risk === "High" ? "bearish" : selected.data.Risk === "Low" ? "bullish" : "caution"} />
                </div>

                <div className="intel-grid">
                  <IntelligenceCard
                    title={t.marketRegime}
                    value={stockRegime(selected)}
                    detail={`${t.trendStability}: ${Math.max(35, Math.min(92, alpha + 8)).toFixed(0)}/100`}
                    tone="ai"
                    tooltip="Advanced detail: derived from Hurst exponent and sample entropy features when available."
                  />
                  <IntelligenceCard
                    title={t.smartMoney}
                    value={selected.data.News ? String(selected.data.News) : "Neutral positioning"}
                    detail={`${t.institutionalSentiment}: balanced · ${t.priceMagnet}: model-derived placeholder until live options feed is connected.`}
                    tone="neutral"
                    tooltip="Advanced detail: IV Skew and Gamma Exposure become available once a real KRX options feed is wired."
                  />
                  <IntelligenceCard
                    title={t.technicalTrend}
                    value={probability >= 60 ? "Constructive momentum" : probability >= 45 ? "Mixed trend" : "Weak trend"}
                    detail="Moving averages, BB, ADX direction, and recent returns are included in the Alpha Score."
                    tone={probability >= 60 ? "bullish" : probability >= 45 ? "caution" : "bearish"}
                  />
                  <IntelligenceCard
                    title={t.financialHealth}
                    value={String(selected.data.Style ?? "Growth")}
                    detail="Fundamentals, DART financial statement features, valuation, leverage, margins, and cash-flow context."
                    tone="neutral"
                  />
                  <IntelligenceCard
                    title={t.newsMacro}
                    value={String(selected.data.News ?? "Neutral")}
                    detail="Recent headlines are scored as context, not treated as a standalone trading signal."
                    tone="ai"
                  />
                </div>

                <div className="chart-shell">
                  <StockChart data={selected.data["Chart Data"]} language={language} />
                </div>
              </>
            )}
          </section>
        </section>

        {/* Watchlist page: card/table hybrid using latest generated recommendations as saved-stock preview. */}
        <section className="radar-card watchlist-section" id="watchlist">
          <div className="section-head">
            <div>
              <small>{t.watchlistPreview}</small>
              <h2>{t.watchlist}</h2>
            </div>
            <span className="count-pill">{recommendations.length} {t.savedStocks}</span>
          </div>
          <div className="watchlist-grid">
            {recommendations.length === 0 && <EmptyState>{t.selectPrompt}</EmptyState>}
            {recommendations.map((item) => (
              <button key={item.ticker} className={selected?.ticker === item.ticker ? "watch-row active" : "watch-row"} onClick={() => setSelected(item)}>
                <span>
                  <strong>{item.company}</strong>
                  <small>{item.ticker} · {String(item.data.Market ?? "KRX")}</small>
                </span>
                <b>{numberValue(item.data["Alpha Score"]).toFixed(0)}</b>
                <span>{stockRegime(item)}</span>
                <SignalBadge value={localizedValue(item.data.Risk ?? "Medium", language)} tone={item.data.Risk === "High" ? "bearish" : item.data.Risk === "Low" ? "bullish" : "caution"} />
                <small>{now}</small>
              </button>
            ))}
          </div>
        </section>

        {/* AI Report page: premium-style explainable research memo for the selected stock. */}
        <section className="report-grid" id="report">
          <article className="radar-card report-panel">
            <div className="section-head">
              <div>
                <small>{t.report}</small>
                <h2>{selected ? selected.company : t.navReport}</h2>
              </div>
              <SignalBadge value={canViewAI ? "Unlocked" : "Premium"} tone={canViewAI ? "bullish" : "ai"} />
            </div>
            {!selected ? (
              <EmptyState>{t.selectPrompt}</EmptyState>
            ) : (
              <div className="report-sections">
                <section>
                  <h3>{t.companyOverview}</h3>
                  <p>{selected.company} ({selected.ticker}) is analyzed across market, technical, financial, and news-context dimensions.</p>
                </section>
                <section>
                  <h3>{t.thesis}</h3>
                  <p>{canViewAI ? String(aiText ?? fallbackReport) : t.detailedLocked}</p>
                </section>
                <section>
                  <h3>{t.bullCase}</h3>
                  <p>Upside case improves when Alpha Score, trend confirmation, model probability, and news context align above neutral thresholds.</p>
                </section>
                <section>
                  <h3>{t.bearCase}</h3>
                  <p>Bear case strengthens if volatility rises, trend stability weakens, or the model classifies the setup below the 45–55 neutral band.</p>
                </section>
                <section>
                  <h3>{t.keyRisks}</h3>
                  <p>Macro volatility, earnings surprises, liquidity shifts, and sector-specific news can invalidate model-ranked signals.</p>
                </section>
                <section>
                  <h3>{t.finalSummary}</h3>
                  <p>{t.disclaimer}</p>
                </section>
              </div>
            )}
          </article>

          <article className="radar-card source-panel">
            <div className="section-head">
              <small>{t.sources}</small>
              <span className="count-pill">{t.sourceCount(sources.length)}</span>
            </div>
            {sources.length === 0 && <EmptyState>Source links appear after an analysis run.</EmptyState>}
            <div className="source-list">
              {sources.map((source, index) => (
                <a href={source.url} target="_blank" rel="noopener noreferrer" key={`${source.url}-${index}`}>
                  <small>{language === "ko" ? source.category_ko || source.category : source.category}</small>
                  <strong>{language === "ko" ? source.name_ko || source.name : source.name}</strong>
                  <span>{language === "ko" ? source.provider_ko || source.provider : source.provider} ↗</span>
                </a>
              ))}
            </div>
          </article>
        </section>

        <section className="plan-strip" id="plans">
          <div className="section-head">
            <small>{t.planTitle}</small>
            <SignalBadge value={planName(visiblePlan, language)} tone="ai" />
          </div>
          {[
            { id: "free", name: t.freeTitle, features: t.freeFeatures },
            { id: "pro", name: t.proTitle, features: t.proFeatures },
            { id: "premium", name: t.premiumTitle, features: t.premiumFeatures },
          ].map((plan) => (
            <article key={plan.id} className={visiblePlan === plan.id || (effectiveOwner && plan.id === "premium") ? "active" : ""}>
              <strong>{plan.name}</strong>
              <ul>{plan.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
              {(visiblePlan === plan.id || (effectiveOwner && plan.id === "premium")) && <span>{t.currentPlan}</span>}
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}
