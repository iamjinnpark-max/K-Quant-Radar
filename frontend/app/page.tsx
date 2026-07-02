"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { authEnabled, currentSession, logout } from "@/lib/auth";

type Recommendation = {
  rank: number;
  ticker: string;
  company: string;
  data: Record<string, string | number | null>;
};
type Job = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  error?: string;
  recommendations: Recommendation[];
};
type User = {
  display_name?: string;
  email?: string;
  is_owner: boolean;
  plan: string;
  subscription_status: string;
};

const sectors = ["AI", "Semiconductors", "EV", "Biotech", "Finance", "Internet", "Energy"];

export default function Dashboard() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [selected, setSelected] = useState<Recommendation | null>(null);
  const [selections, setSelections] = useState(["AI"]);
  const [error, setError] = useState("");
  const [previewMember, setPreviewMember] = useState(false);

  const memberView = Boolean(user?.is_owner && previewMember);
  const effectiveOwner = Boolean(user?.is_owner && !memberView);

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }),
    [token],
  );

  useEffect(() => {
    currentSession()
      .then(async (session) => {
        setToken(session.token);
        const response = await fetch("/api/v1/me", {
          headers: session.token
            ? { Authorization: `Bearer ${session.token}` }
            : {},
        });
        if (!response.ok) throw new Error("Could not load account.");
        setUser(await response.json());
      })
      .catch(() => {
        if (authEnabled) location.assign("/login");
      });
  }, []);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      const response = await fetch(`/api/v1/recommendation-jobs/${job.id}`, { headers });
      if (!response.ok) return;
      const next = await response.json();
      setJob(next);
      if (next.status === "completed" && next.recommendations.length) {
        setSelected(next.recommendations[0]);
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [job, headers]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSelected(null);
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/v1/recommendation-jobs", {
      method: "POST",
      headers,
      body: JSON.stringify({
        market: "Korea",
        risk_level: form.get("risk"),
        style: form.get("style"),
        time_horizon: form.get("horizon"),
        favorite_sectors: selections,
        scan_limit: Number(form.get("scanLimit")),
      }),
    });
    if (response.status === 402) {
      setError("Choose a subscription to run personalized scans.");
      return;
    }
    if (!response.ok) {
      setError("Could not start the scan.");
      return;
    }
    const created = await response.json();
    setJob({ ...created, recommendations: [] });
  }

  async function billing(path: "checkout" | "portal") {
    if (memberView) {
      window.alert("Member preview: this button opens Stripe Checkout for a real customer.");
      return;
    }
    const response = await fetch(`/api/v1/billing/${path}`, {
      method: "POST",
      headers,
    });
    const result = await response.json();
    if (result.url) location.assign(result.url);
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span>KQ</span><strong>K-Quant</strong></div>
        <nav>
          <a className="active" href="#overview"><i>⌁</i>Overview</a>
          <a href="#recommendations"><i>↗</i>Recommendations</a>
          <a href="#analysis"><i>◇</i>Analysis</a>
          <a href="#account"><i>○</i>Account</a>
        </nav>
        <div className="account" id="account">
          <div className="account-status">
            <i />
            <small>{effectiveOwner ? "OWNER ACCESS" : `${memberView ? "FREE" : user?.plan?.toUpperCase() ?? "ACCOUNT"} PLAN`}</small>
          </div>
          <strong>{memberView ? "Member preview" : user?.display_name || user?.email || "Loading…"}</strong>
          {!effectiveOwner && (
            <button onClick={() => billing(user?.subscription_status === "active" ? "portal" : "checkout")}>
              {memberView || user?.subscription_status !== "active" ? "Upgrade to K-Quant Pro →" : "Manage billing →"}
            </button>
          )}
          {user?.is_owner && (
            <button className="preview-toggle" onClick={() => setPreviewMember((value) => !value)}>
              {previewMember ? "Return to owner view" : "Preview member view"}
            </button>
          )}
          {authEnabled && <button onClick={() => logout()}>Sign out</button>}
        </div>
      </aside>

      <section className="dashboard" id="overview">
        <header className="topbar">
          <div>
            <small>MARKET WORKSPACE · SEOUL</small>
            <h1>Good signals start<br />with context.</h1>
            <p>KOSPI + KOSDAQ intelligence, shaped around your strategy.</p>
          </div>
          <div className="topbar-actions">
            <span className={`plan-badge ${effectiveOwner ? "owner" : ""}`}>
              {effectiveOwner ? "Founder" : memberView ? "Free preview" : user?.plan || "Account"}
            </span>
            <div className="live"><i /> KRX DATA LIVE</div>
          </div>
        </header>

        <div className="dashboard-grid">
          <form onSubmit={submit} className="card profile-card">
            <div className="card-head">
              <div><span className="section-number">01</span><h2>Build your scan</h2></div>
              <span>PERSONALIZED</span>
            </div>
            <div className="scan-intro">
              <div>
                <small>YOUR STRATEGY DNA</small>
                <strong>{selections.length || "No"} theme{selections.length === 1 ? "" : "s"} selected</strong>
              </div>
              <div className="signal-orbit" aria-hidden="true"><i /><i /><b>KQ</b></div>
            </div>
            <div className="form-grid">
              <label>Risk<select name="risk" defaultValue="Medium"><option>Low</option><option>Medium</option><option>High</option></select></label>
              <label>Style<select name="style"><option>Growth</option><option>Value</option><option>Dividend</option></select></label>
              <label>Horizon<select name="horizon"><option>0-3 Months</option><option>3-6 Months</option><option>6-12 Months</option><option>1+ Years</option></select></label>
              <label>Scan size<select name="scanLimit" defaultValue="10"><option>10</option><option>20</option><option>30</option><option>40</option><option>60</option></select></label>
            </div>
            <div className="theme-heading">
              <label className="theme-label">Preferred themes</label>
              <small>{selections.length}/7 ACTIVE</small>
            </div>
            <div className="chips">{sectors.map((sector) => (
              <button type="button" key={sector} className={selections.includes(sector) ? "chip active" : "chip"}
                onClick={() => setSelections((items) => items.includes(sector) ? items.filter((x) => x !== sector) : [...items, sector])}>
                {sector}
              </button>
            ))}</div>
            <button className="primary"><span>Run personalized scan</span><b>↗</b></button>
            <div className="scan-foot"><i /> Balanced across KOSPI + KOSDAQ</div>
            {error && <p className="error">{error}</p>}
          </form>

          <section className="card ranking-card" id="recommendations">
            <div className="card-head">
              <div><span className="section-number">02</span><h2>Ranked opportunities</h2></div>
              <span className="result-count">{job?.recommendations.length ?? 0} RESULTS</span>
            </div>
            {!job && <div className="empty">Run a profile scan to begin.</div>}
            {job && ["queued", "running"].includes(job.status) && <div className="empty pulse">{job.status === "queued" ? "Queued" : "Analyzing KOSPI + KOSDAQ"}…</div>}
            {job?.status === "failed" && <div className="error">{job.error}</div>}
            <div className="ranking-list">{job?.recommendations.map((item) => (
              <button key={item.ticker} className={selected?.ticker === item.ticker ? "stock-row selected" : "stock-row"} onClick={() => setSelected(item)}>
                <span className="rank">{item.rank}</span>
                <span><strong>{item.company}</strong><small>{item.ticker} · {String(item.data.Market)}</small></span>
                <span><small>Signal</small><strong>{String(item.data.Signal)}</strong></span>
                <span className="score">{Number(item.data["Personalized Score"]).toFixed(1)}<small>MATCH</small></span>
              </button>
            ))}</div>
          </section>

          <section className="card analysis-card" id="analysis">
            <div className="card-head">
              <div><span className="section-number">03</span><h2>Stock analysis</h2></div>
              <span>EVIDENCE VIEW</span>
            </div>
            {!selected && <div className="empty">Select a recommendation to inspect its evidence.</div>}
            {selected && (
              <>
                <div className="stock-title"><div><small>{selected.ticker} · {String(selected.data.Market)}</small><h3>{selected.company}</h3></div><b>{String(selected.data.Action)}</b></div>
                <div className="metrics">
                  <div><small>Bullish probability</small><strong>{Number(selected.data["Bullish Probability (%)"]).toFixed(1)}%</strong><span style={{width: `${Number(selected.data["Bullish Probability (%)"])}%`}} /></div>
                  <div><small>Alpha score</small><strong>{Number(selected.data["Alpha Score"]).toFixed(1)}</strong><span style={{width: `${Number(selected.data["Alpha Score"])}%`}} /></div>
                  <div><small>Model accuracy</small><strong>{Number(selected.data["Model Accuracy (%)"]).toFixed(1)}%</strong><span style={{width: `${Number(selected.data["Model Accuracy (%)"])}%`}} /></div>
                  <div className={`risk risk-${String(selected.data.Risk).toLowerCase()}`}><small>Risk profile</small><strong>{String(selected.data.Risk)}</strong><em>●</em></div>
                </div>
                <div className="analysis-copy"><small>MODEL-GROUNDED ANALYSIS</small><p>{String(selected.data["AI Analysis"] ?? "Analysis is unavailable for this historical result.")}</p></div>
                <div className="disclaimer">Research signal only. Not investment advice.</div>
              </>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
