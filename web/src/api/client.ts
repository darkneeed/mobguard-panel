import { authApi } from "../features/auth/api/client";
import { dataApi } from "../features/data/api/client";
import { reviewsApi } from "../features/reviews/api/client";
import { settingsApi } from "../features/settings/api/client";

export type {
  AuthCapabilities,
  EnvFieldState,
  ModuleDetailResponse,
  ModuleInstallBundle,
  ModuleListResponse,
  ModuleProvisioningPayload,
  ModuleRecord,
  ReviewItem,
  ReviewListParams,
  ReviewListResponse,
  RulesState,
  Session,
  SettingsSectionUpdatePayload
} from "../shared/api/types";

export const api = {
  ...authApi,
  ...reviewsApi,
  ...settingsApi,
  ...dataApi
};
