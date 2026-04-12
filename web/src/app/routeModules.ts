type RouteLoader = () => Promise<unknown>;

const routeLoaders: Array<{ match: string; loader: RouteLoader }> = [
  { match: "/overview", loader: () => import("../pages/OverviewPage") },
  { match: "/modules", loader: () => import("../pages/ModulesPage") },
  { match: "/queue", loader: () => import("../pages/ReviewQueuePage") },
  { match: "/reviews/", loader: () => import("../pages/ReviewDetailPage") },
  { match: "/rules", loader: () => import("../pages/RulesPage") },
  { match: "/telegram", loader: () => import("../pages/TelegramPage") },
  { match: "/access", loader: () => import("../pages/AccessPage") },
  { match: "/data", loader: () => import("../pages/DataPage") },
  { match: "/quality", loader: () => import("../pages/QualityPage") }
];

const prefetched = new Set<string>();

export function loadOverviewPage() {
  return import("../pages/OverviewPage");
}

export function loadModulesPage() {
  return import("../pages/ModulesPage");
}

export function loadReviewQueuePage() {
  return import("../pages/ReviewQueuePage");
}

export function loadReviewDetailPage() {
  return import("../pages/ReviewDetailPage");
}

export function loadRulesPage() {
  return import("../pages/RulesPage");
}

export function loadTelegramPage() {
  return import("../pages/TelegramPage");
}

export function loadAccessPage() {
  return import("../pages/AccessPage");
}

export function loadDataPage() {
  return import("../pages/DataPage");
}

export function loadQualityPage() {
  return import("../pages/QualityPage");
}

function findLoader(pathname: string): RouteLoader | null {
  const normalized = String(pathname || "").trim();
  const exact = routeLoaders.find((entry) => entry.match === normalized);
  if (exact) return exact.loader;
  const prefix = routeLoaders.find((entry) => normalized.startsWith(entry.match));
  return prefix?.loader || null;
}

export function prefetchRouteModule(pathname: string): void {
  const normalized = String(pathname || "").trim();
  if (!normalized || prefetched.has(normalized)) {
    return;
  }
  const loader = findLoader(normalized);
  if (!loader) {
    return;
  }
  prefetched.add(normalized);
  void loader();
}
