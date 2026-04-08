export type Language = "ru" | "en";

export type TranslationParams = Record<string, string | number>;

export type TranslationDictionary = {
  [key: string]: string | TranslationDictionary;
};
