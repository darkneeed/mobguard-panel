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
  status: string;
  created_at: string;
  updated_at: string;
};

export function AiLearningSuggestionsSection({ t, language, canWriteData = true }: Props) {
  const { pushToast } = useToast();
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionPending, setActionPending] = useState<Record<number, "accept" | "reject" | null>>({});

  const loadSuggestions = async () => {
    try {
      setLoading(true);
      const data = await api.getAiSuggestions();
      // Filter to keep only PENDING suggestions
      setSuggestions(data.filter((s: any) => s.status === "PENDING"));
    } catch (err) {
      pushToast("error", err instanceof Error ? err.message : t("data.errors.loadTabFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSuggestions();
  }, []);

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

  if (suggestions.length === 0) {
    return (
      <div className="panel" style={{ textAlign: "center", padding: "3rem" }}>
        <Sparkles size={48} className="muted" style={{ margin: "0 auto 1.5rem auto", opacity: 0.5 }} />
        <h2>{t("data.aiSuggestions.pageTitle")}</h2>
        <p className="muted" style={{ maxWidth: "500px", margin: "0.5rem auto 0 auto" }}>
          {t("data.aiSuggestions.empty")}
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div className="panel-heading" style={{ marginBottom: "0.5rem" }}>
        <h2>{t("data.aiSuggestions.pageTitle")}</h2>
        <p className="muted">{t("data.aiSuggestions.pageDescription")}</p>
      </div>

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
    </div>
  );
}
