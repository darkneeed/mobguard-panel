import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, X, ArrowRight, AlertTriangle, Loader2, Sparkles } from "lucide-react";

import { api } from "../../api/client";
import { useToast } from "../../components/ToastProvider";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

type Props = {
  t: TranslateFn;
  language: string;
  canWriteData?: boolean;
};

type AISuggestion = {
  id: number;
  pattern_type: string;
  pattern_value: string;
  current_decision: string | null;
  suggested_decision: string;
  confidence: number;
  reasoning_ru: string;
  operator_errors_json: string | null;
  suggested_provider_profile_json: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export function AiLearningSuggestionsSection({ t, language, canWriteData = true }: Props) {
  const { pushToast } = useToast();
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionPending, setActionPending] = useState<Record<number, "accept" | "reject" | null>>({});
  const [currentProfiles, setCurrentProfiles] = useState<any[]>([]);
  const [status, setStatus] = useState<{
    last_run: string | null;
    cooldown_seconds: number;
    seconds_remaining: number;
    can_run: boolean;
  } | null>(null);
  const [generating, setGenerating] = useState(false);

  const loadSuggestions = async () => {
    try {
      setLoading(true);
      const [data, rules, statusData] = await Promise.all([
        api.getAiSuggestions(),
        api.getDetectionSettings(),
        api.getAiSuggestionsStatus()
      ]);
      // Filter to keep only PENDING suggestions
      setSuggestions(data.filter((s: any) => s.status === "PENDING"));
      setCurrentProfiles((rules as any).rules?.provider_profiles || []);
      setStatus(statusData);
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.loadTabFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSuggestions();
  }, []);

  useEffect(() => {
    if (!status || status.seconds_remaining <= 0) return;
    const interval = setInterval(() => {
      setStatus(prev => {
        if (!prev) return null;
        const nextSec = prev.seconds_remaining - 1;
        return {
          ...prev,
          seconds_remaining: nextSec > 0 ? nextSec : 0,
          can_run: nextSec <= 0
        };
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [status]);

  const handleGenerate = async () => {
    try {
      setGenerating(true);
      const res = await api.generateAiSuggestions();
      pushToast("success", res.message || "AI suggestions generation triggered successfully");
      await loadSuggestions();
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : "Failed to trigger AI suggestions generation");
    } finally {
      setGenerating(false);
    }
  };

  const formatRemainingTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) {
      return `${h} ч. ${m} мин.`;
    }
    if (m > 0) {
      return `${m} мин. ${s} сек.`;
    }
    return `${s} сек.`;
  };

  const formatLastRun = (isoString: string | null) => {
    if (!isoString) return t("data.aiSuggestions.status.neverRun") || "Никогда";
    try {
      const date = new Date(isoString);
      return date.toLocaleString(language === "ru" ? "ru-RU" : "en-US");
    } catch (e) {
      return isoString;
    }
  };

  const handleAccept = async (id: number) => {
    setActionPending(prev => ({ ...prev, [id]: "accept" }));
    try {
      await api.acceptAiSuggestion(id);
      pushToast("success", t("data.saved.suggestionAccepted"));
      // Remove from local list
      setSuggestions(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.userActionFailed"));
    } finally {
      setActionPending(prev => ({ ...prev, [id]: null }));
    }
  };

  const handleReject = async (id: number) => {
    setActionPending(prev => ({ ...prev, [id]: "reject" }));
    try {
      await api.rejectAiSuggestion(id);
      pushToast("success", t("data.saved.suggestionRejected"));
      // Remove from local list
      setSuggestions(prev => prev.filter(s => s.id !== id));
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.userActionFailed"));
    } finally {
      setActionPending(prev => ({ ...prev, [id]: null }));
    }
  };

  const getConfidenceColor = (conf: number) => {
    if (conf >= 0.90) return "var(--success)";
    if (conf >= 0.75) return "var(--warning)";
    return "var(--danger)";
  };

  const getDecisionBadgeClass = (decision: string) => {
    if (decision === "MOBILE") return "status-resolved";
    if (decision === "HOME") return "severity-low";
    if (decision === "HOSTING") return "punitive";
    return "muted";
  };

  const parseOperatorErrors = (jsonStr: string | null): number[] => {
    if (!jsonStr) return [];
    try {
      const parsed = JSON.parse(jsonStr);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  };

  if (loading) {
    return (
      <div className="provider-empty" style={{ display: "flex", flexDirection: "column", gap: "1rem", minHeight: "200px" }}>
        <Loader2 className="spinner" size={32} />
        <span>{t("data.aiSuggestions.loading")}</span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="panel-heading" style={{ marginBottom: "0.5rem" }}>
        <h2>{t("data.aiSuggestions.pageTitle")}</h2>
        <p className="muted">{t("data.aiSuggestions.pageDescription")}</p>
      </div>

      {/* AI Cooldown and Action Card */}
      <div
        className="panel"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "1.5rem",
          padding: "1.25rem 1.5rem",
          border: "1px solid var(--line)",
          borderRadius: "16px",
          background: "linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(168, 85, 247, 0.05) 100%)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
            {t("data.aiSuggestions.status.lastRun") || "Последнее обновление"}:{" "}
            <strong style={{ color: "var(--ink)" }}>{status ? formatLastRun(status.last_run) : "..."}</strong>
          </span>
          {status && status.seconds_remaining > 0 && (
            <span style={{ fontSize: "0.85rem", color: "var(--warning)" }}>
              {t("data.aiSuggestions.status.cooldownActive") || "Доступно через"}:{" "}
              <strong>{formatRemainingTime(status.seconds_remaining)}</strong>
            </span>
          )}
        </div>
        <div>
          <button
            disabled={!canWriteData || generating || (status ? !status.can_run : true)}
            onClick={handleGenerate}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              background: (status && !status.can_run) ? "var(--surface-soft)" : "var(--accent)",
              color: (status && !status.can_run) ? "var(--muted)" : "#fff",
              border: 0,
              cursor: (status && !status.can_run) ? "not-allowed" : "pointer",
              padding: "0.6rem 1.25rem",
              borderRadius: "8px",
              fontWeight: 600,
              fontSize: "0.875rem",
              transition: "all 0.2s"
            }}
          >
            {generating ? (
              <Loader2 size={16} className="spinner" />
            ) : (
              <Sparkles size={16} />
            )}
            {generating
              ? (t("data.aiSuggestions.status.generating") || "Обновление...")
              : (t("data.aiSuggestions.status.generateButton") || "Обновить рекомендации")}
          </button>
        </div>
      </div>

      {suggestions.length === 0 ? (
        <div className="panel" style={{ textAlign: "center", padding: "3rem" }}>
          <Sparkles size={48} className="muted" style={{ margin: "0 auto 1.5rem auto", opacity: 0.5 }} />
          <h2>{t("data.aiSuggestions.emptyTitle") || t("data.aiSuggestions.pageTitle")}</h2>
          <p className="muted" style={{ maxWidth: "500px", margin: "0.5rem auto 0 auto" }}>
            {t("data.aiSuggestions.empty")}
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {suggestions.map((sug) => {
          const errors = parseOperatorErrors(sug.operator_errors_json);
          const isPendingAccept = actionPending[sug.id] === "accept";
          const isPendingReject = actionPending[sug.id] === "reject";
          const anyPending = actionPending[sug.id] !== null && actionPending[sug.id] !== undefined;

          return (
            <div
              key={sug.id}
              className="panel"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "1.25rem",
                padding: "1.5rem",
                border: "1px solid var(--line)",
                borderRadius: "16px",
                position: "relative",
                overflow: "hidden"
              }}
            >
              {/* Pattern Info Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <span className="tag" style={{ textTransform: "uppercase", fontSize: "0.7rem", fontWeight: 700 }}>
                    {sug.pattern_type}
                  </span>
                  <strong style={{ fontSize: "1.25rem", color: "var(--ink)", fontFamily: "var(--font-display)" }}>
                    {sug.pattern_value}
                  </strong>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    padding: "0.3rem 0.6rem",
                    borderRadius: "8px",
                    background: "rgba(255, 255, 255, 0.02)",
                    border: `1px solid ${getConfidenceColor(sug.confidence)}`,
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    color: getConfidenceColor(sug.confidence)
                  }}
                >
                  <Sparkles size={14} />
                  <span>{t("data.aiSuggestions.confidence", { value: Math.round(sug.confidence * 100) })}</span>
                </div>
              </div>

              {/* Decision Transformation Row */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "1rem",
                  fontSize: "0.9rem",
                  background: "rgba(0, 0, 0, 0.08)",
                  padding: "0.75rem 1rem",
                  borderRadius: "10px",
                  border: "1px solid var(--line)"
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                    {t("data.aiSuggestions.currentDecision")}
                  </span>
                  <span className={`status-badge ${getDecisionBadgeClass(sug.current_decision || "UNSURE")}`} style={{ fontWeight: 700 }}>
                    {sug.current_decision || "UNSURE"}
                  </span>
                </div>

                <ArrowRight size={18} className="muted" />

                <div style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                    {t("data.aiSuggestions.suggestedDecision")}
                  </span>
                  <span className={`status-badge ${getDecisionBadgeClass(sug.suggested_decision)}`} style={{ fontWeight: 700 }}>
                    {sug.suggested_decision}
                  </span>
                </div>
              </div>

              {/* Reasoning Description */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                <span style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                  {t("data.aiSuggestions.reasoning")}
                </span>
                <p style={{ fontSize: "0.9rem", color: "var(--ink)", lineHeight: "1.5", margin: 0 }}>
                  {sug.reasoning_ru}
                </p>
              </div>
              
              {/* Recommended Operator Profile */}
              {sug.suggested_provider_profile_json ? (() => {
                try {
                  const prof = JSON.parse(sug.suggested_provider_profile_json);
                  if (!prof || !prof.key) return null;
                  const exists = currentProfiles.some(p => p.key === prof.key);
                  return (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "0.5rem",
                        borderTop: "1px solid var(--line)",
                        paddingTop: "1rem"
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", color: "var(--success)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <Sparkles size={16} />
                          <span style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                            {t("data.aiSuggestions.operatorProfile")}
                          </span>
                        </div>
                        {exists ? (
                          <span style={{ fontSize: "0.75rem", fontWeight: 600, background: "rgba(249, 115, 22, 0.15)", color: "rgb(249, 115, 22)", padding: "0.15rem 0.45rem", borderRadius: "4px", border: "1px solid rgba(249, 115, 22, 0.2)" }}>
                            {t("data.aiSuggestions.profileActionUpdate")}
                          </span>
                        ) : (
                          <span style={{ fontSize: "0.75rem", fontWeight: 600, background: "rgba(16, 185, 129, 0.15)", color: "rgb(16, 185, 129)", padding: "0.15rem 0.45rem", borderRadius: "4px", border: "1px solid rgba(16, 185, 129, 0.2)" }}>
                            {t("data.aiSuggestions.profileActionCreate")}
                          </span>
                        )}
                      </div>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                          gap: "1rem",
                          background: "rgba(255, 255, 255, 0.01)",
                          padding: "1rem",
                          borderRadius: "10px",
                          border: "1px solid rgba(255, 255, 255, 0.03)",
                          fontSize: "0.85rem"
                        }}
                      >
                        <div>
                          <span style={{ color: "var(--muted)" }}>{t("data.aiSuggestions.profileKey")}:</span>{" "}
                          <strong style={{ color: "var(--ink)" }}>{prof.key}</strong>
                        </div>
                        <div>
                          <span style={{ color: "var(--muted)" }}>{t("data.aiSuggestions.profileClassification")}:</span>{" "}
                          <span className={`status-badge ${getDecisionBadgeClass(prof.classification.toUpperCase())}`} style={{ fontWeight: 700 }}>
                            {prof.classification}
                          </span>
                        </div>
                        {prof.aliases && prof.aliases.length > 0 && (
                          <div style={{ gridColumn: "1 / -1" }}>
                            <span style={{ color: "var(--muted)" }}>{t("data.aiSuggestions.profileAliases")}:</span>{" "}
                            <span style={{ color: "var(--ink)" }}>{prof.aliases.join(", ")}</span>
                          </div>
                        )}
                        {((prof.mobile_markers && prof.mobile_markers.length > 0) || (prof.home_markers && prof.home_markers.length > 0)) && (
                          <div style={{ gridColumn: "1 / -1" }}>
                            <span style={{ color: "var(--muted)" }}>{t("data.aiSuggestions.profileMarkers")}:</span>{" "}
                            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.25rem" }}>
                              {prof.mobile_markers?.map((m: string) => (
                                <span key={m} className="tag status-resolved" style={{ fontSize: "0.75rem" }}>{m}</span>
                              ))}
                              {prof.home_markers?.map((m: string) => (
                                <span key={m} className="tag severity-low" style={{ fontSize: "0.75rem" }}>{m}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        {prof.asns && prof.asns.length > 0 && (
                          <div style={{ gridColumn: "1 / -1" }}>
                            <span style={{ color: "var(--muted)" }}>{t("data.aiSuggestions.profileAsns")}:</span>{" "}
                            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginTop: "0.25rem" }}>
                              {prof.asns.map((asn: number) => (
                                <span key={asn} className="tag" style={{ fontSize: "0.75rem", background: "rgba(255,255,255,0.05)" }}>AS{asn}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                } catch (e) {
                  return null;
                }
              })() : null}

              {/* Erroneous Cases List */}
              {errors.length > 0 ? (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                    borderTop: "1px solid var(--line)",
                    paddingTop: "1rem"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--warning)" }}>
                    <AlertTriangle size={16} />
                    <span style={{ fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                      {t("data.aiSuggestions.operatorErrors")}
                    </span>
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                    {t("data.aiSuggestions.operatorErrorsDetail", { count: errors.length })}:
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.25rem" }}>
                    {errors.map((eid) => (
                      <Link
                        key={eid}
                        to={`/reviews/${eid}`}
                        className="tag inline-link"
                        style={{
                          fontSize: "0.75rem",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "6px",
                          fontWeight: 600,
                          background: "rgba(255, 170, 0, 0.05)",
                          border: "1px solid rgba(255, 170, 0, 0.2)",
                          color: "var(--warning)"
                        }}
                      >
                        #{eid}
                      </Link>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* Actions Footer */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: "0.75rem",
                  borderTop: "1px solid var(--line)",
                  paddingTop: "1rem",
                  marginTop: "0.5rem"
                }}
              >
                <button
                  className="ghost"
                  disabled={!canWriteData || anyPending}
                  onClick={() => handleReject(sug.id)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    borderColor: "var(--line)",
                    color: "var(--danger)"
                  }}
                >
                  {isPendingReject ? <Loader2 size={16} className="spinner" /> : <X size={16} />}
                  {isPendingReject ? t("data.aiSuggestions.actions.rejecting") : t("data.aiSuggestions.actions.reject")}
                </button>

                <button
                  disabled={!canWriteData || anyPending}
                  onClick={() => handleAccept(sug.id)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    background: "var(--success)",
                    color: "#fff"
                  }}
                >
                  {isPendingAccept ? <Loader2 size={16} className="spinner" /> : <Check size={16} />}
                  {isPendingAccept ? t("data.aiSuggestions.actions.accepting") : t("data.aiSuggestions.actions.accept")}
                </button>
              </div>
            </div>
          );
        })}
        </div>
      )}
    </div>
  );
}
