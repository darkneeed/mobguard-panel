export type RuleListKey =
  | "admin_tg_ids"
  | "exempt_ids"
  | "exempt_tg_ids"
  | "pure_mobile_asns"
  | "pure_home_asns"
  | "mixed_asns"
  | "allowed_isp_keywords"
  | "home_isp_keywords"
  | "exclude_isp_keywords";

export type RuleSettingKey =
  | "pure_asn_score"
  | "mixed_asn_score"
  | "ptr_home_penalty"
  | "mobile_kw_bonus"
  | "provider_mobile_marker_bonus"
  | "provider_home_marker_penalty"
  | "ip_api_mobile_bonus"
  | "pure_home_asn_penalty"
  | "concurrency_threshold"
  | "churn_window_hours"
  | "churn_mobile_threshold"
  | "lifetime_stationary_hours"
  | "subnet_mobile_ttl_days"
  | "subnet_home_ttl_days"
  | "subnet_mobile_min_evidence"
  | "subnet_home_min_evidence"
  | "score_subnet_mobile_bonus"
  | "score_subnet_home_penalty"
  | "score_churn_high_bonus"
  | "score_churn_medium_bonus"
  | "score_stationary_penalty"
  | "threshold_probable_home"
  | "threshold_probable_mobile"
  | "threshold_home"
  | "threshold_mobile"
  | "shadow_mode"
  | "probable_home_warning_only"
  | "auto_enforce_requires_hard_or_multi_signal"
  | "provider_conflict_review_only"
  | "review_ui_base_url"
  | "learning_promote_asn_min_support"
  | "learning_promote_asn_min_precision"
  | "learning_promote_combo_min_support"
  | "learning_promote_combo_min_precision"
  | "live_rules_refresh_seconds"
  | "db_cleanup_interval_minutes"
  | "module_heartbeats_retention_days"
  | "ingested_raw_events_retention_days"
  | "ip_history_retention_days"
  | "orphan_analysis_events_retention_days"
  | "resolved_review_retention_days";

export type RuleListSectionKey = "access" | "asnLists" | "keywords";
export type RuleSettingSectionKey =
  | "thresholds"
  | "scores"
  | "behavior"
  | "policy"
  | "learning"
  | "retention";

export type RuleSettingValue = string | number | boolean | null | undefined;

export type ProviderProfileDraft = {
  key: string;
  classification: "mixed" | "mobile" | "home";
  aliases: string[];
  mobile_markers: string[];
  home_markers: string[];
  asns: string[];
};

export type RulesDraft = Partial<Record<RuleListKey, Array<string | number>>> & {
  settings?: Partial<Record<RuleSettingKey, RuleSettingValue>>;
  provider_profiles?: ProviderProfileDraft[];
};

export type RuleListFieldMeta = {
  key: RuleListKey;
  sectionKey: RuleListSectionKey;
  itemType: "number" | "string";
};

export type RuleSettingFieldMeta = {
  key: RuleSettingKey;
  sectionKey: RuleSettingSectionKey;
  inputType: "number" | "boolean" | "text";
  step?: number;
};

export const RULE_LIST_FIELDS: RuleListFieldMeta[] = [
  { key: "admin_tg_ids", sectionKey: "access", itemType: "number" },
  { key: "exempt_ids", sectionKey: "access", itemType: "number" },
  { key: "exempt_tg_ids", sectionKey: "access", itemType: "number" },
  { key: "pure_mobile_asns", sectionKey: "asnLists", itemType: "number" },
  { key: "pure_home_asns", sectionKey: "asnLists", itemType: "number" },
  { key: "mixed_asns", sectionKey: "asnLists", itemType: "number" },
  { key: "allowed_isp_keywords", sectionKey: "keywords", itemType: "string" },
  { key: "home_isp_keywords", sectionKey: "keywords", itemType: "string" },
  { key: "exclude_isp_keywords", sectionKey: "keywords", itemType: "string" }
];

export const RULE_SETTING_FIELDS: RuleSettingFieldMeta[] = [
  { key: "threshold_mobile", sectionKey: "thresholds", inputType: "number" },
  { key: "threshold_probable_mobile", sectionKey: "thresholds", inputType: "number" },
  { key: "threshold_home", sectionKey: "thresholds", inputType: "number" },
  { key: "threshold_probable_home", sectionKey: "thresholds", inputType: "number" },
  { key: "pure_asn_score", sectionKey: "scores", inputType: "number" },
  { key: "mixed_asn_score", sectionKey: "scores", inputType: "number" },
  { key: "ptr_home_penalty", sectionKey: "scores", inputType: "number" },
  { key: "mobile_kw_bonus", sectionKey: "scores", inputType: "number" },
  { key: "provider_mobile_marker_bonus", sectionKey: "scores", inputType: "number" },
  { key: "provider_home_marker_penalty", sectionKey: "scores", inputType: "number" },
  { key: "ip_api_mobile_bonus", sectionKey: "scores", inputType: "number" },
  { key: "pure_home_asn_penalty", sectionKey: "scores", inputType: "number" },
  { key: "score_subnet_mobile_bonus", sectionKey: "scores", inputType: "number" },
  { key: "score_subnet_home_penalty", sectionKey: "scores", inputType: "number" },
  { key: "score_churn_high_bonus", sectionKey: "scores", inputType: "number" },
  { key: "score_churn_medium_bonus", sectionKey: "scores", inputType: "number" },
  { key: "score_stationary_penalty", sectionKey: "scores", inputType: "number" },
  { key: "concurrency_threshold", sectionKey: "behavior", inputType: "number" },
  { key: "churn_window_hours", sectionKey: "behavior", inputType: "number" },
  { key: "churn_mobile_threshold", sectionKey: "behavior", inputType: "number" },
  {
    key: "lifetime_stationary_hours",
    sectionKey: "behavior",
    inputType: "number",
    step: 0.5
  },
  { key: "subnet_mobile_ttl_days", sectionKey: "behavior", inputType: "number" },
  { key: "subnet_home_ttl_days", sectionKey: "behavior", inputType: "number" },
  { key: "subnet_mobile_min_evidence", sectionKey: "behavior", inputType: "number" },
  { key: "subnet_home_min_evidence", sectionKey: "behavior", inputType: "number" },
  { key: "shadow_mode", sectionKey: "policy", inputType: "boolean" },
  { key: "probable_home_warning_only", sectionKey: "policy", inputType: "boolean" },
  {
    key: "auto_enforce_requires_hard_or_multi_signal",
    sectionKey: "policy",
    inputType: "boolean"
  },
  { key: "provider_conflict_review_only", sectionKey: "policy", inputType: "boolean" },
  { key: "review_ui_base_url", sectionKey: "policy", inputType: "text" },
  { key: "live_rules_refresh_seconds", sectionKey: "policy", inputType: "number" },
  { key: "learning_promote_asn_min_support", sectionKey: "learning", inputType: "number" },
  {
    key: "learning_promote_asn_min_precision",
    sectionKey: "learning",
    inputType: "number",
    step: 0.01
  },
  { key: "learning_promote_combo_min_support", sectionKey: "learning", inputType: "number" },
  {
    key: "learning_promote_combo_min_precision",
    sectionKey: "learning",
    inputType: "number",
    step: 0.01
  },
  { key: "db_cleanup_interval_minutes", sectionKey: "retention", inputType: "number" },
  { key: "module_heartbeats_retention_days", sectionKey: "retention", inputType: "number" },
  { key: "ingested_raw_events_retention_days", sectionKey: "retention", inputType: "number" },
  { key: "ip_history_retention_days", sectionKey: "retention", inputType: "number" },
  { key: "orphan_analysis_events_retention_days", sectionKey: "retention", inputType: "number" },
  { key: "resolved_review_retention_days", sectionKey: "retention", inputType: "number" }
];
