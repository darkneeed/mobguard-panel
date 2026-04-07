import { useEffect, useState } from "react";

import { api } from "../api/client";

type PromotedLearningTypeSummary = {
  pattern_type: string;
  count: number;
  total_support: number;
  avg_precision: number;
};

type PromotedPattern = {
  pattern_type: string;
  pattern_value: string;
  decision: string;
  support: number;
  precision: number;
};

type LegacyLearningTypeSummary = {
  pattern_type: string;
  count: number;
  total_confidence: number;
};

type LegacyLearningPattern = {
  pattern_type: string;
  pattern_value: string;
  decision: string;
  confidence: number;
  timestamp: string;
};

type QualityPayload = {
  open_cases: number;
  total_cases: number;
  resolved_home: number;
  resolved_mobile: number;
  skipped: number;
  resolution_total: number;
  active_learning_patterns: number;
  active_sessions: number;
  live_rules_revision: number;
  live_rules_updated_at: string;
  live_rules_updated_by: string;
  top_noisy_asns: Array<{ asn_key: string; cnt: number }>;
  top_patterns: PromotedPattern[];
  asn_source: {
    type: string;
    label: string;
    files: string[];
  };
  learning: {
    thresholds: {
      asn_min_support: number;
      asn_min_precision: number;
      combo_min_support: number;
      combo_min_precision: number;
    };
    promoted: {
      active_patterns: number;
      by_type: PromotedLearningTypeSummary[];
      top_patterns: PromotedPattern[];
    };
    legacy: {
      total_patterns: number;
      total_confidence: number;
      by_type: LegacyLearningTypeSummary[];
      top_patterns: LegacyLearningPattern[];
    };
  };
};

function formatUpdatedBy(value: string): string {
  if (!value || value === "bootstrap") return "system";
  return value;
}

export function QualityPage() {
  const [data, setData] = useState<QualityPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getQuality()
      .then((payload) => setData(payload as QualityPayload))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Quality</span>
          <h1>Шумные ASN, объём ревью и активные паттерны</h1>
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      {!data ? <div className="panel">Loading…</div> : null}

      {data ? (
        <>
          <div className="stats-grid">
            <div className="stat-card"><span>Open cases</span><strong>{data.open_cases}</strong></div>
            <div className="stat-card"><span>Total cases</span><strong>{data.total_cases}</strong></div>
            <div className="stat-card"><span>Resolved HOME</span><strong>{data.resolved_home}</strong></div>
            <div className="stat-card"><span>Resolved MOBILE</span><strong>{data.resolved_mobile}</strong></div>
            <div className="stat-card"><span>Skipped</span><strong>{data.skipped}</strong></div>
            <div className="stat-card"><span>Active patterns</span><strong>{data.active_learning_patterns}</strong></div>
            <div className="stat-card"><span>Active sessions</span><strong>{data.active_sessions}</strong></div>
            <div className="stat-card">
              <span>HOME ratio</span>
              <strong>
                {data.resolution_total > 0
                  ? `${Math.round((data.resolved_home / data.resolution_total) * 100)}%`
                  : "0%"}
              </strong>
            </div>
            <div className="stat-card">
              <span>MOBILE ratio</span>
              <strong>
                {data.resolution_total > 0
                  ? `${Math.round((data.resolved_mobile / data.resolution_total) * 100)}%`
                  : "0%"}
              </strong>
            </div>
          </div>
          <div className="panel queue-footer">
            <span>Rules revision {data.live_rules_revision}</span>
            <span>Updated {data.live_rules_updated_at}</span>
            <span>By {formatUpdatedBy(data.live_rules_updated_by)}</span>
          </div>
          <div className="panel">
            <h2>ASN source</h2>
            <ul className="reason-list">
              <li>
                <strong>{data.asn_source.label}</strong>
                <span>{data.asn_source.type}</span>
                <span>{data.asn_source.files.length > 0 ? data.asn_source.files.join(", ") : "No ASN source available"}</span>
              </li>
            </ul>
          </div>
          <div className="panel">
            <h2>Top noisy ASN</h2>
            <ul className="reason-list">
              {data.top_noisy_asns.map((item) => (
                <li key={item.asn_key}>
                  <strong>{item.asn_key}</strong>
                  <span>{item.cnt} review cases</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>Top promoted patterns</h2>
            <ul className="reason-list">
              {data.learning.promoted.top_patterns.map((item) => (
                <li key={`${item.pattern_type}:${item.pattern_value}`}>
                  <strong>{item.pattern_type}:{item.pattern_value}</strong>
                  <span>
                    {item.decision} · support {item.support} · precision{" "}
                    {Math.round(item.precision * 100)}%
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>Learning state</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <span>Promoted patterns</span>
                <strong>{data.learning.promoted.active_patterns}</strong>
              </div>
              <div className="stat-card">
                <span>Legacy patterns</span>
                <strong>{data.learning.legacy.total_patterns}</strong>
              </div>
              <div className="stat-card">
                <span>Legacy confidence</span>
                <strong>{data.learning.legacy.total_confidence}</strong>
              </div>
              <div className="stat-card">
                <span>ASN min support</span>
                <strong>{data.learning.thresholds.asn_min_support}</strong>
              </div>
              <div className="stat-card">
                <span>ASN min precision</span>
                <strong>{Math.round(data.learning.thresholds.asn_min_precision * 100)}%</strong>
              </div>
              <div className="stat-card">
                <span>Combo min support</span>
                <strong>{data.learning.thresholds.combo_min_support}</strong>
              </div>
              <div className="stat-card">
                <span>Combo min precision</span>
                <strong>{Math.round(data.learning.thresholds.combo_min_precision * 100)}%</strong>
              </div>
            </div>
          </div>
          <div className="panel">
            <h2>Promoted learning by type</h2>
            <ul className="reason-list">
              {data.learning.promoted.by_type.length === 0 ? <li><span>No promoted data yet</span></li> : null}
              {data.learning.promoted.by_type.map((item) => (
                <li key={item.pattern_type}>
                  <strong>{item.pattern_type}</strong>
                  <span>
                    {item.count} patterns · support {item.total_support} · avg precision{" "}
                    {Math.round(item.avg_precision * 100)}%
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>Legacy learning by type</h2>
            <ul className="reason-list">
              {data.learning.legacy.by_type.length === 0 ? <li><span>No legacy learning data yet</span></li> : null}
              {data.learning.legacy.by_type.map((item) => (
                <li key={item.pattern_type}>
                  <strong>{item.pattern_type}</strong>
                  <span>
                    {item.count} patterns · accumulated confidence {item.total_confidence}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="panel">
            <h2>Top legacy learning patterns</h2>
            <ul className="reason-list">
              {data.learning.legacy.top_patterns.length === 0 ? <li><span>No legacy patterns yet</span></li> : null}
              {data.learning.legacy.top_patterns.map((item) => (
                <li key={`${item.pattern_type}:${item.pattern_value}:${item.decision}`}>
                  <strong>{item.pattern_type}:{item.pattern_value}</strong>
                  <span>
                    {item.decision} · confidence {item.confidence}
                  </span>
                  <span>{item.timestamp}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </section>
  );
}
