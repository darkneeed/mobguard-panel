import { authApi } from "../features/auth/api/client";
import { dataApi } from "../features/data/api/client";
import { reviewsApi } from "../features/reviews/api/client";
import { settingsApi } from "../features/settings/api/client";

export type {
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
  OverridesResponse,
  ReviewDetailResponse,
  ReviewItem,
  ReviewListParams,
  ReviewListResponse,
  ReviewResolution,
  RulesState,
  Session,
  SettingsSectionUpdatePayload,
  UserCardExportResponse,
  UserCardResponse,
  UserSearchResponse,
  ViolationsResponse
} from "../shared/api/types";

export const api = {
  ...authApi,
  ...reviewsApi,
  ...settingsApi,
  ...dataApi
};
