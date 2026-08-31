// Jezyki rozpoznawania. Wartosci to locale Data Dragon, z ktorych aplikacja
// bierze nazwy umiejetnosci; Whisper dostaje sam prefiks jezyka.
// Testowany byl polski. Pozostale, z angielskim wlacznie, sa nietestowane.

export interface RecognitionLanguage {
  value: string;
  label: string;
  tested: boolean;
}

export const RECOGNITION_LANGUAGES: RecognitionLanguage[] = [
  { value: 'pl_PL', label: 'Polski', tested: true },
  { value: 'en_US', label: 'English', tested: false },
  { value: 'de_DE', label: 'Deutsch', tested: false },
  { value: 'fr_FR', label: 'Français', tested: false },
  { value: 'es_ES', label: 'Español', tested: false },
  { value: 'it_IT', label: 'Italiano', tested: false },
  { value: 'pt_BR', label: 'Português (BR)', tested: false },
  { value: 'ru_RU', label: 'Русский', tested: false },
  { value: 'tr_TR', label: 'Türkçe', tested: false },
  { value: 'cs_CZ', label: 'Čeština', tested: false },
  { value: 'hu_HU', label: 'Magyar', tested: false },
  { value: 'ro_RO', label: 'Română', tested: false },
  { value: 'el_GR', label: 'Ελληνικά', tested: false },
  { value: 'ko_KR', label: '한국어', tested: false },
  { value: 'ja_JP', label: '日本語', tested: false },
  { value: 'zh_CN', label: '中文 (简体)', tested: false },
  { value: 'zh_TW', label: '中文 (繁體)', tested: false },
  { value: 'th_TH', label: 'ไทย', tested: false },
  { value: 'vi_VN', label: 'Tiếng Việt', tested: false },
  { value: 'id_ID', label: 'Bahasa Indonesia', tested: false },
  { value: 'ar_AE', label: 'العربية', tested: false },
];

export function languageOptions(untested: string): { value: string; label: string }[] {
  return RECOGNITION_LANGUAGES.map((l) => ({
    value: l.value,
    label: l.tested ? l.label : `${l.label} (${untested})`,
  }));
}
