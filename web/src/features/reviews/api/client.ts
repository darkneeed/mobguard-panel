import { buildSearchParams, request } from "../../../shared/api/request";
import { ReviewListParams, ReviewListResponse, RulesState } from "../../../shared/api/types";

export const reviewsApi = {
  listReviews: (params: ReviewListParams) =>
    request<ReviewListResponse>(`/admin/reviews?${buildSearchParams(params)}`),
  getReview: (caseId: string) => request<Record<string, unknown>>(`/admin/reviews/${caseId}`),
  resolveReview: (caseId: string, resolution: string, note: string) =>
    request<Record<string, unknown>>(`/admin/reviews/${caseId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ resolution, note })
    }),
  getRules: () => request<RulesState>("/admin/rules"),
  updateRules: (payload: { rules: Record<string, unknown>; revision: number; updated_at: string }) =>
    request<RulesState>("/admin/rules", {
      method: "PUT",
      body: JSON.stringify(payload)
    })
};
