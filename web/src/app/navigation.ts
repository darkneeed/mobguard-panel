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
      { to: "/quality", labelKey: "layout.nav.quality", permission: "quality.read" }
    ]
  },
  {
    titleKey: "layout.groups.configure",
    items: [
      { to: "/rules/general", labelKey: "layout.nav.rules", permission: "rules.read" },
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

export const rulesNavigation: NavigationItem[] = [
  { to: "/rules/general", labelKey: "layout.subnav.rules.general", permission: "rules.read" },
  { to: "/rules/thresholds", labelKey: "layout.subnav.rules.thresholds", permission: "rules.read" },
  { to: "/rules/lists", labelKey: "layout.subnav.rules.lists", permission: "rules.read" },
  { to: "/rules/providers", labelKey: "layout.subnav.rules.providers", permission: "rules.read" },
  { to: "/rules/learning", labelKey: "layout.subnav.rules.learning", permission: "rules.read" },
  { to: "/rules/retention", labelKey: "layout.subnav.rules.retention", permission: "rules.read" }
];

export const dataNavigation: NavigationItem[] = [
  { to: "/data/users", labelKey: "layout.subnav.data.users", permission: "data.read" },
  { to: "/data/events", labelKey: "layout.subnav.data.events", permission: "data.read" },
];

export const systemNavigation: NavigationItem[] = [
  { to: "/system/access", labelKey: "layout.subnav.system.access", permission: "settings.access.read" },
  { to: "/system/branding", labelKey: "layout.subnav.system.branding", permission: "settings.access.read" },
];

export function getSecondaryNavigation(pathname: string): NavigationItem[] {
  if (pathname.startsWith("/rules")) {
    return rulesNavigation;
  }
  if (pathname.startsWith("/data")) {
    return dataNavigation;
  }
  if (pathname.startsWith("/system")) {
    return systemNavigation;
  }
  return [];
}
