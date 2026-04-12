export type NavigationItem = {
  to: string;
  labelKey: string;
  exact?: boolean;
};

export type NavigationGroup = {
  titleKey: string;
  items: NavigationItem[];
};

export const primaryNavigation: NavigationGroup[] = [
  {
    titleKey: "layout.groups.monitor",
    items: [
      { to: "/overview", labelKey: "layout.nav.overview" },
      { to: "/modules", labelKey: "layout.nav.modules" },
      { to: "/queue", labelKey: "layout.nav.queue" },
      { to: "/quality", labelKey: "layout.nav.quality" }
    ]
  },
  {
    titleKey: "layout.groups.configure",
    items: [
      { to: "/rules/thresholds", labelKey: "layout.nav.rules" },
      { to: "/telegram", labelKey: "layout.nav.telegram" },
      { to: "/access", labelKey: "layout.nav.access" }
    ]
  },
  {
    titleKey: "layout.groups.operate",
    items: [{ to: "/data/users", labelKey: "layout.nav.data" }]
  }
];

export const rulesNavigation: NavigationItem[] = [
  { to: "/rules/general", labelKey: "layout.subnav.rules.general" },
  { to: "/rules/thresholds", labelKey: "layout.subnav.rules.thresholds" },
  { to: "/rules/lists", labelKey: "layout.subnav.rules.lists" },
  { to: "/rules/providers", labelKey: "layout.subnav.rules.providers" },
  { to: "/rules/policy", labelKey: "layout.subnav.rules.policy" },
  { to: "/rules/learning", labelKey: "layout.subnav.rules.learning" }
];

export const dataNavigation: NavigationItem[] = [
  { to: "/data/users", labelKey: "layout.subnav.data.users" },
  { to: "/data/violations", labelKey: "layout.subnav.data.violations" },
  { to: "/data/overrides", labelKey: "layout.subnav.data.overrides" },
  { to: "/data/cache", labelKey: "layout.subnav.data.cache" },
  { to: "/data/learning", labelKey: "layout.subnav.data.learning" },
  { to: "/data/cases", labelKey: "layout.subnav.data.cases" },
  { to: "/data/exports", labelKey: "layout.subnav.data.exports" }
];

export function getSecondaryNavigation(pathname: string): NavigationItem[] {
  if (pathname.startsWith("/rules")) {
    return rulesNavigation;
  }
  if (pathname.startsWith("/data")) {
    return dataNavigation;
  }
  return [];
}
