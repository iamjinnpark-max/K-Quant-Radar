"use client";

import { useEffect, useState } from "react";

import type { Language } from "@/lib/language";

// Rotating wisdom from the people who moved markets. Shown wherever the
// user waits: landing hero, post-login transition, analysis runs.
const QUOTES: Array<{ en: string; ko: string; who: string }> = [
  {
    en: "Be fearful when others are greedy, and greedy when others are fearful.",
    ko: "남들이 탐욕스러울 때 두려워하고, 남들이 두려워할 때 탐욕스러워라.",
    who: "Warren Buffett",
  },
  {
    en: "In the short run, the market is a voting machine. In the long run, it is a weighing machine.",
    ko: "단기적으로 시장은 인기 투표기이지만, 장기적으로는 가치를 재는 저울이다.",
    who: "Benjamin Graham",
  },
  {
    en: "The big money is not in the buying and the selling, but in the waiting.",
    ko: "큰돈은 사고파는 데서가 아니라 기다리는 데서 나온다.",
    who: "Charlie Munger",
  },
  {
    en: "Know what you own, and know why you own it.",
    ko: "무엇을 보유하고 있는지, 왜 보유하는지를 알아라.",
    who: "Peter Lynch",
  },
  {
    en: "The four most dangerous words in investing are: 'this time it's different.'",
    ko: "투자에서 가장 위험한 네 단어는 '이번엔 다르다'이다.",
    who: "Sir John Templeton",
  },
  {
    en: "It's not whether you're right or wrong, but how much money you make when you're right and how much you lose when you're wrong.",
    ko: "맞느냐 틀리느냐가 아니라, 맞았을 때 얼마나 벌고 틀렸을 때 얼마나 잃느냐가 중요하다.",
    who: "George Soros",
  },
  {
    en: "There is nothing new in Wall Street. Whatever happens today has happened before and will happen again.",
    ko: "월가에 새로운 것은 없다. 오늘 일어나는 일은 전에도 일어났고 앞으로도 일어난다.",
    who: "Jesse Livermore",
  },
  {
    en: "The stock market is a device for transferring money from the impatient to the patient.",
    ko: "주식시장은 조급한 사람의 돈을 인내하는 사람에게 옮기는 장치다.",
    who: "Warren Buffett",
  },
  {
    en: "Buy when there's blood in the streets, even if the blood is your own.",
    ko: "거리에 피가 흐를 때 사라. 그 피가 당신의 것일지라도.",
    who: "Baron Rothschild",
  },
  {
    en: "The most important quality for an investor is temperament, not intellect.",
    ko: "투자자에게 가장 중요한 자질은 지성이 아니라 기질이다.",
    who: "Warren Buffett",
  },
  {
    en: "Time in the market beats timing the market.",
    ko: "시장의 타이밍을 맞추는 것보다 시장에 머무는 시간이 이긴다.",
    who: "Ken Fisher",
  },
  {
    en: "Risk comes from not knowing what you're doing.",
    ko: "위험은 자신이 무엇을 하는지 모르는 데서 온다.",
    who: "Warren Buffett",
  },
  {
    en: "You get recessions, you have stock market declines. If you don't understand that's going to happen, then you're not ready.",
    ko: "경기침체도 오고 주가 하락도 온다. 그것이 온다는 걸 이해하지 못하면 준비되지 않은 것이다.",
    who: "Peter Lynch",
  },
  {
    en: "The individual investor should act consistently as an investor and not as a speculator.",
    ko: "개인 투자자는 투기꾼이 아니라 투자자로서 일관되게 행동해야 한다.",
    who: "Benjamin Graham",
  },
];

function useRotatingQuote(intervalMs: number) {
  const [index, setIndex] = useState(() =>
    Math.floor(Math.random() * QUOTES.length),
  );
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => {
      setVisible(false);
      const swap = setTimeout(() => {
        setIndex((current) => (current + 1) % QUOTES.length);
        setVisible(true);
      }, 400);
      return () => clearTimeout(swap);
    }, intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);

  return { quote: QUOTES[index], visible };
}

/** Single rotating quote line -- landing hero, dashboard wait states. */
export function QuoteLine({
  language,
  intervalMs = 5000,
  className = "",
}: {
  language: Language;
  intervalMs?: number;
  className?: string;
}) {
  const { quote, visible } = useRotatingQuote(intervalMs);
  return (
    <div className={className} aria-live="off">
      <p
        className="transition-opacity duration-400 text-sm italic leading-relaxed text-terminal-muted"
        style={{ opacity: visible ? 1 : 0 }}
      >
        “{language === "ko" ? quote.ko : quote.en}”
        <span className="ml-2 font-mono text-[11px] not-italic tracking-widest text-terminal-faint">
          — {quote.who.toUpperCase()}
        </span>
      </p>
    </div>
  );
}

/** Full-screen loading overlay: brand mark, spinner, cycling quotes. */
export function QuoteLoadingScreen({
  language,
  label,
}: {
  language: Language;
  label: string;
}) {
  const { quote, visible } = useRotatingQuote(3000);
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-terminal-bg px-6">
      <span className="flex h-12 w-12 items-center justify-center rounded bg-signal-dim font-mono text-lg font-bold text-signal">
        KQ
      </span>
      <div className="mt-8 flex items-center gap-3">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-terminal-line border-t-signal" />
        <span className="font-mono text-[11px] tracking-[0.3em] text-terminal-muted">
          {label.toUpperCase()}
        </span>
      </div>
      <div className="mt-12 min-h-[7rem] max-w-xl text-center">
        <p
          className="text-lg italic leading-relaxed text-terminal-ink transition-opacity duration-400"
          style={{ opacity: visible ? 1 : 0 }}
        >
          “{language === "ko" ? quote.ko : quote.en}”
        </p>
        <p
          className="mt-4 font-mono text-[11px] tracking-[0.3em] text-signal transition-opacity duration-400"
          style={{ opacity: visible ? 1 : 0 }}
        >
          — {quote.who.toUpperCase()}
        </p>
      </div>
    </div>
  );
}
