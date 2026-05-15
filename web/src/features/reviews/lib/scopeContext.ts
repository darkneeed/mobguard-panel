type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

export type ReviewScopeType = "ip_device" | "subject_ip" | "ip_only";

export type ScopeContextPresentation = {
  scopeType: ReviewScopeType;
  decisionTarget: string;
  queueScopeLabel: string;
  contextLabel: string;
  contextValue: string;
  detailContextValue: string;
  historyTitle: string;
  historyLabel: string;
  scopeMeta: string;
  sharedAccessWarning: string;
};

export function normalizeReviewScopeType(value: string | null | undefined): ReviewScopeType {
  if (value === "ip_device" || value === "subject_ip") {
    return value;
  }
  return "ip_only";
}

export function describeScopeContext(
  t: TranslateFn,
  scopeTypeRaw: string | null | undefined,
  sharedAccountSuspected = false,
  historyCount?: number
): ScopeContextPresentation {
  const scopeType = normalizeReviewScopeType(scopeTypeRaw);
  const historyParams = typeof historyCount === "number" ? { count: historyCount } : undefined;

  if (scopeType === "ip_device") {
    return {
      scopeType,
      decisionTarget: t("common.scopeLabels.ipDeviceScope"),
      queueScopeLabel: t("common.scopeLabels.queueScopeDevice"),
      contextLabel: t("common.scopeLabels.deviceField"),
      contextValue: t("common.notAvailable"),
      detailContextValue: t("common.notAvailable"),
      historyTitle: t("common.scopeLabels.ipDeviceHistoryTitle"),
      historyLabel: t("common.scopeLabels.ipDeviceHistory", historyParams),
      scopeMeta: t("common.scopeLabels.ipDeviceScope"),
      sharedAccessWarning: ""
    };
  }

  if (scopeType === "subject_ip") {
    return {
      scopeType,
      decisionTarget: t("common.scopeLabels.subjectIpScope"),
      queueScopeLabel: t("common.scopeLabels.queueScopeAccount"),
      contextLabel: t("common.scopeLabels.accountField"),
      contextValue: sharedAccountSuspected
        ? t("common.scopeLabels.sharedAccountContext")
        : t("common.scopeLabels.subjectContext"),
      detailContextValue: t("common.scopeLabels.subjectContextValue"),
      historyTitle: t("common.scopeLabels.subjectIpHistoryTitle"),
      historyLabel: t("common.scopeLabels.subjectIpHistory", historyParams),
      scopeMeta: sharedAccountSuspected
        ? t("common.scopeLabels.sharedAccountContext")
        : t("common.scopeLabels.subjectContext"),
      sharedAccessWarning: sharedAccountSuspected ? t("common.scopeLabels.sharedAccountWarning") : ""
    };
  }

  return {
    scopeType,
    decisionTarget: t("common.scopeLabels.ipOnlyScope"),
    queueScopeLabel: t("common.scopeLabels.queueScopeIpOnly"),
    contextLabel: t("common.scopeLabels.contextField"),
    contextValue: t("common.scopeLabels.ipOnlyContext"),
    detailContextValue: t("common.scopeLabels.ipOnlyContext"),
    historyTitle: t("common.scopeLabels.ipOnlyHistoryTitle"),
    historyLabel: t("common.scopeLabels.ipOnlyHistory", historyParams),
    scopeMeta: t("common.scopeLabels.ipOnlyScope"),
    sharedAccessWarning: ""
  };
}
