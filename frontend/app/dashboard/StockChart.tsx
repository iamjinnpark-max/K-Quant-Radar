"use client";

import { MouseEvent, useMemo, useState } from "react";
import { Language } from "@/lib/language";

type ChartPoint = {
  date: string;
  close: number;
  ma20: number | null;
  ma60: number | null;
  bb_upper: number | null;
  bb_lower: number | null;
};

type Props = {
  data: unknown;
  language: Language;
};

const WIDTH = 760;
const HEIGHT = 310;
const PAD = { top: 20, right: 24, bottom: 38, left: 70 };

function parsePoints(data: unknown): ChartPoint[] {
  if (!Array.isArray(data)) return [];
  return data.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const point = item as Record<string, unknown>;
    if (typeof point.date !== "string" || typeof point.close !== "number") {
      return [];
    }
    const optionalNumber = (value: unknown) => (
      typeof value === "number" && Number.isFinite(value) ? value : null
    );
    return [{
      date: point.date,
      close: point.close,
      ma20: optionalNumber(point.ma20),
      ma60: optionalNumber(point.ma60),
      bb_upper: optionalNumber(point.bb_upper),
      bb_lower: optionalNumber(point.bb_lower),
    }];
  });
}

export default function StockChart({ data, language }: Props) {
  const allPoints = useMemo(() => parsePoints(data), [data]);
  const [period, setPeriod] = useState<63 | 126>(126);
  const [hovered, setHovered] = useState<number | null>(null);
  const points = useMemo(() => allPoints.slice(-period), [allPoints, period]);
  const ko = language === "ko";

  if (points.length < 2) {
    return (
      <section className="stock-chart chart-empty">
        {ko ? "이전 분석에는 차트 데이터가 없습니다." : "Chart data is unavailable for this historical result."}
      </section>
    );
  }

  const plotWidth = WIDTH - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;
  const values = points.flatMap((point) => [
    point.close,
    point.ma20,
    point.ma60,
    point.bb_upper,
    point.bb_lower,
  ]).filter((value): value is number => value !== null);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const margin = Math.max((rawMax - rawMin) * 0.08, rawMax * 0.005, 1);
  const min = rawMin - margin;
  const max = rawMax + margin;
  const x = (index: number) => PAD.left + (index / (points.length - 1)) * plotWidth;
  const y = (value: number) => PAD.top + ((max - value) / (max - min)) * plotHeight;

  function linePath(key: "close" | "ma20" | "ma60") {
    let started = false;
    return points.map((point, index) => {
      const value = point[key];
      if (value === null) return "";
      const command = started ? "L" : "M";
      started = true;
      return `${command}${x(index).toFixed(2)},${y(value).toFixed(2)}`;
    }).join(" ");
  }

  const upper = points.flatMap((point, index) => (
    point.bb_upper === null ? [] : [`${x(index)},${y(point.bb_upper)}`]
  ));
  const lower = points.flatMap((point, index) => (
    point.bb_lower === null ? [] : [`${x(index)},${y(point.bb_lower)}`]
  )).reverse();
  const band = [...upper, ...lower].join(" ");
  const formatPrice = (value: number) => new Intl.NumberFormat(
    ko ? "ko-KR" : "en-US",
    { maximumFractionDigits: 0 },
  ).format(value);
  const formatDate = (value: string) => {
    const date = new Date(`${value}T00:00:00`);
    return new Intl.DateTimeFormat(ko ? "ko-KR" : "en-US", {
      month: "short",
      day: "numeric",
    }).format(date);
  };
  const focus = hovered === null ? null : points[hovered];

  function move(event: MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const svgX = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const index = Math.round(((svgX - PAD.left) / plotWidth) * (points.length - 1));
    setHovered(Math.max(0, Math.min(points.length - 1, index)));
  }

  return (
    <section className="stock-chart">
      <div className="chart-head">
        <div>
          <small>{ko ? "기술적 차트" : "TECHNICAL CHART"}</small>
          <strong>{ko ? "가격 추세와 BB" : "Price trend & BB"}</strong>
        </div>
        <div className="period-toggle">
          <button className={period === 63 ? "active" : ""} onClick={() => setPeriod(63)}>
            {ko ? "3개월" : "3M"}
          </button>
          <button className={period === 126 ? "active" : ""} onClick={() => setPeriod(126)}>
            {ko ? "6개월" : "6M"}
          </button>
        </div>
      </div>
      <div className="chart-legend">
        <span className="legend-close">{ko ? "종가" : "Close"}</span>
        <span className="legend-ma20">MA20</span>
        <span className="legend-ma60">MA60</span>
        <span className="legend-band">BB</span>
      </div>
      <div className="chart-canvas">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={ko ? "주가 및 기술적 추세 차트" : "Price and technical trend chart"}
          onMouseMove={move}
          onMouseLeave={() => setHovered(null)}
        >
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const value = max - (max - min) * ratio;
            const lineY = PAD.top + plotHeight * ratio;
            return (
              <g key={ratio}>
                <line className="chart-grid-line" x1={PAD.left} x2={WIDTH - PAD.right} y1={lineY} y2={lineY} />
                <text className="chart-axis-label" x={PAD.left - 10} y={lineY + 4} textAnchor="end">{formatPrice(value)}</text>
              </g>
            );
          })}
          {band && <polygon className="bollinger-area" points={band} />}
          <path className="chart-line ma60-line" d={linePath("ma60")} />
          <path className="chart-line ma20-line" d={linePath("ma20")} />
          <path className="chart-line close-line" d={linePath("close")} />
          {[0, Math.floor((points.length - 1) / 2), points.length - 1].map((index) => (
            <text key={index} className="chart-axis-label" x={x(index)} y={HEIGHT - 11} textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"}>
              {formatDate(points[index].date)}
            </text>
          ))}
          {focus && hovered !== null && (
            <g>
              <line className="chart-focus-line" x1={x(hovered)} x2={x(hovered)} y1={PAD.top} y2={HEIGHT - PAD.bottom} />
              <circle className="chart-focus-dot" cx={x(hovered)} cy={y(focus.close)} r="5" />
            </g>
          )}
        </svg>
        {focus && hovered !== null && (
          <div className="chart-tooltip" style={{ left: `${(x(hovered) / WIDTH) * 100}%` }}>
            <small>{focus.date}</small>
            <strong>{formatPrice(focus.close)} {ko ? "원" : "KRW"}</strong>
            <span>MA20 {focus.ma20 === null ? "—" : formatPrice(focus.ma20)}</span>
            <span>MA60 {focus.ma60 === null ? "—" : formatPrice(focus.ma60)}</span>
          </div>
        )}
      </div>
    </section>
  );
}
