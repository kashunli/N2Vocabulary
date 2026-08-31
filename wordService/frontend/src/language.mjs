export const LANGUAGE_STORAGE_KEY = "n2-word-service:language:v1";

/** Keep the preference deliberately small so unknown future values fail safe. */
export function normalizeLanguage(value) {
  return value === "zh" ? "zh" : "en";
}

export function readStoredLanguage(storage) {
  try {
    return normalizeLanguage(storage?.getItem(LANGUAGE_STORAGE_KEY));
  } catch {
    return "en";
  }
}
