export type Session = {
  telegram_id: number;
  username?: string;
  first_name?: string;
  expires_at: string;
  payload?: Record<string, unknown>;
};

export type AuthCapabilities = {
  telegram_enabled: boolean;
  bot_username: string;
  local_enabled: boolean;
  local_username_hint: string;
  review_ui_base_url: string;
  panel_name: string;
};

export type EnvFieldState = {
  key: string;
  value: string;
  present: boolean;
  masked: boolean;
  restart_required: boolean;
};

export type ReviewItem = {
  id: number;
  status: string;
  review_reason: string;
  module_id: string | null;
  module_name: string | null;
  uuid: string | null;
  username: string | null;
  system_id: number | null;
  telegram_id: string | null;
  ip: string;
  tag: string | null;
  verdict: string;
  confidence_band: string;
  score: number;
  isp: string | null;
  asn: number | null;
  punitive_eligible: number;
  severity: "critical" | "high" | "medium" | "low";
  repeat_count: number;
  reason_codes: string[];
  opened_at: string;
  updated_at: string;
  review_url: string;
};

export type ReviewListResponse = {
  items: ReviewItem[];
  count: number;
  page: number;
  page_size: number;
};

export type ModuleRecord = {
  module_id: string;
  module_name: string;
  status: string;
  version: string;
  protocol_version: string;
  config_revision_applied: number;
  install_state: string;
  managed: boolean;
  inbound_tags: string[];
  health_status: "ok" | "warn" | "error";
  error_text: string;
  last_validation_at: string;
  spool_depth: number;
  access_log_exists: boolean;
  token_reveal_available?: boolean;
  first_seen_at?: string;
  last_seen_at: string;
  healthy?: boolean;
  open_review_cases?: number;
  analysis_events_count?: number;
};

export type ModuleListResponse = {
  items: ModuleRecord[];
  count: number;
};

export type ModuleInstallBundle = {
  compose_yaml: string;
  module_token?: string;
};

export type ModuleDetailResponse = {
  module: ModuleRecord;
  install: ModuleInstallBundle;
};

export type ModuleProvisioningPayload = {
  module_name: string;
  inbound_tags: string[];
};

export type RulesState = {
  rules: Record<string, unknown>;
  revision: number;
  updated_at: string;
  updated_by: string;
};

export type ReviewListParams = Record<string, string | number | boolean | undefined>;

export type SettingsSectionUpdatePayload = {
  settings?: Record<string, unknown>;
  lists?: Record<string, unknown[]>;
  env?: Record<string, string>;
  revision?: number;
  updated_at?: string;
};

export type CalibrationReadinessCheck = {
  key: string;
  scope: "dataset" | "tuning";
  current: number;
  target: number;
  ratio: number;
  percent: number;
  ready: boolean;
};

export type CalibrationReadiness = {
  overall_percent: number;
  dataset_percent: number;
  tuning_percent: number;
  blockers: string[];
  checks: CalibrationReadinessCheck[];
};

export type CalibrationExportPreview = {
  schema_version: number;
  generated_at: string;
  snapshot_source: string;
  dataset_ready: boolean;
  tuning_ready: boolean;
  warnings: string[];
  readiness: CalibrationReadiness;
  filters: Record<string, unknown>;
  row_counts: Record<string, unknown>;
  coverage: Record<string, unknown>;
};

export type HealthCoreSnapshot = {
  service_name?: string;
  healthy: boolean;
  status: string;
  mode: "embedded" | "heartbeat";
  updated_at?: string;
  age_seconds?: number;
  details?: Record<string, unknown>;
};

export type HealthSnapshot = {
  status: string;
  admin_sessions: number;
  ipinfo_token_present: boolean;
  db: {
    healthy: boolean;
    path: string;
  };
  core: HealthCoreSnapshot;
  live_rules: {
    revision: number;
    updated_at: string;
    updated_by: string;
  };
  analysis_24h: {
    total: number;
    score_zero_count: number;
    score_zero_ratio: number;
    asn_missing_count: number;
    asn_missing_ratio: number;
  };
};
