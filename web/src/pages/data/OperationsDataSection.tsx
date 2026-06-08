import type { Dispatch, SetStateAction } from "react";
import { api, CacheAdminResponse, OverridesResponse, ViolationsResponse } from "../../api/client";
import { Loader2 } from "lucide-react";
import type { Language } from "../../localization/types";
import { useVisibleItems } from "../../shared/useVisibleItems";
import { formatDisplayDateTime } from "../../utils/datetime";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;
type Mode = "violations" | "overrides" | "cache";
type PendingKey = "exactOverride" | "unsureOverride" | "cacheSave";

type Props = {
  mode: Mode;
  t: TranslateFn;
  language: Language;
  violations: ViolationsResponse | null;
  overrides: OverridesResponse | null;
  cache: CacheAdminResponse | null;
  exactOverrideIp: string;
  setExactOverrideIp: (value: string) => void;
  exactOverrideDecision: string;
  setExactOverrideDecision: (value: string) => void;
  unsureOverrideIp: string;
  setUnsureOverrideIp: (value: string) => void;
  unsureOverrideDecision: string;
  setUnsureOverrideDecision: (value: string) => void;
  selectedCacheIp: string;
  setSelectedCacheIp: (value: string) => void;
  cacheDraft: Record<string, string>;
  setCacheDraft: Dispatch<SetStateAction<Record<string, string>>>;
  canWriteData?: boolean;
  saveExactOverride: () => Promise<void>;
  saveUnsureOverride: () => Promise<void>;
  saveCachePatch: () => Promise<void>;
  setOverrides: (value: OverridesResponse) => void;
  setCache: (value: CacheAdminResponse) => void;
  pushToast: (kind: "success" | "error" | "warning" | "info", message: string) => void;
  withPending: <T>(key: PendingKey, action: () => Promise<T>) => Promise<T>;
  isPending: (...keys: PendingKey[]) => boolean;
  displayValue: (value: unknown) => string;
  formatDecisionLabel: (value: unknown) => string;
};

export function OperationsDataSection({
  mode,
  t,
  language,
  violations,
  overrides,
  cache,
  exactOverrideIp,
  setExactOverrideIp,
  exactOverrideDecision,
  setExactOverrideDecision,
  unsureOverrideIp,
  setUnsureOverrideIp,
  unsureOverrideDecision,
  setUnsureOverrideDecision,
  selectedCacheIp,
  setSelectedCacheIp,
  cacheDraft,
  setCacheDraft,
  canWriteData = true,
  saveExactOverride,
  saveUnsureOverride,
  saveCachePatch,
  setOverrides,
  setCache,
  pushToast,
  withPending,
  isPending,
  displayValue,
  formatDecisionLabel,
}: Props) {
  const active = (violations?.active as Array<Record<string, unknown>> | undefined) || [];
  const history = (violations?.history as Array<Record<string, unknown>> | undefined) || [];
  const limiterWindows = (violations?.limiter?.windows as Array<Record<string, unknown>> | undefined) || [];
  const limiterCooldowns = (violations?.limiter?.cooldowns as Array<Record<string, unknown>> | undefined) || [];
  const limiterIgnores = (violations?.limiter?.ignores as Array<Record<string, unknown>> | undefined) || [];
  const webhookDeliveries = (violations?.webhooks as Array<Record<string, unknown>> | undefined) || [];
  const exactIp = (overrides?.exact_ip as Array<Record<string, unknown>> | undefined) || [];
  const unsure = (overrides?.unsure_patterns as Array<Record<string, unknown>> | undefined) || [];
  const items = (cache?.items as Array<Record<string, unknown>> | undefined) || [];
  const {
    visibleItems: visibleActive,
    hasMore: hasMoreActive,
    loadMoreRef: loadMoreActiveRef,
  } = useVisibleItems(active, { initialCount: 20, step: 20 });
  const {
    visibleItems: visibleHistory,
    hasMore: hasMoreHistory,
    loadMoreRef: loadMoreHistoryRef,
  } = useVisibleItems(history, { initialCount: 20, step: 20 });
  const {
    visibleItems: visibleLimiterWindows,
    hasMore: hasMoreLimiterWindows,
    loadMoreRef: loadMoreLimiterWindowsRef,
  } = useVisibleItems(limiterWindows, { initialCount: 20, step: 20 });
  const {
    visibleItems: visibleLimiterCooldowns,
    hasMore: hasMoreLimiterCooldowns,
    loadMoreRef: loadMoreLimiterCooldownsRef,
  } = useVisibleItems(limiterCooldowns, { initialCount: 20, step: 20 });
  const {
    visibleItems: visibleLimiterIgnores,
    hasMore: hasMoreLimiterIgnores,
    loadMoreRef: loadMoreLimiterIgnoresRef,
  } = useVisibleItems(limiterIgnores, { initialCount: 20, step: 20 });
  const {
    visibleItems: visibleWebhookDeliveries,
    hasMore: hasMoreWebhookDeliveries,
    loadMoreRef: loadMoreWebhookDeliveriesRef,
  } = useVisibleItems(webhookDeliveries, { initialCount: 20, step: 20 });
  const {
    visibleItems: visibleExactIp,
    hasMore: hasMoreExactIp,
    loadMoreRef: loadMoreExactIpRef,
  } = useVisibleItems(exactIp, { initialCount: 20, step: 20 });
  const {
    visibleItems: visibleUnsure,
    hasMore: hasMoreUnsure,
    loadMoreRef: loadMoreUnsureRef,
  } = useVisibleItems(unsure, { initialCount: 20, step: 20 });
  const {
    visibleItems: visibleCacheItems,
    hasMore: hasMoreCacheItems,
    loadMoreRef: loadMoreCacheRef,
  } = useVisibleItems(items, { initialCount: 20, step: 20 });

  if (mode === "violations") {
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>{t("data.violations.activeTitle")}</h2>
          <div className="record-list">
            {visibleActive.map((item) => (
              <div className="record-item" key={String(item.uuid)}>
                <div className="record-main">
                  <span className="record-title">{String(item.uuid)}</span>
                  <span className="tag">{String(item.restriction_mode || t("common.notAvailable"))}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.violations.strikes", { value: String(item.strikes) })}</span>
                  <span>{t("data.violations.warningCount", { value: String(item.warning_count) })}</span>
                  <span>{t("data.violations.unban", { value: formatDisplayDateTime(String(item.unban_time ?? ""), t("common.notAvailable"), language) })}</span>
                </div>
              </div>
            ))}
            {hasMoreActive ? (
              <div className="provider-empty muted" ref={loadMoreActiveRef}>
                <span>{t("common.loading")}</span>
              </div>
            ) : null}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.violations.historyTitle")}</h2>
          <div className="record-list">
            {visibleHistory.map((item) => (
              <div className="record-item" key={String(item.id)}>
                <div className="record-main">
                  <span className="record-title">{String(item.uuid)}</span>
                  <span>{String(item.ip)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.violations.historyRow", { strike: String(item.strike_number), duration: String(item.punishment_duration) })}</span>
                  <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
                </div>
              </div>
            ))}
            {hasMoreHistory ? (
              <div className="provider-empty muted" ref={loadMoreHistoryRef}>
                <span>{t("common.loading")}</span>
              </div>
            ) : null}
          </div>
        </div>
        <div className="panel">
          <h2>Limiter windows</h2>
          <div className="record-list">
            {visibleLimiterWindows.map((item) => (
              <div className="record-item" key={String(item.scope_key)}>
                <div className="record-main">
                  <span className="record-title">{String(item.scope_key)}</span>
                  <span>{String(item.event_count)}</span>
                </div>
                <div className="record-meta">
                  <span>{formatDisplayDateTime(String(item.window_started_at ?? ""), t("common.notAvailable"), language)}</span>
                  <span>{formatDisplayDateTime(String(item.last_event_at ?? ""), t("common.notAvailable"), language)}</span>
                </div>
              </div>
            ))}
            {hasMoreLimiterWindows ? (
              <div className="provider-empty muted" ref={loadMoreLimiterWindowsRef}>
                <span>{t("common.loading")}</span>
              </div>
            ) : null}
          </div>
        </div>
        <div className="panel">
          <h2>Limiter cooldown/ignore</h2>
          <div className="record-list">
            {visibleLimiterCooldowns.map((item) => (
              <div className="record-item" key={`${String(item.scope_key)}:${String(item.action)}`}>
                <div className="record-main">
                  <span className="record-title">{String(item.scope_key)}</span>
                  <span>{String(item.action)}</span>
                </div>
                <div className="record-meta">
                  <span>{formatDisplayDateTime(String(item.cooldown_until ?? ""), t("common.notAvailable"), language)}</span>
                </div>
              </div>
            ))}
            {visibleLimiterIgnores.map((item) => (
              <div className="record-item" key={String(item.scope_key)}>
                <div className="record-main">
                  <span className="record-title">{String(item.scope_key)}</span>
                  <span className="tag">{String(item.reason || "ignore")}</span>
                </div>
                <div className="record-meta">
                  <span>{formatDisplayDateTime(String(item.expires_at ?? ""), t("common.notAvailable"), language)}</span>
                </div>
              </div>
            ))}
            {hasMoreLimiterCooldowns || hasMoreLimiterIgnores ? (
              <div className="provider-empty muted" ref={hasMoreLimiterCooldowns ? loadMoreLimiterCooldownsRef : loadMoreLimiterIgnoresRef}>
                <span>{t("common.loading")}</span>
              </div>
            ) : null}
          </div>
        </div>
        <div className="panel">
          <h2>Webhook deliveries</h2>
          <div className="record-list">
            {visibleWebhookDeliveries.map((item) => (
              <div className="record-item" key={String(item.id)}>
                <div className="record-main">
                  <span className="record-title">{String(item.event_type)}</span>
                  <span className="tag">{String(item.status)}</span>
                </div>
                <div className="record-meta">
                  <span>{String(item.target_url)}</span>
                  <span>{String(item.attempt_count)}</span>
                  <span>{formatDisplayDateTime(String(item.created_at ?? ""), t("common.notAvailable"), language)}</span>
                </div>
              </div>
            ))}
            {hasMoreWebhookDeliveries ? (
              <div className="provider-empty muted" ref={loadMoreWebhookDeliveriesRef}>
                <span>{t("common.loading")}</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  if (mode === "overrides") {
    return (
      <div className="detail-grid">
        <div className="panel">
          <h2>{t("data.overrides.exactTitle")}</h2>
          <div className="action-row">
            <input placeholder={t("data.overrides.ipPlaceholder")} value={exactOverrideIp} onChange={(event) => setExactOverrideIp(event.target.value)} />
            <select value={exactOverrideDecision} onChange={(event) => setExactOverrideDecision(event.target.value)}>
              <option value="HOME">{t("data.decisions.home")}</option>
              <option value="MOBILE">{t("data.decisions.mobile")}</option>
              <option value="SKIP">{t("data.decisions.skip")}</option>
            </select>
            <button
              disabled={!canWriteData || isPending("exactOverride")}
              onClick={saveExactOverride}
              style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
            >
              {isPending("exactOverride") && <Loader2 size={16} className="spinner" />}
              {t("data.overrides.save")}
            </button>
          </div>
          <div className="record-list">
            {visibleExactIp.map((item) => (
              <div className="record-item" key={String(item.ip)}>
                <div className="record-main">
                  <span className="record-title">{String(item.ip)}</span>
                  <span className="tag">{formatDecisionLabel(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{t("data.overrides.expires", { value: formatDisplayDateTime(String(item.expires_at ?? ""), t("common.notAvailable"), language) })}</span>
                </div>
                <div className="record-actions">
                  <button className="ghost" disabled={!canWriteData || isPending("exactOverride")} onClick={async () => {
                    try {
                      await withPending("exactOverride", () => api.deleteExactOverride(String(item.ip)));
                      setOverrides(await api.getOverrides());
                      pushToast("success", t("data.saved.exactOverride"));
                    } catch (err) {
                      pushToast("error", err instanceof Error ? err.message : t("data.errors.saveExactOverrideFailed"));
                    }
                  }}>{t("data.overrides.delete")}</button>
                </div>
              </div>
            ))}
            {hasMoreExactIp ? (
              <div className="provider-empty muted" ref={loadMoreExactIpRef}>
                <span>{t("common.loading")}</span>
              </div>
            ) : null}
          </div>
        </div>
        <div className="panel">
          <h2>{t("data.overrides.unsureTitle")}</h2>
          <div className="action-row">
            <input placeholder={t("data.overrides.ipPatternPlaceholder")} value={unsureOverrideIp} onChange={(event) => setUnsureOverrideIp(event.target.value)} />
            <select value={unsureOverrideDecision} onChange={(event) => setUnsureOverrideDecision(event.target.value)}>
              <option value="HOME">{t("data.decisions.home")}</option>
              <option value="MOBILE">{t("data.decisions.mobile")}</option>
              <option value="SKIP">{t("data.decisions.skip")}</option>
            </select>
            <button
              disabled={!canWriteData || isPending("unsureOverride")}
              onClick={saveUnsureOverride}
              style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
            >
              {isPending("unsureOverride") && <Loader2 size={16} className="spinner" />}
              {t("data.overrides.save")}
            </button>
          </div>
          <div className="record-list">
            {visibleUnsure.map((item) => (
              <div className="record-item" key={String(item.ip_pattern)}>
                <div className="record-main">
                  <span className="record-title">{String(item.ip_pattern)}</span>
                  <span className="tag">{formatDecisionLabel(item.decision)}</span>
                </div>
                <div className="record-meta">
                  <span>{formatDisplayDateTime(String(item.timestamp ?? ""), t("common.notAvailable"), language)}</span>
                </div>
                <div className="record-actions">
                  <button className="ghost" disabled={!canWriteData || isPending("unsureOverride")} onClick={async () => {
                    try {
                      await withPending("unsureOverride", () => api.deleteUnsureOverride(String(item.ip_pattern)));
                      setOverrides(await api.getOverrides());
                      pushToast("success", t("data.saved.unsureOverride"));
                    } catch (err) {
                      pushToast("error", err instanceof Error ? err.message : t("data.errors.saveUnsureOverrideFailed"));
                    }
                  }}>{t("data.overrides.delete")}</button>
                </div>
              </div>
            ))}
            {hasMoreUnsure ? (
              <div className="provider-empty muted" ref={loadMoreUnsureRef}>
                <span>{t("common.loading")}</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="detail-grid">
      <div className="panel">
        <h2>{t("data.cache.title")}</h2>
        <div className="record-list">
          {visibleCacheItems.map((item) => (
            <div className="record-item" key={String(item.ip)}>
              <div className="record-main">
                <span className="record-title">{String(item.ip)}</span>
                <span className="tag">{String(item.status)} / {String(item.confidence)}</span>
              </div>
              <div className="record-meta">
                <span>{t("data.cache.asnValue", { value: displayValue(item.asn) })}</span>
                <span>{String(item.details || t("common.notAvailable"))}</span>
              </div>
              <div className="record-actions">
                <button className="ghost" disabled={!canWriteData} onClick={() => {
                  setSelectedCacheIp(String(item.ip));
                  setCacheDraft({
                    status: String(item.status || ""),
                    confidence: String(item.confidence || ""),
                    details: String(item.details || ""),
                    asn: String(item.asn || "")
                  });
                }}>{t("data.cache.edit")}</button>
                <button className="ghost" disabled={!canWriteData} onClick={async () => {
                  try {
                    await api.deleteCache(String(item.ip));
                    setCache(await api.getCache());
                    pushToast("success", t("data.saved.cacheUpdated"));
                  } catch (err) {
                    pushToast("error", err instanceof Error ? err.message : t("data.errors.saveCacheFailed"));
                  }
                }}>{t("data.cache.delete")}</button>
              </div>
            </div>
          ))}
          {hasMoreCacheItems ? (
            <div className="provider-empty muted" ref={loadMoreCacheRef}>
              <span>{t("common.loading")}</span>
            </div>
          ) : null}
        </div>
      </div>
      <div className="panel">
        <div className="panel-heading">
          <h2>{t("data.cache.editTitle")}</h2>
          <p className="muted">{t("data.sectionDescriptions.cache")}</p>
        </div>
        <div className="form-grid compact-form-grid">
          <div className="rule-field compact-rule-field">
            <strong>{t("data.cache.selectedIp")}</strong>
            <input placeholder={t("data.cache.selectedIp")} value={selectedCacheIp} onChange={(event) => setSelectedCacheIp(event.target.value)} />
          </div>
          <div className="rule-field compact-rule-field">
            <strong>{t("data.cache.status")}</strong>
            <input placeholder={t("data.cache.status")} value={cacheDraft.status || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, status: event.target.value }))} />
          </div>
          <div className="rule-field compact-rule-field">
            <strong>{t("data.cache.confidence")}</strong>
            <input placeholder={t("data.cache.confidence")} value={cacheDraft.confidence || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, confidence: event.target.value }))} />
          </div>
          <div className="rule-field rule-field-wide compact-rule-field">
            <strong>{t("data.cache.details")}</strong>
            <textarea className="note-box compact-note-box" placeholder={t("data.cache.details")} value={cacheDraft.details || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, details: event.target.value }))} />
          </div>
          <div className="rule-field compact-rule-field">
            <strong>{t("data.cache.asn")}</strong>
            <input placeholder={t("data.cache.asn")} value={cacheDraft.asn || ""} onChange={(event) => setCacheDraft((prev) => ({ ...prev, asn: event.target.value }))} />
          </div>
        </div>
        <button
          onClick={saveCachePatch}
          disabled={!canWriteData || !selectedCacheIp || isPending("cacheSave")}
          style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
        >
          {isPending("cacheSave") && <Loader2 size={16} className="spinner" />}
          {t("data.cache.save")}
        </button>
      </div>
    </div>
  );
}
