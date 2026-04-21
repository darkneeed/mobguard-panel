import { Link } from "react-router-dom";

import { api, LearningAdminResponse, ReviewListResponse } from "../../api/client";
import type { Language } from "../../localization/types";
import { formatDisplayDateTime } from "../../utils/datetime";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;
type Mode = "learning" | "cases";

type Props = {
  mode: Mode;
  t: TranslateFn;
  language: Language;
  learning: LearningAdminResponse | null;
  cases: ReviewListResponse | null;
  setLearning: (value: LearningAdminResponse) => void;
  pushToast: (kind: "success" | "error" | "warning" | "info", message: string) => void;
};

export function LearningCasesSection({
  mode,
  t,
  language,
  learning,
  cases,
  setLearning,
  pushToast,
}: Props) {
  if (mode === "cases") {
    const items = cases?.items || [];
    return (
      <div className="panel">
        <h2>{t("data.cases.title")}</h2>
        <div className="record-list">
          {items.map((item) => (
            <Link className="record-item inline-link" key={String(item.id)} to={`/reviews/${item.id}`}>
              <div className="record-main">
                <span className="record-title">#{String(item.id)} · {String(item.username || item.uuid || t("common.notAvailable"))}</span>
                <span className="tag">{String(item.review_reason)}</span>
              </div>
              <div className="record-meta">
                <span>{String(item.ip)}</span>
                <span>{formatDisplayDateTime(String(item.updated_at ?? ""), t("common.notAvailable"), language)}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  const promotedActive = (learning?.promoted_active as Array<Record<string, unknown>> | undefined) || [];
  const promotedStats = (learning?.promoted_stats as Array<Record<string, unknown>> | undefined) || [];
  const legacy = (learning?.legacy as Array<Record<string, unknown>> | undefined) || [];
  const promotedProviderActive = (learning?.promoted_provider_active as Array<Record<string, unknown>> | undefined) || [];
  const promotedProviderServiceActive = (learning?.promoted_provider_service_active as Array<Record<string, unknown>> | undefined) || [];
  const legacyProvider = (learning?.legacy_provider as Array<Record<string, unknown>> | undefined) || [];
  const legacyProviderService = (learning?.legacy_provider_service as Array<Record<string, unknown>> | undefined) || [];

  return (
    <div className="detail-grid">
      <div className="panel">
        <h2>{t("data.learning.promotedActiveTitle")}</h2>
        <div className="record-list">
          {promotedActive.map((item) => (
            <div className="record-item" key={`${String(item.pattern_type)}:${String(item.pattern_value)}`}>
              <div className="record-main">
                <span className="record-title">{String(item.pattern_type)}:{String(item.pattern_value)}</span>
                <span className="tag">{String(item.decision)}</span>
              </div>
              <div className="record-meta">
                <span>{t("data.learning.support", { value: String(item.support) })}</span>
                <span>{t("data.learning.precision", { value: String(item.precision) })}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>{t("data.learning.promotedStatsTitle")}</h2>
        <div className="record-list">
          {promotedStats.map((item) => (
            <div className="record-item" key={`${String(item.pattern_type)}:${String(item.pattern_value)}:${String(item.decision)}`}>
              <div className="record-main">
                <span className="record-title">{String(item.pattern_type)}:{String(item.pattern_value)}</span>
                <span className="tag">{String(item.decision)}</span>
              </div>
              <div className="record-meta">
                <span>{t("data.learning.total", { value: String(item.total) })}</span>
                <span>{t("data.learning.precision", { value: String(item.precision) })}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>{t("data.learning.legacyTitle")}</h2>
        <div className="record-list">
          {legacy.map((item) => (
            <div className="record-item" key={String(item.id)}>
              <div className="record-main">
                <span className="record-title">{String(item.pattern_type)}:{String(item.pattern_value)}</span>
                <span className="tag">{String(item.decision)}</span>
              </div>
              <div className="record-meta">
                <span>{t("data.learning.confidence", { value: String(item.confidence) })}</span>
              </div>
              <div className="record-actions">
                <button className="ghost" onClick={async () => {
                  try {
                    await api.patchLegacyLearning(Number(item.id), { confidence: Number(item.confidence) + 1 });
                    setLearning(await api.getLearningAdmin());
                    pushToast("success", t("data.saved.learningUpdated"));
                  } catch (err) {
                    pushToast("error", err instanceof Error ? err.message : t("data.errors.loadTabFailed"));
                  }
                }}>{t("data.learning.plusOneConfidence")}</button>
                <button className="ghost" onClick={async () => {
                  try {
                    await api.deleteLegacyLearning(Number(item.id));
                    setLearning(await api.getLearningAdmin());
                    pushToast("success", t("data.saved.learningUpdated"));
                  } catch (err) {
                    pushToast("error", err instanceof Error ? err.message : t("data.errors.loadTabFailed"));
                  }
                }}>{t("data.learning.delete")}</button>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>{t("data.learning.providerActiveTitle")}</h2>
        <div className="record-list">
          {promotedProviderActive.length === 0 ? <div className="provider-empty"><span>{t("data.learning.empty")}</span></div> : null}
          {promotedProviderActive.map((item) => (
            <div className="record-item" key={`${String(item.pattern_type)}:${String(item.pattern_value)}`}>
              <div className="record-main"><span className="record-title">{String(item.pattern_value)}</span><span className="tag">{String(item.decision)}</span></div>
              <div className="record-meta"><span>{t("data.learning.support", { value: String(item.support) })}</span><span>{t("data.learning.precision", { value: String(item.precision) })}</span></div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>{t("data.learning.providerServiceActiveTitle")}</h2>
        <div className="record-list">
          {promotedProviderServiceActive.length === 0 ? <div className="provider-empty"><span>{t("data.learning.empty")}</span></div> : null}
          {promotedProviderServiceActive.map((item) => (
            <div className="record-item" key={`${String(item.pattern_type)}:${String(item.pattern_value)}`}>
              <div className="record-main"><span className="record-title">{String(item.pattern_value)}</span><span className="tag">{String(item.decision)}</span></div>
              <div className="record-meta"><span>{t("data.learning.support", { value: String(item.support) })}</span><span>{t("data.learning.precision", { value: String(item.precision) })}</span></div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>{t("data.learning.providerLegacyTitle")}</h2>
        <div className="record-list">
          {[...legacyProvider, ...legacyProviderService].length === 0 ? <div className="provider-empty"><span>{t("data.learning.empty")}</span></div> : null}
          {[...legacyProvider, ...legacyProviderService].map((item) => (
            <div className="record-item" key={String(item.id)}>
              <div className="record-main"><span className="record-title">{String(item.pattern_type)}:{String(item.pattern_value)}</span><span className="tag">{String(item.decision)}</span></div>
              <div className="record-meta"><span>{t("data.learning.confidence", { value: String(item.confidence) })}</span></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
