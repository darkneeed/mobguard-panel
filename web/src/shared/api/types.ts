export type Session = {
  telegram_id: number;
  username?: string;
  first_name?: string;
  expires_at: string;
  subject?: string;
  auth_method?: string;
  role?: string;
  permissions?: string[];
  totp_enabled?: boolean;
  totp_verified?: boolean;
  totp_verified_at?: string;
  payload?: Record<string, unknown>;
};

export type AuthResult = Session & {
  requires_totp?: boolean;
  totp_setup_required?: boolean;
  challenge_token?: string;
};

export type TotpSetupPayload = {
  challenge_token: string;
  secret: string;
  provisioning_uri: string;
  account_name: string;
  issuer: string;
};

export type AuthCapabilities = {
  telegram_enabled: boolean;
  bot_username: string;
  local_enabled: boolean;
  local_username_hint: string;
  review_ui_base_url: string;
  panel_name: string;
  panel_logo_url: string;
};

export type BrandingConfig = {
  panel_name: string;
  panel_logo_url: string;
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
  subject_key?: string;
  case_scope_key?: string;
  device_scope_key?: string;
  scope_type?: "ip_device" | "ip_only";
  module_id: string | null;
  module_name: string | null;
  client_device_id?: string | null;
  client_device_label?: string | null;
  client_os_family?: string | null;
  client_app_name?: string | null;
  uuid: string | null;
  username: string | null;
  system_id: number | null;
  telegram_id: string | null;
  ip: string;
  tag: string | null;
  inbound_tag?: string | null;
  target_ip?: string | null;
  target_scope_type?: "ip_device" | "ip_only";
  device_display?: string | null;
  verdict: string;
  confidence_band: string;
  score: number;
  isp: string | null;
  asn: number | null;
  punitive_eligible: number;
  severity: "critical" | "high" | "medium" | "low";
  repeat_count: number;
  reason_codes: string[];
  ip_inventory?: ReviewIpInventoryItem[];
  same_device_ip_history?: ReviewSameDeviceIpItem[];
  distinct_ip_count?: number;
  module_inventory?: ReviewModuleInventoryItem[];
  module_count?: number;
  provider_key?: string | null;
  provider_classification?: string;
  provider_service_hint?: string;
  provider_conflict?: boolean;
  provider_review_recommended?: boolean;
  usage_profile_summary?: string;
  usage_profile_signal_count?: number;
  usage_profile_priority?: number;
  usage_profile_soft_reasons?: string[];
  usage_profile_ongoing_duration_seconds?: number | null;
  usage_profile_ongoing_duration_text?: string;
  last_repeat_at?: string | null;
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

export type ReviewIpInventoryItem = {
  ip: string;
  hit_count: number;
  first_seen_at: string;
  last_seen_at: string;
  isp?: string | null;
  asn?: number | null;
};

export type ReviewSameDeviceIpItem = {
  ip: string;
  hit_count: number;
  first_seen_at: string;
  last_seen_at: string;
  isp?: string | null;
  asn?: number | null;
  country?: string | null;
  region?: string | null;
  city?: string | null;
  module_id?: string | null;
  module_name?: string | null;
  inbound_tag?: string | null;
};

export type ReviewModuleInventoryItem = {
  module_id?: string | null;
  module_name?: string | null;
  first_seen_at: string;
  last_seen_at: string;
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

export type DetectionSettingsResponse = {
  rules: Record<string, unknown>;
  revision: number;
  updated_at: string;
  updated_by: string;
};

export type RulesState = {
  rules: Record<string, unknown>;
  revision: number;
  updated_at: string;
  updated_by: string;
};

export type ReviewListParams = Record<string, string | number | boolean | undefined>;

export type SettingsScalar = string | number | boolean | string[];

export type EnforcementSettingsResponse = {
  settings: Record<string, SettingsScalar>;
};

export type SettingsSectionUpdatePayload = {
  settings?: Record<string, unknown>;
  lists?: Record<string, unknown[]>;
  env?: Record<string, string>;
  revision?: number;
  updated_at?: string;
};

export type UserIdentity = {
  uuid?: string | null;
  username?: string | null;
  system_id?: number | null;
  telegram_id?: string | null;
};

export type UserSearchItem = UserIdentity & {
  updated_at?: string | null;
};

export type UserSearchResponse = {
  items: UserSearchItem[];
  panel_match: Record<string, unknown> | null;
};

export type UserCardFlags = {
  exempt_system_id?: boolean;
  exempt_telegram_id?: boolean;
  active_ban?: boolean;
  active_warning?: boolean;
};

export type UsageProfile = {
  available?: boolean;
  event_count?: number;
  ip_count?: number;
  provider_count?: number;
  device_count?: number;
  device_labels?: string[];
  devices?: Array<Record<string, unknown>>;
  os_families?: string[];
  node_count?: number;
  nodes?: string[];
  geo_summary?: {
    country_count?: number;
    countries?: string[];
    recent_locations?: Array<Record<string, unknown>>;
    last_location?: Record<string, unknown> | null;
  };
  travel_flags?: {
    geo_country_jump?: boolean;
    geo_impossible_travel?: boolean;
    country_jumps?: Array<Record<string, unknown>>;
    impossible_travel?: Array<Record<string, unknown>>;
  };
  top_ips?: Array<Record<string, unknown>>;
  top_providers?: Array<Record<string, unknown>>;
  traffic_burst?: Record<string, unknown> | null;
  soft_reasons?: string[];
  signal_counts?: Record<string, unknown>;
  ongoing_duration_seconds?: number | null;
  ongoing_duration_text?: string;
  last_seen?: string | null;
  updated_at?: string | null;
  usage_profile_summary?: string;
  summary_score?: number;
  summary_reason_set?: string[];
};

export type UserCardResponse = {
  identity?: UserIdentity;
  panel_user?: Record<string, unknown> | null;
  violation?: Record<string, unknown> | null;
  history?: Array<Record<string, unknown>>;
  active_trackers?: Array<Record<string, unknown>>;
  ip_history?: Array<Record<string, unknown>>;
  review_cases?: Array<Record<string, unknown>>;
  analysis_events?: Array<Record<string, unknown>>;
  usage_profile?: UsageProfile;
  flags?: UserCardFlags;
  remote_updated?: boolean;
  remote_changed?: boolean;
  remote_error?: string;
  traffic_cap?: Record<string, unknown>;
};

export type UserCardExportResponse = UserCardResponse & {
  export_meta?: {
    generated_at?: string;
    identifier?: string;
    lookup_fields?: Record<string, unknown>;
    record_counts?: Record<string, unknown>;
  };
};

export type ReviewResolution = {
  id: number;
  resolution: string;
  actor: string;
  actor_tg_id?: number | null;
  note?: string | null;
  created_at: string;
};

export type ReviewDetailResponse = Partial<ReviewItem> & {
  latest_event?: Record<string, unknown>;
  resolutions?: ReviewResolution[];
  related_cases?: Array<Record<string, unknown>>;
  usage_profile?: UsageProfile;
};

export type AnalysisEventItem = {
  id: number;
  created_at: string;
  ip: string;
  tag?: string | null;
  inbound_tag?: string | null;
  target_ip?: string | null;
  target_scope_type?: "ip_device" | "ip_only";
  case_scope_key?: string | null;
  device_scope_key?: string | null;
  verdict: string;
  confidence_band: string;
  score: number;
  isp?: string | null;
  asn?: number | null;
  module_id?: string | null;
  module_name?: string | null;
  client_device_id?: string | null;
  client_device_label?: string | null;
  client_os_family?: string | null;
  client_app_name?: string | null;
  device_display?: string | null;
  country?: string | null;
  region?: string | null;
  city?: string | null;
  provider_evidence?: Record<string, unknown>;
  reasons?: Array<Record<string, unknown>>;
  signal_flags?: Record<string, unknown>;
  bundle?: Record<string, unknown> | null;
  has_review_case?: boolean;
  review_case_id?: number | null;
  review_case_status?: string | null;
  review_url?: string;
};

export type AnalysisEventListResponse = {
  items: AnalysisEventItem[];
  count: number;
  page: number;
  page_size: number;
};

export type OverviewMetricsResponse = {
  health: HealthSnapshot;
  quality: Record<string, unknown>;
  latest_cases: ReviewListResponse;
};

export type ViolationsResponse = {
  active: Array<Record<string, unknown>>;
  history: Array<Record<string, unknown>>;
};

export type OverridesResponse = {
  exact_ip: Array<Record<string, unknown>>;
  unsure_patterns: Array<Record<string, unknown>>;
};

export type CacheAdminResponse = {
  items: Array<Record<string, unknown>>;
};

export type AuditEvent = {
  id: number;
  actor_subject: string;
  actor_role: string;
  actor_auth_method: string;
  actor_telegram_id?: number | null;
  actor_username?: string | null;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
  created_at: string;
};

export type AuditTrailResponse = {
  items: AuditEvent[];
};

export type LearningAdminResponse = {
  promoted_active: Array<Record<string, unknown>>;
  promoted_stats: Array<Record<string, unknown>>;
  legacy: Array<Record<string, unknown>>;
  promoted_provider_active: Array<Record<string, unknown>>;
  promoted_provider_service_active: Array<Record<string, unknown>>;
  promoted_provider_stats: Array<Record<string, unknown>>;
  promoted_provider_service_stats: Array<Record<string, unknown>>;
  legacy_provider: Array<Record<string, unknown>>;
  legacy_provider_service: Array<Record<string, unknown>>;
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
