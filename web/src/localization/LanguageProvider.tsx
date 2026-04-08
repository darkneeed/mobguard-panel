import { createContext, ReactNode, useContext, useEffect, useMemo } from "react";

import { enDictionary } from "./dictionaries/en";
import { ruDictionary } from "./dictionaries/ru";
import type { Language, TranslationDictionary, TranslationParams } from "./types";

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string, params?: TranslationParams) => string;
};

const dictionaries: Record<Language, TranslationDictionary> = {
  en: enDictionary,
  ru: ruDictionary
};

const LanguageContext = createContext<I18nContextValue | null>(null);

type LanguageProviderProps = {
  children: ReactNode;
  language: Language;
  setLanguage: (language: Language) => void;
};

function resolveTranslation(dictionary: TranslationDictionary, key: string): string {
  const value = key.split(".").reduce<string | TranslationDictionary | undefined>((current, segment) => {
    if (!current || typeof current === "string") {
      return undefined;
    }
    return current[segment];
  }, dictionary);

  return typeof value === "string" ? value : key;
}

function interpolate(template: string, params?: TranslationParams): string {
  if (!params) {
    return template;
  }

  return Object.entries(params).reduce(
    (result, [key, value]) => result.split(`{${key}}`).join(String(value)),
    template
  );
}

export function LanguageProvider({ children, language, setLanguage }: LanguageProviderProps) {
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo<I18nContextValue>(() => {
    const dictionary = dictionaries[language];

    return {
      language,
      setLanguage,
      t: (key, params) => interpolate(resolveTranslation(dictionary, key), params)
    };
  }, [language, setLanguage]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useI18n must be used within LanguageProvider");
  }
  return context;
}
