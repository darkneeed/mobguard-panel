import type { Dispatch, SetStateAction } from "react";
import { CalibrationExportPreview, CalibrationReadinessCheck } from "../../api/client";

type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

type Props = {
  t: TranslateFn;
  isPending: (...keys: Array<"calibrationPreview" | "calibrationExport">) => boolean;
  calibrationFilters: Record<string, string | boolean>;
  setCalibrationFilters: Dispatch<SetStateAction<Record<string, string | boolean>>>;
  generateCalibrationExport: () => Promise<void>;
  lastCalibrationManifest: CalibrationExportPreview | null;
  lastCalibrationFilename: string;
  previewError: string;
  displayValue: (value: unknown) => string;
  formatExportWarning: (code: string) => string;
  formatReadinessCheckLabel: (key: string) => string;
  formatReadinessCheckValue: (check: CalibrationReadinessCheck) => string;
};

export function ExportsDataSection({
  t,
  isPending,
  calibrationFilters,
  setCalibrationFilters,
  generateCalibrationExport,
  lastCalibrationManifest,
  lastCalibrationFilename,
  previewError,
  displayValue,
  formatExportWarning,
  formatReadinessCheckLabel,
  formatReadinessCheckValue,
}: Props) {
  const rowCounts = lastCalibrationManifest?.row_counts || {};
  const filters = lastCalibrationManifest?.filters || {};
  const coverage = lastCalibrationManifest?.coverage || {};
  const warnings = lastCalibrationManifest?.warnings || [];
  const readiness = lastCalibrationManifest?.readiness;
  const blockers = readiness?.blockers || [];
  const checks = readiness?.checks || [];
  const datasetReady = Boolean(lastCalibrationManifest?.dataset_ready);
  const tuningReady = Boolean(lastCalibrationManifest?.tuning_ready);

  return (
    <div className="detail-grid">
      <div className="panel">
        <div className="panel-heading panel-heading-row">
          <div>
            <h2>{t("data.exports.title")}</h2>
            <p className="muted">{t("data.exports.description")}</p>
          </div>
          <button onClick={generateCalibrationExport} disabled={isPending("calibrationExport")}>
            {isPending("calibrationExport") ? t("data.exports.generating") : t("data.exports.generate")}
          </button>
        </div>
        <div className="form-grid">
          <div className="rule-field">
            <strong>{t("data.exports.filters.openedFrom")}</strong>
            <input type="date" value={String(calibrationFilters.opened_from)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, opened_from: event.target.value }))} />
          </div>
          <div className="rule-field">
            <strong>{t("data.exports.filters.openedTo")}</strong>
            <input type="date" value={String(calibrationFilters.opened_to)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, opened_to: event.target.value }))} />
          </div>
          <div className="rule-field">
            <strong>{t("data.exports.filters.reviewReason")}</strong>
            <input value={String(calibrationFilters.review_reason)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, review_reason: event.target.value }))} />
          </div>
          <div className="rule-field">
            <strong>{t("data.exports.filters.providerKey")}</strong>
            <input value={String(calibrationFilters.provider_key)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, provider_key: event.target.value }))} />
          </div>
          <div className="rule-field">
            <strong>{t("data.exports.filters.status")}</strong>
            <select value={String(calibrationFilters.status)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, status: event.target.value }))}>
              <option value="resolved_only">{t("data.exports.status.resolvedOnly")}</option>
              <option value="open_only">{t("data.exports.status.openOnly")}</option>
              <option value="all">{t("data.exports.status.all")}</option>
            </select>
          </div>
          <div className="rule-field">
            <strong>{t("data.exports.filters.includeUnknown")}</strong>
            <select value={String(calibrationFilters.include_unknown)} onChange={(event) => setCalibrationFilters((prev) => ({ ...prev, include_unknown: event.target.value === "true" }))}>
              <option value="false">{t("common.no")}</option>
              <option value="true">{t("common.yes")}</option>
            </select>
          </div>
        </div>
      </div>
      <div className="panel">
        <div className="panel-heading">
          <h2>{t("data.exports.readinessTitle")}</h2>
          <p className="muted">{t("data.exports.readinessDescription")}</p>
        </div>
        {isPending("calibrationPreview") && !lastCalibrationManifest ? <p className="muted">{t("common.loading")}</p> : null}
        {previewError ? <div className="error-box">{previewError}</div> : null}
        {!lastCalibrationManifest && !isPending("calibrationPreview") ? <p className="muted">{t("data.exports.noManifest")}</p> : null}
        {lastCalibrationManifest ? (
          <>
            <div className="stats-grid">
              <div className="stat-card"><span>{t("data.exports.cards.overallReadiness")}</span><strong>{readiness?.overall_percent ?? 0}%</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.datasetReadiness")}</span><strong>{readiness?.dataset_percent ?? 0}%</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.tuningReadiness")}</span><strong>{readiness?.tuning_percent ?? 0}%</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.file")}</span><strong>{displayValue(lastCalibrationFilename)}</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.rawRows")}</span><strong>{displayValue((rowCounts as Record<string, unknown>).raw_rows)}</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.knownRows")}</span><strong>{displayValue((rowCounts as Record<string, unknown>).known_rows)}</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.unknownRows")}</span><strong>{displayValue((rowCounts as Record<string, unknown>).unknown_rows)}</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.providerProfiles")}</span><strong>{displayValue((coverage as Record<string, unknown>).provider_profiles_count)}</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.providerCoverage")}</span><strong>{displayValue((coverage as Record<string, unknown>).provider_key_coverage)}</strong></div>
              <div className="stat-card"><span>{t("data.exports.cards.patternCandidates")}</span><strong>{displayValue((coverage as Record<string, unknown>).provider_pattern_candidates)}</strong></div>
            </div>
            <div className={datasetReady ? "ok-box" : "error-box"}>
              {datasetReady ? t("data.exports.datasetReady") : t("data.exports.datasetNotReady")}
            </div>
            <div className={tuningReady ? "ok-box" : "error-box"}>
              {tuningReady ? t("data.exports.tuningReady") : t("data.exports.tuningNotReady")}
            </div>
            {blockers.length > 0 ? (
              <div className="panel export-warning-panel">
                <h3>{t("data.exports.blockersTitle")}</h3>
                <ul className="reason-list">
                  {blockers.map((blocker) => (
                    <li key={blocker}><span>{formatReadinessCheckLabel(blocker)}</span></li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="ok-box">{t("data.exports.noBlockers")}</div>
            )}
            {warnings.length > 0 ? (
              <div className="panel export-warning-panel">
                <h3>{t("data.exports.warningsTitle")}</h3>
                <ul className="reason-list">
                  {warnings.map((warning) => (
                    <li key={warning}><span>{formatExportWarning(warning)}</span></li>
                  ))}
                </ul>
              </div>
            ) : null}
            <div className="panel export-checks-panel">
              <h3>{t("data.exports.checksTitle")}</h3>
              <div className="record-list">
                {checks.map((check) => (
                  <div className="record-item" key={`${check.scope}:${check.key}`}>
                    <div className="record-main">
                      <span className="record-title">{formatReadinessCheckLabel(check.key)}</span>
                      <span className={check.ready ? "tag status-resolved" : "tag severity-high"}>
                        {check.percent}%
                      </span>
                    </div>
                    <div className="record-meta">
                      <span>{check.scope}</span>
                      <span>{formatReadinessCheckValue(check)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <details className="export-section" open>
              <summary>{t("data.exports.filterSnapshot")}</summary>
              <pre className="log-box">{JSON.stringify(filters, null, 2)}</pre>
            </details>
            <details className="export-section">
              <summary>{t("data.exports.coverageSnapshot")}</summary>
              <pre className="log-box">{JSON.stringify(coverage, null, 2)}</pre>
            </details>
          </>
        ) : null}
      </div>
    </div>
  );
}
