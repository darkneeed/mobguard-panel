import type { AppPermission } from "./permissions";

export type NavigationItem = {
  to: string;
  labelKey: string;
  exact?: boolean;
  permission?: AppPermission;
};

export type NavigationGroup = {
  titleKey: string;
  items: NavigationItem[];
};

export const primaryNavigation: NavigationGroup[] = [
  {
    titleKey: "layout.groups.monitor",
    items: [
      { to: "/overview", labelKey: "layout.nav.overview", permission: "overview.read" },
      { to: "/modules", labelKey: "layout.nav.modules", permission: "modules.read" },
      { to: "/queue", labelKey: "layout.nav.queue", permission: "reviews.read" },
      { to: "/decisions", labelKey: "layout.nav.decisions", permission: "data.read" },
      { to: "/quality/metrics", labelKey: "layout.nav.quality", permission: "quality.read" }
    ]
  },
  {
    titleKey: "layout.groups.configure",
    items: [
      { to: "/telegram", labelKey: "layout.nav.telegram", permission: "settings.telegram.read" },
      { to: "/system/access", labelKey: "layout.nav.system", permission: "settings.access.read" }
    ]
  },
  {
    titleKey: "layout.groups.operate",
    items: [
      { to: "/data/console", labelKey: "layout.nav.console", permission: "data.read" },
      { to: "/data/users", labelKey: "layout.nav.data", permission: "data.read" },
      { to: "/bedolaga", labelKey: "layout.nav.bedolaga", permission: "data.read" }
    ]
  }
];

export const qualityNavigation: NavigationItem[] = [
  { to: "/quality/metrics", labelKey: "layout.subnav.quality.metrics", permission: "quality.read" },
  { to: "/quality/learning", labelKey: "layout.subnav.quality.learning", permission: "rules.read" },
  { to: "/quality/ai-suggestions", labelKey: "layout.subnav.quality.aiSuggestions", permission: "rules.read" },
  { to: "/quality/ai-optimizer", labelKey: "layout.subnav.quality.aiOptimizer", permission: "rules.read" }
];

export const dataNavigation: NavigationItem[] = [
  { to: "/data/users", labelKey: "layout.subnav.data.users", permission: "data.read" },
  { to: "/data/ai-suggestions", labelKey: "layout.subnav.data.aiSuggestions", permission: "data.read" },
  { to: "/data/events", labelKey: "layout.subnav.data.events", permission: "data.read" },
];

export const systemNavigation: NavigationItem[] = [
  { to: "/system/access", labelKey: "layout.subnav.system.access", permission: "settings.access.read" },
  { to: "/system/branding", labelKey: "layout.subnav.system.branding", permission: "settings.access.read" },
  { to: "/system/general", labelKey: "layout.subnav.system.general", permission: "rules.read" },
  { to: "/system/thresholds", labelKey: "layout.subnav.system.thresholds", permission: "rules.read" },
  { to: "/system/lists", labelKey: "layout.subnav.system.lists", permission: "rules.read" },
  { to: "/system/providers", labelKey: "layout.subnav.system.providers", permission: "rules.read" },
  { to: "/system/retention", labelKey: "layout.subnav.system.retention", permission: "rules.read" }
];

export function getSecondaryNavigation(pathname: string): NavigationItem[] {
  if (pathname.startsWith("/quality")) {
    return qualityNavigation;
  }
  if (pathname.startsWith("/data")) {
    return dataNavigation;
  }
  if (pathname.startsWith("/system")) {
    return systemNavigation;
  }
  return [];
}
