"use client";

import { useEffect, useState } from "react";

export type Language = "ko" | "en";

const STORAGE_KEY = "kquant-language";

export function useLanguage() {
  const [language, setLanguageState] = useState<Language>("ko");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "ko" || saved === "en") {
      setLanguageState(saved);
      document.documentElement.lang = saved;
    } else {
      document.documentElement.lang = "ko";
    }
  }, []);

  function setLanguage(next: Language) {
    setLanguageState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = next;
  }

  return { language, setLanguage };
}
