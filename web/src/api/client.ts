import { authApi } from "../features/auth/api/client";
import { dataApi } from "../features/data/api/client";
import { reviewsApi } from "../features/reviews/api/client";
import { settingsApi } from "../features/settings/api/client";

export type {
  AuditEvent,
  AnalysisEventItem,
  AnalysisEventListResponse,
  AuditTrailResponse,
  AuthResult,
  AuthCapabilities,
  BrandingConfig,
  CacheAdminResponse,
  CalibrationExportPreview,
  CalibrationReadiness,
  CalibrationReadinessCheck,
  DetectionSettingsResponse,
  EnvFieldState,
  EnforcementSettingsResponse,
  HealthCoreSnapshot,
  HealthSnapshot,
  LearningAdminResponse,
  ModuleDetailResponse,
  ModuleInstallBundle,
  ModuleListResponse,
  ModuleProvisioningPayload,
  ModuleRecord,
  OverviewMetricsResponse,
  OverridesResponse,
  PipelineStatus,
  ReviewDetailResponse,
  ReviewIpInventoryItem,
  ReviewItem,
  ReviewListParams,
  ReviewListResponse,
  ReviewModuleInventoryItem,
  ReviewSameDeviceIpItem,
  ReviewResolution,
  RulesState,
  Session,
  SnapshotFreshness,
  SettingsSectionUpdatePayload,
  TotpSetupPayload,
  UserCardExportResponse,
  UserCardResponse,
  UserSearchResponse,
  UsageProfile,
  ViolationsResponse
} from "../shared/api/types";

export const api = {
  ...authApi,
  ...reviewsApi,
  ...settingsApi,
  ...dataApi
};
