import { BrandingConfig } from "../api/client";

export type ThemeMode = "light" | "dark" | "system";
export type PaletteName = "green" | "orange" | "blue" | "purple" | "red";

export const THEME_KEY = "mobguard_theme";
export const LANGUAGE_KEY = "mobguard_language";
export const PALETTE_KEY = "mobguard_palette";
export const DEFAULT_PALETTE: PaletteName = "green";

export const DEFAULT_BRANDING: BrandingConfig = {
  panel_name: "MobGuard",
  panel_logo_url: "",
};
